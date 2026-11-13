from odoo import models, fields, api, _
from markupsafe import Markup
from odoo.exceptions import UserError, ValidationError
from datetime import timedelta
from odoo.tools import html_escape 

class PurchaseOrder(models.Model):
    _inherit = 'purchase.order'

    approval_group_id = fields.Many2one(
        'ml.approval.group',
        string='Approval Group',
        tracking=True
    )
    current_approval_level_id = fields.Many2one(
        'ml.approval.level',
        string='Current Approval Level',
        tracking=True
    )

    approval_history_ids = fields.One2many(
        'ml.approval.history',
        'purchase_order_id',
        string='Approval History',
        readonly=True,
    )
    requires_approval = fields.Boolean(
        string='Requires Approval',
        compute='_compute_requires_approval',
        store=True
    )

    show_recommend_button = fields.Boolean(
        string='Show Recommend Button',
        compute='_compute_show_recommend_button',
        store=False
    )

    show_returned_button = fields.Boolean(
        string='Show Returned Button',
        compute='_compute_show_returned_button',
        store=False
    )

    show_approval_button = fields.Boolean(
        string='Show Approval Button',
        compute='_compute_show_approval_button',
        store=False
    )

    curr_pending_at_user_show = fields.Char(
        string='Pending At',
        compute='_compute_curr_pending_at_user_show',
        store=False
    )

    def _compute_show_recommend_button(self):
        for order in self:
            show_recommend_button = False
            line = order.current_approval_level_id or False
            if line and line.is_recommendation and line.active and self.env.user.id in line.user_ids.ids:
                show_recommend_button = True
            order.show_recommend_button = show_recommend_button

    def _compute_show_returned_button(self):
        for order in self:
            show_returned_button = False
            line = order.current_approval_level_id or False
            if line and (line.is_recommendation or line.is_approval) and line.active and self.env.user.id in line.user_ids.ids:
                show_returned_button = True
            order.show_returned_button = show_returned_button

    def _compute_show_approval_button(self):
        for order in self:
            show_approval_button = False
            line = order.current_approval_level_id or False
            if line and line.is_approval and line.active and self.env.user.id in line.user_ids.ids and order.amount_total <= line.max_amount:
                show_approval_button = True
            order.show_approval_button = show_approval_button

    def _compute_curr_pending_at_user_show(self):
        for order in self:
            curr_pending_at_user_show = ''
            line = order.current_approval_level_id or False
            if order.state == 'to approve':
                if line and line.active:
                    for user in line.user_ids:
                        curr_pending_at_user_show += user.name + ' [' + ('R' if line.is_recommendation else '') + ('A' if line.is_approval and order.amount_total <= line.max_amount else '') + '], '
                if len(curr_pending_at_user_show) == 0:
                    curr_pending_at_user_show = 'No user attached with this level of approval. Please attach the users in approval group!'
            order.curr_pending_at_user_show = curr_pending_at_user_show

    @api.depends('amount_total', 'approval_group_id', 'state')
    def _compute_requires_approval(self):
        for order in self:
            order.requires_approval = bool(
                order.approval_group_id and
                order.amount_total > 0 and
                order.state in ['draft', 'sent', 'to approve']
            )

    # -------------------------------------------------------------------------
    # Activity Helpers
    # -------------------------------------------------------------------------

    def _create_approval_activity(self, approval_level):
        print("_create_approval_activity called")
        print("\n"*5)
        self.ensure_one()
        if not approval_level or not approval_level.user_ids:
            return

        activity_type = self.env.ref('mail.mail_activity_data_todo')
        level_label = 'Recommendation' if approval_level.is_recommendation else 'Approval'

        for user in approval_level.user_ids:
            self.activity_schedule(
                'mail.mail_activity_data_todo',
                user_id=user.id,
                summary=f'PO {level_label} Required: {self.name}',
                # note=(
                #     f'Purchase Order <b>{self.name}</b> is pending your '
                #     f'<b>{level_label}</b> at level <b>{approval_level.name}</b>.'
                # ),
                # note = self.approval_history_ids.notes,
            )

    def _close_approval_activities(self, feedback='Processed.'):
        self.ensure_one()
        activities = self.env['mail.activity'].search([
            ('res_model', '=', 'purchase.order'),
            ('res_id', '=', self.id),
            ('activity_type_id', '=', self.env.ref('mail.mail_activity_data_todo').id),
            ('user_id', '=', self.env.uid),])
        if activities:
            activities.action_feedback(feedback=feedback)

    def _notify_buyer_approval_complete(self):
        self.ensure_one()
        buyer = self.user_id
        if not buyer:
            return

        activity_type = self.env.ref('mail.mail_activity_data_todo')
        self.activity_schedule(
            activity_type_id=activity_type.id,
            date_deadline=fields.Date.today() + timedelta(days=2),
            summary='Purchase Order Approved',
            note=Markup(
                '✅ Purchase Order <b>%s</b> has completed the full '
                'approval sequence and has been approved.'
            ) % self.name, user_id=buyer.id,)

        self.message_post( body=Markup(
                '✅ Purchase Order <b>%s</b> has completed the full '
                'approval sequence and has been approved.'
            ) % self.name, message_type='notification', partner_ids=[buyer.partner_id.id],)
            #  subtype_xmlid='mail.mt_comment'

    # -------------------------------------------------------------------------
    # Core Workflow Methods
    # -------------------------------------------------------------------------

    def button_cancel(self):
        for order in self:
            activities = self.env['mail.activity'].search([('res_model', '=', 'purchase.order'), ('res_id', '=', order.id),])
            if activities:
                activities.unlink()
            order.write({ 'current_approval_level_id': False,})
        return super(PurchaseOrder, self).button_cancel()

    def button_approve(self, force=False):
        orders_with_approval = self.filtered(lambda o: o.current_approval_level_id)

        for order in orders_with_approval:
            order._close_approval_activities()

            self.env['ml.approval.history'].create({
                'purchase_order_id': order.id,
                'approval_level_id': order.current_approval_level_id.id,
                'action': 'approved',
                'user_id': self.env.user.id,
                'notes': 'Approved',
            })

            order._notify_buyer_approval_complete()

        return super(PurchaseOrder, self).button_approve(force=force)

    def button_confirm(self):
        for order in self:
            if order.requires_approval and order.state in ['draft', 'sent']:
                return order.action_request_approval()
        result = super(PurchaseOrder, self).button_confirm()
        self._notify_buyer_approval_complete()
        return result

    def action_request_approval(self):
        self.ensure_one()
        if not self.approval_group_id:
            raise UserError('Please select an approval group first!')

        approval_level = self._get_next_approval_level()
        if not approval_level:
            return super(PurchaseOrder, self).button_confirm()

        self.write({
            'state': 'to approve',
            'current_approval_level_id': approval_level.id,
        })

        self.env['ml.approval.history'].create({
            'purchase_order_id': self.id,
            'approval_level_id': approval_level.id,
            'action': 'requested',
            'user_id': self.env.user.id,
            'notes': 'Request Created',
        })

        self._create_approval_activity(approval_level)

    def action_button_next_level(self):
        self.ensure_one()
        if not self.budget_information:
            raise UserError(_( "Please set the 'Budget Information' field before this "
                "Purchase Order can be approved (Level-2):\n%s" ) % self.name)
        
        if not self.approval_group_id:
            raise UserError('Please select an approval group first!')

        approval_level = self._get_next_approval_level()
        if not approval_level:
            raise UserError('Next Recommendation Level Not Set!')


        # REMOVED: self._close_approval_activities()

        return {
            'type': 'ir.actions.act_window',
            'name': 'Add Comments',
            'res_model': 'ml.approval.comment.wizard',
            'view_mode': 'form',
            'target': 'new',
            'context': {
                'default_purchase_order_id': self.id,
                'default_approval_level_id': approval_level.id,
            },
        }

    def action_button_prev_level(self):
        self.ensure_one()
        if not self.approval_group_id:
            raise UserError('Please select an approval group first!')

        approval_level = self._get_prev_approval_level()
        if not approval_level:
            raise UserError('Previous Recommendation Level Not Set!')

        # REMOVED: self._close_approval_activities()  ← was marking done prematurely
        return {
            'type': 'ir.actions.act_window',
            'name': 'Add Comments',
            'res_model': 'ml.returned.comment.wizard',
            'view_mode': 'form',
            'target': 'new',
            'context': {
                'default_purchase_order_id': self.id,
                'default_approval_level_id': approval_level.id,
            },
        }

    def _after_level_change(self, new_approval_level, action):
        self.ensure_one()
        self._create_approval_activity(new_approval_level)

    def _get_next_approval_level(self):
        if not self.approval_group_id:
            return False
        levels = self.approval_group_id.level_ids.filtered(lambda l: l.active).sorted('sequence')
        if self.current_approval_level_id:
            for level in levels:
                if level.sequence > self.current_approval_level_id.sequence:
                    return level
        else:
            return levels[0] if levels else False
        return False

    def _get_prev_approval_level(self):
        if not self.approval_group_id:
            return False
        levels = self.approval_group_id.level_ids.filtered(lambda l: l.active).sorted('sequence', reverse=True)
        if self.current_approval_level_id:
            for level in levels:
                if level.sequence < self.current_approval_level_id.sequence:
                    return level
        else:
            return levels[0] if levels else False
        return False


