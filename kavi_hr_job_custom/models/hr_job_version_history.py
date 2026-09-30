# -*- coding: utf-8 -*-
from odoo import api, fields, models, _
from odoo.tools import html2plaintext


class HrJobVersionHistory(models.Model):
    _name = 'hr.job.version.history'
    _description = 'Job Position Field Change History (structured)'
    _order = 'changed_on desc, id desc'

    job_id = fields.Many2one(
        'hr.job', string='Job Position', required=True,
        ondelete='cascade', index=True,
    )

   
    field_name = fields.Selection(
        selection='_selection_field_name', string='Field (technical)', required=True,
    )

  
    field_changed_picker = fields.Selection(
        selection='_selection_field_changed_picker', string='Field Changed',
        store=False, compute='_compute_field_changed_picker', readonly=False,
    )

   
    field_label = fields.Char(string='Field Changed (label)', required=True)
    old_value = fields.Html(string='Previous Value', sanitize=False)
    new_value = fields.Html(string='New Value', sanitize=False)

   
    old_value_text = fields.Text(
        string='Previous Value (text)', compute='_compute_value_text', store=True,
    )
    new_value_text = fields.Text(
        string='New Value (text)', compute='_compute_value_text', store=True,
    )

    changed_by = fields.Many2one(
        'res.users', string='Changed By',
        default=lambda self: self.env.user, readonly=True,
    )
    changed_on = fields.Datetime(
        string='Changed On', default=fields.Datetime.now, readonly=True,
    )

    @api.depends('old_value', 'new_value')
    def _compute_value_text(self):
        for rec in self:
            rec.old_value_text = html2plaintext(rec.old_value or '')
            rec.new_value_text = html2plaintext(rec.new_value or '')

    @api.model
    def _selection_field_name(self):
        """Full set of technical values this module ever creates - used
        internally by create()/write() in hr_job.py. Not the dropdown
        you see on screen; see _selection_field_changed_picker below for
        that."""
        options = [('__baseline__', _('Job Position Created'))]
        tracked = self.env['hr.job.tracked.field']._get_tracked_fields_map()
        for key, label in tracked.items():
            options.append((key, label))
        options.append(('work_mode', _('Work Mode')))
        return options

    @api.model
    def _selection_field_changed_picker(self):
        """Options for the visible 'Field Changed' picker: ONLY Budgeting
        Information and Key Roles and Responsibilities, sourced from
        Recruitment > Configuration > Tracked Fields so relabeling there
        is reflected here automatically. 'Job Position Created' and
        'Work Mode' are intentionally left out, per your request."""
        tracked = self.env['hr.job.tracked.field']._get_tracked_fields_map()
        return [(key, label) for key, label in tracked.items()]

    @api.depends('field_name')
    def _compute_field_changed_picker(self):
        allowed = dict(self._selection_field_changed_picker())
        for rec in self:
            rec.field_changed_picker = rec.field_name if rec.field_name in allowed else False

   
    @api.onchange('field_changed_picker')
    def _onchange_field_changed_picker(self):
        for rec in self:
            if not rec.field_changed_picker or not rec.job_id:
                continue
            latest = self.search([
                ('job_id', '=', rec.job_id.id),
                ('field_name', '=', rec.field_changed_picker),
            ], order='changed_on desc, id desc', limit=1)
            if latest:
                rec.field_label = latest.field_label
                rec.old_value = latest.old_value
                rec.new_value = latest.new_value
                rec.changed_on = latest.changed_on
                rec.changed_by = latest.changed_by
            else:
                rec.field_label = dict(rec._selection_field_changed_picker()).get(rec.field_changed_picker)
                rec.old_value = False
                rec.new_value = False

   
    _KAVI_PROTECTED_FIELDS = {
        'job_id', 'field_name', 'field_label', 'old_value', 'new_value',
        'changed_on', 'changed_by',
    }

    def write(self, vals):
        if not self.env.context.get('kavi_allow_history_write'):
            vals = {k: v for k, v in vals.items() if k not in self._KAVI_PROTECTED_FIELDS}
        if not vals:
            return True
        return super().write(vals)

    def name_get(self):
        result = []
        for rec in self:
            result.append((rec.id, f"{rec.field_label} - {rec.changed_on}"))
        return result

    
    def action_view_version_history_detail(self):
        self.ensure_one()
        form_view = self.env.ref('kavi_hr_job_custom.view_kavi_job_version_history_form')
        return {
            'type': 'ir.actions.act_window',
            'name': _('Version History'),
            'res_model': 'hr.job.version.history',
            'view_mode': 'form',
            'views': [(form_view.id, 'form')],
            'res_id': self.id,
            'target': 'current',
        }

   
    def action_back_to_version_history_list(self):
        self.ensure_one()
        list_view = self.env.ref('kavi_hr_job_custom.view_kavi_job_version_history_list')
        return {
            'type': 'ir.actions.act_window',
            'name': _('Version History'),
            'res_model': 'hr.job.version.history',
            'view_mode': 'list',
            'views': [(list_view.id, 'list')],
            'domain': [('job_id', '=', self.job_id.id)],
            'context': {'default_job_id': self.job_id.id},
            'target': 'current',
        }

   
    def action_discard_version_history_detail(self):
        self.ensure_one()
        return {
            'type': 'ir.actions.act_window',
            'name': self.job_id.display_name,
            'res_model': 'hr.job',
            'view_mode': 'form',
            'res_id': self.job_id.id,
            'target': 'current',
        }
