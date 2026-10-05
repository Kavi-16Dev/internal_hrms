from odoo import _, fields, models


class HrApplicantBlacklistWizard(models.TransientModel):
    _name = 'hr.applicant.blacklist.wizard'
    _description = 'Blacklist Applicant Wizard'

    applicant_id = fields.Many2one('hr.applicant', string='Applicant', required=True, readonly=True)
    reason = fields.Text(string='Reason', required=True)

    def action_confirm(self):
        self.ensure_one()
        applicant = self.applicant_id
        applicant.write({
            'blacklist_reason': self.reason,
            'is_applicant_blacklisted': True,
        })
        applicant.message_post(body=_("Applicant blacklisted. Reason: %s", self.reason))
        return {'type': 'ir.actions.act_window_close'}
