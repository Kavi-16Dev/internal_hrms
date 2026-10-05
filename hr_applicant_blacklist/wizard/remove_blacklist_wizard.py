from odoo import _, fields, models


class HrApplicantRemoveBlacklistWizard(models.TransientModel):
    _name = 'hr.applicant.remove.blacklist.wizard'
    _description = 'Remove Applicant Blacklist Wizard'

    applicant_id = fields.Many2one('hr.applicant', string='Applicant', required=True, readonly=True)
    reason = fields.Text(string='Reason', required=True)

    def action_confirm(self):
        self.ensure_one()
        applicant = self.applicant_id
        applicant.write({
            'removed_blacklist_reason': self.reason,
            'is_applicant_blacklisted': False,
        })
        applicant.message_post(
            body=_("Blacklist removed. Reason: %s", self.reason),
        )
        # closes the dialog; the form reloads and the ribbon disappears
        return {'type': 'ir.actions.act_window_close'}
