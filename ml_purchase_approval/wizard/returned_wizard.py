from odoo import models, fields, api
from odoo.exceptions import UserError


class ReturnedCommentWizard(models.TransientModel):
    _name = 'ml.returned.comment.wizard'
    _description = 'Returned Comment Wizard'

    comment = fields.Text(string='Comments', required=True)
    purchase_order_id = fields.Many2one('purchase.order', string='Purchase Order')
    approval_level_id = fields.Many2one('ml.approval.level', string='Approval Level')

    def action_cancel_returned_wizard(self):
        return {'type': 'ir.actions.act_window_close'}
    

    def action_confirm_with_comment(self):
        self.ensure_one()
        if not self.comment:
            raise UserError('Please enter comments before proceeding.')

        # Close activities with "Returned." feedback instead of default "Processed."
        self.purchase_order_id._close_approval_activities(feedback='Returned.')

        # Update the purchase order with the previous level
        self.purchase_order_id.write({'current_approval_level_id': self.approval_level_id.id})

        # Create approval history record with comments
        self.env['ml.approval.history'].create({
            'purchase_order_id': self.purchase_order_id.id,
            'approval_level_id': self.approval_level_id.id,
            'action': 'returned',
            'user_id': self.env.user.id,
            'notes': f"Comments: {self.comment}",
        })

        # Get all approver user ids from the current approval level
        level_user_ids = self.approval_level_id.user_ids.ids

        if level_user_ids:
            # Find and mark done any related activity assigned to those users
            related_activities = self.env['mail.activity'].search([
                ('res_model', '=', 'purchase.order'),
                ('res_id', '=', self.purchase_order_id.id),
                ('user_id', 'in', level_user_ids),
            ])
            if related_activities:
                # related_activities.action_done()          # ← DELETE this line
                related_activities.action_feedback(feedback='Returned.')   # ← ADD this line instead

        # Notify via _after_level_change hook
        self.purchase_order_id._after_level_change(self.approval_level_id, 'returned')
        return {'type': 'ir.actions.act_window_close'}