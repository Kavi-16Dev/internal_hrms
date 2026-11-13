from odoo import models, fields, api
from odoo.exceptions import UserError


class ApprovalCommentWizard(models.TransientModel):
    _name = 'ml.approval.comment.wizard'
    _description = 'Approval Comment Wizard'

    comment = fields.Text(string='Comments', default='Approval requested', required=True)
    purchase_order_id = fields.Many2one('purchase.order', string='Purchase Order')
    approval_level_id = fields.Many2one('ml.approval.level', string='Approval Level')

    def action_cancel_approval_wizard(self):
        return {'type': 'ir.actions.act_window_close'}

    def action_confirm_with_comment(self):
        self.ensure_one()
        if not self.comment:
            raise UserError('Please enter comments before proceeding.')

        # Close activities ONLY on actual confirm
        self.purchase_order_id._close_approval_activities()

        # Update the purchase order with the next level
        self.purchase_order_id.write({'current_approval_level_id': self.approval_level_id.id})


        # Create approval history record with comments
        self.env['ml.approval.history'].create({
            'purchase_order_id': self.purchase_order_id.id,
            'approval_level_id': self.approval_level_id.id,
            'action': 'recommended',
            'user_id': self.env.user.id,
            'notes': self.comment})

        # Create Todo Activity for each user in approval_level_id.user_ids
        activity_type = self.env.ref('mail.mail_activity_data_todo')
        purchase_order_model_id = self.env['ir.model']._get_id('purchase.order')
        for user in self.approval_level_id.user_ids:
            self.env['mail.activity'].create({
                'activity_type_id': activity_type.id,
                'res_model_id': purchase_order_model_id,
                'res_id': self.purchase_order_id.id,
                'user_id': user.id,
                'summary': f'Approval Required: {self.purchase_order_id.name}',
                # 'notes': self.comment,
            })
        return {'type': 'ir.actions.act_window_close'}