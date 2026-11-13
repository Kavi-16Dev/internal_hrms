# Copyright 2018-2019 ForgeFlow, S.L.
# License LGPL-3.0 or later (https://www.gnu.org/licenses/lgpl-3.0)

from datetime import timedelta

from odoo import api, fields, models
from odoo.exceptions import UserError

_STATES = [
    ("draft", "Draft"),
    ("to_approve", "To be approved"),
    ("approved", "Approved"),
    ("in_progress", "In progress"),
    ("done", "Done"),
    ("rejected", "Rejected"),
]


class PurchaseRequest(models.Model):
    _name = "purchase.request"
    _description = "Purchase Request"
    _mail_post_access = "read"
    _inherit = ["mail.thread", "mail.activity.mixin"]
    _order = "id desc"

    @api.model
    def _company_get(self):
        return self.env["res.company"].browse(self.env.company.id)

    @api.model
    def _get_default_requested_by(self):
        return self.env["res.users"].browse(self.env.uid)

    @api.model
    def _get_default_name(self):
        return self.env["ir.sequence"].next_by_code("purchase.request")

    @api.model
    def _default_picking_type(self):
        type_obj = self.env["stock.picking.type"]
        company_id = self.env.context.get("company_id") or self.env.company.id
        types = type_obj.search(
            [("code", "=", "incoming"), ("warehouse_id.company_id", "=", company_id)]
        )
        if not types:
            types = type_obj.search(
                [("code", "=", "incoming"), ("warehouse_id", "=", False)]
            )
        return types[:1]

    @api.depends("state")
    def _compute_is_editable(self):
        for rec in self:
            if rec.state in (
                "to_approve",
                "approved",
                "rejected",
                "in_progress",
                "done",
            ):
                rec.is_editable = False
            else:
                rec.is_editable = True

    name = fields.Char(
        string="Request Reference",
        required=True,
        default=lambda self: self.env._("New"),
        tracking=True,
    )
    is_name_editable = fields.Boolean(
        default=lambda self: self.env.user.has_group("base.group_no_one"),
    )
    origin = fields.Char(string="Source Document")
    date_start = fields.Date(
        string="Creation date",
        help="Date when the user initiated the request.",
        default=fields.Date.context_today,
        tracking=True,
    )
    requested_by = fields.Many2one(
        comodel_name="res.users",
        required=True,
        copy=False,
        tracking=True,
        default=lambda self: self._get_default_requested_by(),
        index=True,
    )
    assigned_to = fields.Many2one( comodel_name="res.users", string="Approver", tracking=True,
        domain=lambda self: [("group_ids", "in", self.env.ref("purchase_request.group_purchase_request_manager").id,) ], 
        index=True, )
    
    description = fields.Text(string="Business Justification", required=True, tracking=True)

    company_id = fields.Many2one(comodel_name="res.company", required=False, default=lambda self: self._company_get(), tracking=True,)
    
    line_ids = fields.One2many(
        comodel_name="purchase.request.line",
        inverse_name="request_id",
        string="Products to Purchase",
        readonly=False,
        copy=True,
        tracking=True,
    )
    product_id = fields.Many2one(
        comodel_name="product.product",
        related="line_ids.product_id",
        string="Product",
        readonly=True,
    )
    state = fields.Selection(
        selection=_STATES,
        string="Status",
        index=True,
        tracking=True,
        required=True,
        copy=False,
        default="draft",
    )
    is_editable = fields.Boolean(compute="_compute_is_editable", readonly=True)
    to_approve_allowed = fields.Boolean(compute="_compute_to_approve_allowed")
    picking_type_id = fields.Many2one(
        comodel_name="stock.picking.type",
        string="Picking Type",
        required=True,
        default=lambda self: self._default_picking_type(),
    )
    line_count = fields.Integer(
        string="Purchase Request Line count",
        compute="_compute_line_count",
        readonly=True,
    )
    move_count = fields.Integer(
        string="Stock Move count", compute="_compute_move_count", readonly=True
    )
    purchase_count = fields.Integer(
        string="Purchases count", compute="_compute_purchase_count", readonly=True
    )
    currency_id = fields.Many2one(related="company_id.currency_id", readonly=True)
    estimated_cost = fields.Monetary(
        compute="_compute_estimated_cost",
        string="Total Estimated Cost",
        store=True,
    )

    @api.depends("line_ids", "line_ids.estimated_cost")
    def _compute_estimated_cost(self):
        for rec in self:
            rec.estimated_cost = sum(rec.line_ids.mapped("estimated_cost"))

    @api.depends("line_ids")
    def _compute_purchase_count(self):
        for rec in self:
            rec.purchase_count = len(rec.mapped("line_ids.purchase_lines.order_id"))

    def action_view_purchase_order(self):
        action = self.env["ir.actions.actions"]._for_xml_id("purchase.purchase_rfq")
        lines = self.mapped("line_ids.purchase_lines.order_id")
        if len(lines) > 1:
            action["domain"] = [("id", "in", lines.ids)]
        elif lines:
            action["views"] = [
                (self.env.ref("purchase.purchase_order_form").id, "form")
            ]
            action["res_id"] = lines.id
        return action

    @api.depends("line_ids")
    def _compute_move_count(self):
        for rec in self:
            rec.move_count = len(
                rec.mapped("line_ids.purchase_request_allocation_ids.stock_move_id")
            )

    def action_view_stock_picking(self):
        action = self.env["ir.actions.actions"]._for_xml_id(
            "stock.action_picking_tree_all"
        )
        # remove default filters
        action["context"] = {}
        lines = self.mapped(
            "line_ids.purchase_request_allocation_ids.stock_move_id.picking_id"
        )
        if len(lines) > 1:
            action["domain"] = [("id", "in", lines.ids)]
        elif lines:
            action["views"] = [(self.env.ref("stock.view_picking_form").id, "form")]
            action["res_id"] = lines.id
        return action

    @api.depends("line_ids")
    def _compute_line_count(self):
        for rec in self:
            rec.line_count = len(rec.mapped("line_ids"))

    def action_view_purchase_request_line(self):
        action = (
            self.env.ref("purchase_request.purchase_request_line_form_action")
            .sudo()
            .read()[0]
        )
        lines = self.mapped("line_ids")
        if len(lines) > 1:
            action["domain"] = [("id", "in", lines.ids)]
        elif lines:
            action["views"] = [
                (self.env.ref("purchase_request.purchase_request_line_form").id, "form")
            ]
            action["res_id"] = lines.ids[0]
        return action

    @api.depends("state", "line_ids.product_qty", "line_ids.cancelled")
    def _compute_to_approve_allowed(self):
        for rec in self:
            rec.to_approve_allowed = rec.state == "draft" and any(
                not line.cancelled and line.product_qty for line in rec.line_ids
            )

    def copy(self, default=None):
        default = dict(default or {})
        self.ensure_one()
        default.update({"state": "draft", "name": self._get_default_name()})
        return super().copy(default)

    @api.model
    def _get_partner_id(self, request):
        user_id = request.assigned_to or self.env.user
        return user_id.partner_id.id

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            if vals.get("name", self.env._("New")) == self.env._("New"):
                vals["name"] = self._get_default_name()
        requests = super().create(vals_list)
        for vals, request in zip(vals_list, requests, strict=True):
            if vals.get("assigned_to"):
                partner_id = self._get_partner_id(request)
                request.message_subscribe(partner_ids=[partner_id])
        return requests

    def write(self, vals):
        res = super().write(vals)
        for request in self:
            if vals.get("assigned_to"):
                partner_id = self._get_partner_id(request)
                request.message_subscribe(partner_ids=[partner_id])
        return res

    def _can_be_deleted(self):
        self.ensure_one()
        return self.state == "draft"

    @api.ondelete(at_uninstall=False)
    def _unlink_if_draft(self):
        for request in self:
            if not request._can_be_deleted():
                raise UserError(
                    self.env._(
                        "You cannot delete a purchase request which is not draft."
                    )
                )

    # def button_draft(self):
    #     self.mapped("line_ids").do_uncancel()
    #     return self.write({"state": "draft"})

    def button_draft(self):
        self.mapped("line_ids").do_uncancel()
        # Cancel all approval activities related to this PR
        activities = self.env["mail.activity"].search([
            ("res_model", "=", self._name),
            ("res_id", "in", self.ids), ])
        activities.unlink()

        return self.write({"state": "draft"})

    # def button_to_approve(self):
    #     self.to_approve_allowed_check()
    #     return self.write({"state": "to_approve"})

    def button_to_approve(self):
        self.to_approve_allowed_check()
        for rec in self:
            rec.activity_schedule(
                'mail.mail_activity_data_todo',
                user_id=rec.assigned_to.id,  # ✅ Changed from self.env.user.id to rec.assigned_to.id
                date_deadline=fields.Date.today() + timedelta(days=2),
                summary='Approval Required',
                note='Please review this record.' )
        return self.write({"state": "to_approve"})

    def button_approved(self):
        for rec in self:
            # Mark existing 'Approval Required' activity as done
            approval_activities = rec.activity_ids.filtered(
                lambda a: a.activity_type_id == self.env.ref('mail.mail_activity_data_todo')
                and a.summary == 'Approval Required'
            )
            for activity in approval_activities:
                activity.action_feedback(feedback='Approved')

            # Notify PR Creator
            if rec.requested_by:
                rec.message_post(
                    body=f"Purchase Requisition {rec.display_name} has been approved.",
                    partner_ids=[rec.requested_by.partner_id.id])

            # Find ALL Buyers: Users with Purchase > User access right
            all_users = rec.env['res.users'].search([
                ('active', '=', True),
                ('share', '=', False),
            ])
            buyers = all_users.filtered(
                lambda u: u.has_group('purchase.group_purchase_user')
            )

            if buyers:
                rec.message_post(
                    body=f"Purchase Requisition {rec.display_name} is approved and ready for Purchase Order creation.",
                    partner_ids=buyers.mapped('partner_id.id'))

                for buyer in buyers:
                    rec.activity_schedule(
                        'mail.mail_activity_data_todo',
                        user_id=buyer.id,
                        date_deadline=fields.Date.today() + timedelta(days=2),
                        summary='Create Purchase Order',
                        note=f'Please create a Purchase Order for the approved requisition {rec.display_name}.')
            else:
                fallback_user = rec.activity_user_id or rec.env.user
                rec.message_post(
                    body=f"Purchase Requisition {rec.display_name} is approved and ready for Purchase Order creation.",
                    partner_ids=[fallback_user.partner_id.id])

                rec.activity_schedule(
                    'mail.mail_activity_data_todo',
                    user_id=fallback_user.id,
                    date_deadline=fields.Date.today() + timedelta(days=2),
                    summary='Create Purchase Order',
                    note=f'Please create a Purchase Order for the approved requisition {rec.display_name}.')
        return self.write({"state": "approved"})


    def action_feedback(self, feedback=False, attachment_ids=None):
        print("action_feedback called on purchase")
        print("\n"*5)
        """
        Override action_feedback on mail.activity via the PR model.
        When any buyer marks 'Create Purchase Order' activity as done,
        auto-close the same activity for all other buyers on this PR.
        """
        # Call the original feedback first
        result = super().action_feedback(feedback=feedback, attachment_ids=attachment_ids)

        for rec in self:
            # Find and close all remaining 'Create Purchase Order' activities on this PR
            remaining_activities = rec.activity_ids.filtered(
                lambda a: a.activity_type_id == self.env.ref('mail.mail_activity_data_todo')
                and a.summary == 'Create Purchase Order' )
            for activity in remaining_activities:
                activity.action_feedback(
                    feedback=f'Auto-closed: Purchase Order creation was completed by another user.')
        return result

    def button_rejected(self):
        self.mapped("line_ids").do_cancel()
        for rec in self:
            # Mark approval activities as done
            activities = self.env["mail.activity"].search([ ("res_model", "=", rec._name), ("res_id", "=", rec.id),])
            activities.action_feedback(feedback="PR has been rejected.")
            # Post a message to notify the requested_by user
            if rec.requested_by:
                rec.message_post(
                    body=f"Purchase Requisition {rec.display_name} has been rejected.",
                    partner_ids=[rec.requested_by.partner_id.id],
                    message_type="comment",
                    subtype_xmlid="mail.mt_comment",)
        return self.write({"state": "rejected"})

    def button_in_progress(self):
        return self.write({"state": "in_progress"})

    def button_done(self):
        return self.write({"state": "done"})

    def check_auto_reject(self):
        """When all lines are cancelled the purchase request should be
        auto-rejected."""
        for pr in self:
            if not pr.line_ids.filtered(lambda line: line.cancelled is False):
                pr.write({"state": "rejected"})

    def to_approve_allowed_check(self):
        for rec in self:
            if not rec.to_approve_allowed:
                raise UserError(
                    self.env._(
                        "You can't request an approval for a purchase request "
                        "which is empty. (%(name)s)",
                        name=rec.name,
                    )
                )