class ApprovalHistory(models.Model):
    _name = 'ml.approval.history'
    _description = 'Approval History'
    _order = 'create_date desc'

    purchase_order_id = fields.Many2one( 'purchase.order', string='Purchase Order', 
        required=True, ondelete='cascade', tracking=True, readonly = True, )
    
    approval_level_id = fields.Many2one(
        'ml.approval.level',
        string='Approval Level',
        required=True, tracking=True, readonly = True, )

    action = fields.Selection([
        ('requested', 'Approval Requested'),
        ('recommended', 'Recommended'),
        ('returned', 'Returned'),
        ('approved', 'Approved'),
        ('rejected', 'Rejected'), ], string='Action', required=True, tracking=True, readonly = True, )

    user_id = fields.Many2one(
        'res.users',
        string='User',
        required=True, tracking=True, readonly = True, )
    
    timestamp = fields.Datetime(
        string='Timestamp',
        default=fields.Datetime.now, tracking=True, readonly = True, )
    
    notes = fields.Text(string='Notes', tracking=True)
    

    # can_edit_comment = fields.Boolean( string='Can Edit Comment', compute='_compute_can_edit_comment', store=False, invisible=True)
    can_edit_comment = fields.Boolean(
        string='Can Edit Comment', 
        compute='_compute_can_edit_comment', 
        store=False, 
        invisible=True 
    )

    @api.depends('create_uid')
    def _compute_can_edit_comment(self):
        current_user = self.env.user
        for rec in self:
            # New records not yet saved don't have a create_uid yet.
            # Allow editing during creation, otherwise match current user with record creator.
            record_creator_id = rec.create_uid.id or self.env.uid
            
            if current_user.id == record_creator_id:
                rec.can_edit_comment = True
            else:
                rec.can_edit_comment = False

    def write(self, vals):
        if 'notes' in vals:
            current_user = self.env.user
            for rec in self:
                # Fallback to current user if it's a completely new/unsaved memory record
                record_creator_id = rec.create_uid.id or self.env.uid

                # Hard Wall: Check if the logged-in user is the literal creator of this comment row
                if current_user.id != record_creator_id:
                    raise ValidationError(
                        "Access Denied: You do not have permission to edit this comment. "
                        "Each comment entry can only be updated by the user who originally created it."
                    )

                # Post tracking details to chatter logs safely
                po = rec.purchase_order_id
                old_note = html_escape(rec.notes or '')
                new_note = html_escape(vals.get('notes', ''))
                user_name = html_escape(current_user.name or '')
                level_name = html_escape(rec.approval_level_id.name or 'N/A')

                raw_html = (
                    "<div>"
                    "   <h4 style='margin: 0 0 6px 0; color: #7C5B80; font-size: 14px;'>⚙️ Approval Comment Updated</h4>"
                    "   <ul style='list-style-type: none; padding-left: 0; margin: 0; line-height: 1.5; font-size: 13px;'>"
                    "       <li><b>User:</b> %s</li>"
                    "       <li><b>Approval Level:</b> %s</li>"
                    "       <li style='margin-top: 4px;'><span style='color: #b30000; text-decoration: line-through;'><b>Old Comment:</b> %s</span></li>"
                    "       <li><span style='color: #006622;'><b>New Comment:</b> %s</span></li>"
                    "   </ul>"
                    "</div>"
                ) % (user_name, level_name, old_note, new_note)

                formatted_body = Markup(raw_html)

                if po:
                    po.message_post(
                        body=formatted_body,
                        message_type='notification',
                        subtype_xmlid='mail.mt_note'
                    )

        return super(ApprovalHistory, self).write(vals)