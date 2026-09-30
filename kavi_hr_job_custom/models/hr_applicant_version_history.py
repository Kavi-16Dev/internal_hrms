# -*- coding: utf-8 -*-
from odoo import api, fields, models, _
from odoo.tools import html2plaintext


class HrApplicantVersionHistory(models.Model):
    _name = 'hr.applicant.version.history'
    _description = 'Applicant Field Change History (structured)'
    _order = 'changed_on desc, id desc'

    applicant_id = fields.Many2one(
        'hr.applicant', string='Applicant', required=True,
        ondelete='cascade', index=True,
    )

   
    field_name = fields.Char(string='Field (technical)', required=True)
    field_label = fields.Char(string='Field Changed', required=True)
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

    def name_get(self):
        result = []
        for rec in self:
            result.append((rec.id, f"{rec.field_label} - {rec.changed_on}"))
        return result

  
    def action_view_version_history_detail(self):
        self.ensure_one()
        form_view = self.env.ref('kavi_hr_job_custom.view_kavi_applicant_version_history_form')
        return {
            'type': 'ir.actions.act_window',
            'name': _('Version History'),
            'res_model': 'hr.applicant.version.history',
            'view_mode': 'form',
            'views': [(form_view.id, 'form')],
            'res_id': self.id,
            'target': 'current',
        }

   
    def action_back_to_version_history_list(self):
        self.ensure_one()
        list_view = self.env.ref('kavi_hr_job_custom.view_kavi_applicant_version_history_list')
        return {
            'type': 'ir.actions.act_window',
            'name': _('Version History'),
            'res_model': 'hr.applicant.version.history',
            'view_mode': 'list',
            'views': [(list_view.id, 'list')],
            'domain': [('applicant_id', '=', self.applicant_id.id)],
            'context': {'default_applicant_id': self.applicant_id.id},
            'target': 'current',
        }

    
    def action_discard_version_history_detail(self):
        self.ensure_one()
        return {
            'type': 'ir.actions.act_window',
            'name': self.applicant_id.display_name,
            'res_model': 'hr.applicant',
            'view_mode': 'form',
            'res_id': self.applicant_id.id,
            'target': 'current',
        }
