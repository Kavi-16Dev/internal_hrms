from odoo import _, fields, models
from odoo.exceptions import UserError


class HrApplicant(models.Model):
    _inherit = 'hr.applicant'

    is_applicant_blacklisted = fields.Boolean(string='Blacklisted', tracking=True, copy=False)
    blacklist_reason = fields.Text(string='Blacklisted Reason', copy=False)
    removed_blacklist_reason = fields.Text(string='Removed Blacklist', copy=False)

    def action_open_blacklist_wizard(self):
        """Server action entry point: open the 'why blacklist' dialog on the current screen."""
        self.ensure_one()
        if self.is_applicant_blacklisted:
            raise UserError(_("This applicant is already blacklisted."))
        return {
            'type': 'ir.actions.act_window',
            'name': _('Blacklist Applicant'),
            'res_model': 'hr.applicant.blacklist.wizard',
            'view_mode': 'form',
            'target': 'new',
            'context': {'default_applicant_id': self.id},
        }

    def action_open_remove_blacklist_wizard(self):
        """Server action entry point: open the 'why remove blacklist' dialog."""
        self.ensure_one()
        if not self.is_applicant_blacklisted:
            raise UserError(_("This applicant is not blacklisted."))
        return {
            'type': 'ir.actions.act_window',
            'name': _('Remove Blacklist'),
            'res_model': 'hr.applicant.remove.blacklist.wizard',
            'view_mode': 'form',
            'target': 'new',
            'context': {'default_applicant_id': self.id},
        }
