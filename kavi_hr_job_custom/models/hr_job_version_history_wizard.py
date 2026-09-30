# -*- coding: utf-8 -*-
from markupsafe import Markup
from odoo import api, fields, models, _
from odoo.exceptions import UserError
from odoo.tools import html2plaintext


class HrJobVersionHistoryWizard(models.TransientModel):
    """Popup ('Version History') for hr.job - mirrors the reference UI:
    a timeline of past versions on the left (radio list), the content of
    the selected version on the right, a 'View comparison' toggle that
    shows Previous Value vs New Value side by side, and Restore/Discard
    buttons at the bottom.

    Opened (target='new', i.e. as a dialog) from action_open_job_version_
    history() on hr.job - see models/hr_job.py.
    """
    _name = 'hr.job.version.history.wizard'
    _description = 'Job Position Version History (Popup)'

    job_id = fields.Many2one('hr.job', string='Job Position', required=True)

   
    history_id = fields.Many2one(
        'hr.job.version.history', string='Select Version',
        domain="[('job_id', '=', job_id), ('field_name', '=', snapshot_field_name)]"
               " if snapshot_field_name else [('job_id', '=', job_id)]",
    )

    show_comparison = fields.Boolean(string='Show Comparison', default=False)

    
    field_snapshot_view = fields.Boolean(string='Field Snapshot View', default=False)

    
    snapshot_field_name = fields.Char(string='Snapshot Field (technical)')

  
    _KAVI_SNAPSHOT_FIELD_LABELS = {
        'key_responsibilities': 'Key Roles and Responsibilities',
        'budgeting_information': 'Budgeting Information',
    }

    
    preview_field_label = fields.Char(
        string='Field Changed', compute='_compute_preview_field_label', readonly=True,
    )

    @api.depends('history_id.field_label', 'snapshot_field_name')
    def _compute_preview_field_label(self):
        for rec in self:
            if rec.history_id:
                rec.preview_field_label = rec.history_id.field_label
            elif rec.snapshot_field_name:
                tracked_fields = rec.env['hr.job.tracked.field']._get_tracked_fields_map()
                rec.preview_field_label = (
                    tracked_fields.get(rec.snapshot_field_name)
                    or rec._KAVI_SNAPSHOT_FIELD_LABELS.get(rec.snapshot_field_name)
                    or rec.snapshot_field_name
                )
            else:
                rec.preview_field_label = False

    preview_changed_on = fields.Datetime(related='history_id.changed_on', string='Date & Time', readonly=True)
    preview_changed_by = fields.Many2one(related='history_id.changed_by', string='Changed By', readonly=True)
    preview_old_value = fields.Html(related='history_id.old_value', string='Previous Value', readonly=True)
    preview_new_value = fields.Html(related='history_id.new_value', string='New Value', readonly=True)

   
    preview_empty_message = fields.Char(
        string='Empty Value Message', compute='_compute_preview_empty_message',
    )

    @api.depends('preview_field_label')
    def _compute_preview_empty_message(self):
        for rec in self:
            label = rec.preview_field_label or _('field')
            rec.preview_empty_message = _('The %s was empty at the time.') % (label,)

    
    diff_html = fields.Html(string='Differences', compute='_compute_diff_html', sanitize=False)

    def _get_latest_value_text(self):
        self.ensure_one()
        if not self.job_id or not self.history_id:
            return ''
        latest = self.env['hr.job.version.history'].search(
            [('job_id', '=', self.job_id.id), ('field_name', '=', self.history_id.field_name)],
            order='changed_on desc, id desc', limit=1,
        )
        return html2plaintext(latest.new_value or '') if latest else ''

    @api.depends('history_id', 'job_id')
    def _compute_diff_html(self):
        for rec in self:
            if not rec.history_id or not rec.job_id or rec.is_latest_version:
                rec.diff_html = False
                continue
            current_text = rec._get_latest_value_text()
            old_text = html2plaintext(rec.history_id.new_value or '')
            if not current_text and not old_text:
                rec.diff_html = False
                continue
            diff = Markup('')
            if current_text:
                diff += Markup('<span class="o_kavi_vh_diff_added">%s</span>') % current_text
            if old_text:
                diff += Markup('<span class="o_kavi_vh_diff_removed">%s</span>') % old_text
            rec.diff_html = diff

  
    is_latest_version = fields.Boolean(string='Is Latest Version', compute='_compute_is_latest_version')

    @api.depends('history_id', 'job_id')
    def _compute_is_latest_version(self):
        for rec in self:
            if not rec.history_id or not rec.job_id:
                rec.is_latest_version = False
                continue
            latest = self.env['hr.job.version.history'].search(
                [('job_id', '=', rec.job_id.id), ('field_name', '=', rec.history_id.field_name)],
                order='changed_on desc, id desc', limit=1,
            )
            rec.is_latest_version = bool(latest and latest.id == rec.history_id.id)

    @api.model
    def default_get(self, fields_list):
        res = super().default_get(fields_list)
        job_id = self.env.context.get('default_job_id')
        if job_id and 'history_id' in fields_list and not res.get('history_id'):
            latest = self.env['hr.job.version.history'].search(
                [('job_id', '=', job_id)], order='changed_on desc, id desc', limit=1,
            )
            if latest:
                res['history_id'] = latest.id
        return res

    def _reopen_self(self):
        self.ensure_one()
        name = _('Version History')
        if self.field_snapshot_view and self.preview_field_label:
            name = _('%s History') % (self.preview_field_label,)
        return {
            'type': 'ir.actions.act_window',
            'name': name,
            'res_model': 'hr.job.version.history.wizard',
            'view_mode': 'form',
            'res_id': self.id,
            'target': 'new',
        }

    def action_toggle_comparison(self):
        self.ensure_one()
        self.show_comparison = not self.show_comparison
        return self._reopen_self()

    def _open_field_snapshot(self, field_name):
        """Jump straight to the latest change recorded for `field_name`
        and switch the popup into the stripped-down Previous Value / New
        Value / Date & Time snapshot view. Used by the two "Menu"
        submenus below.

        BUG FIX: this used to raise UserError('No recorded changes yet
        for this field.') whenever `field_name` had never been changed
        on this Job Position - which is exactly why ONE submenu worked
        (its field already had history) while the OTHER one popped the
        "Invalid Operation" error dialog. A field simply not having been
        edited yet is a normal, expected state, not an error - so now we
        still switch into the snapshot view (history_id left empty) and
        let the view show a friendly "no changes recorded yet" message
        instead of blocking the whole popup.
        """
        self.ensure_one()
        latest = self.env['hr.job.version.history'].search(
            [('job_id', '=', self.job_id.id), ('field_name', '=', field_name)],
            order='changed_on desc, id desc', limit=1,
        )
        self.write({
            'history_id': latest.id if latest else False,
            'show_comparison': False,
            'field_snapshot_view': True,
            'snapshot_field_name': field_name,
        })
        return self._reopen_self()

    def action_view_key_responsibilities(self):
        return self._open_field_snapshot('key_responsibilities')

    def action_view_budgeting_information(self):
        return self._open_field_snapshot('budgeting_information')

    def action_back_to_full_history(self):
        self.ensure_one()
        self.write({'field_snapshot_view': False, 'snapshot_field_name': False, 'show_comparison': False})
        return self._reopen_self()

    def action_restore_history(self):
        self.ensure_one()
        if not self.history_id:
            raise UserError(_('Select a version to restore first.'))
        if self.is_latest_version:
            raise UserError(_('This is already the current version - nothing to restore.'))

        tracked_fields = self.env['hr.job.tracked.field']._get_tracked_fields_map()
        field_name = self.history_id.field_name
        if field_name not in tracked_fields:
            raise UserError(_(
                'This entry ("%s") is informational only and cannot be '
                'restored. Only Budgeting Information and Key Roles and '
                'Responsibilities versions can be restored.'
            ) % (self.history_id.field_label,))

        self.job_id.write({field_name: self.history_id.new_value})

     
        if field_name in self.job_id._KAVI_NATIVE_HISTORY_FIELDS:
            self.job_id._kavi_reset_native_html_history([field_name])

        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {
                'title': _('Version Restored'),
                'message': _('%s has been restored to the selected version.') % (self.history_id.field_label,),
                'type': 'success',
                'next': {
                    'type': 'ir.actions.act_window',
                    'res_model': 'hr.job',
                    'view_mode': 'form',
                    'res_id': self.job_id.id,
                    'target': 'current',
                },
            },
        }

    def action_discard(self):
        return {'type': 'ir.actions.act_window_close'}
