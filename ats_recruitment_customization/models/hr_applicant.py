# -*- coding: utf-8 -*-
from odoo import api, fields, models, _
from odoo.exceptions import UserError


class HrApplicant(models.Model):
    _inherit = "hr.applicant"

    # ---------------------------------------------------------------
    # Offer Letter Components fields
    # ---------------------------------------------------------------
    offer_date = fields.Date(string="Offer Date", tracking=True)
    joining_date = fields.Date(string="Joining Date", tracking=True)
    offer_designation_id = fields.Many2one(
        "hr.job", string="Designation", tracking=True
    )
    # salary_structure = fields.Html(string="Salary Structure", tracking=True)
    offer_salary_structure = fields.Html(
        string="Salary Structure"
    )
    offer_note = fields.Html(string="Note")
    # salary_note = fields.Html(string="Note", tracking=True)

    offer_approval_state = fields.Selection(
        [
            ("draft", "Draft"),
            ("submitted", "Submitted for Approval"),
            ("approved", "Approved"),
            ("rejected", "Rejected"),
        ],
        string="Offer Approval Status",
        default="draft",
        tracking=True,
        copy=False,
    )
    offer_submitted_by_id = fields.Many2one(
        "res.users", string="Submitted By", readonly=True, copy=False
    )
    offer_activity_ids = fields.Many2many(
        "mail.activity",
        "hr_applicant_offer_activity_rel",
        "applicant_id",
        "activity_id",
        string="Pending Approval Activities",
        copy=False,
    )

    is_offer_submission_stage = fields.Boolean(
        string="Is Offer Submission Stage",
        compute="_compute_is_offer_submission_stage",
    )
    is_offer_approval_stage = fields.Boolean(
        string="Is Offer Approval Stage",
        compute="_compute_is_offer_approval_stage",
    )
    can_approve_offer = fields.Boolean(
        string="Can Approve/Reject Offer",
        compute="_compute_can_approve_offer",
    )

    # ---------------------------------------------------------------
    # Compute
    # ---------------------------------------------------------------
    @api.depends("stage_id")
    def _compute_is_offer_submission_stage(self):
        offer_submission_stage = self.env["hr.recruitment.stage"].search(
            [("name", "=", "Offer Submission")],
            limit=1,
        )
        
        for rec in self:
            rec.is_offer_submission_stage = bool(offer_submission_stage) and (
                rec.stage_id.id == offer_submission_stage.id
            )

    @api.depends("stage_id")
    def _compute_is_offer_approval_stage(self):
        approval_stage = self.env["hr.recruitment.stage"].search(
            [("name", "=", "Offer Approval")],
            limit=1,
        )
        
        for rec in self:
            rec.is_offer_approval_stage = bool(approval_stage) and (
                rec.stage_id.id == approval_stage.id
            )

    @api.depends_context("uid")
    def _compute_can_approve_offer(self):
        can_approve = self.env.user.is_recruitment_offer_approver
        for rec in self:
            rec.can_approve_offer = can_approve

    # ---------------------------------------------------------------
    # Button actions
    # ---------------------------------------------------------------
    def action_submit_offer(self):
        self.ensure_one()
        if not (self.designation and self.offer_salary_structure and self.joining_date):
            raise UserError(
                _(
                    "Please fill in Designation, Salary Structure/Breakup and "
                    "Joining Date before submitting the offer for approval."
                )
            )

        approvers = self.env["res.users"].search(
            [("is_recruitment_offer_approver", "=", True)]
        )
        if not approvers:
            raise UserError(
                _(
                    "No Recruitment Offer Approver is configured. Please enable "
                    "'Can Approve/Reject Offers' on at least one user (Settings > "
                    "Users > Access Rights tab) before submitting offers for "
                    "approval."
                )
            )

        self.write(
            {
                "offer_approval_state": "submitted",
                "offer_submitted_by_id": self.env.uid,
            }
        )

        activities = self.env["mail.activity"]
        for approver in approvers:
            activities |= self.activity_schedule(
                "mail.mail_activity_data_todo",
                summary=_("Offer Approval Required: %s") % (self.partner_name or self.display_name),
                note=_(
                    "Please review and Approve or Reject the submitted offer "
                    "details for %s."
                )
                % (self.partner_name or self.display_name),
                user_id=approver.id,
            )
        self.offer_activity_ids = [(6, 0, activities.ids)]
        self.message_post(
            body=_("Offer submitted for approval by %s.") % self.env.user.name
        )

    def action_approve_offer(self):
        self._check_can_approve_offer()
        approval_stage = self.env.ref(
            "recruitment_offer_approval.stage_offer_approval", raise_if_not_found=False
        )
        for rec in self:
            rec.offer_approval_state = "approved"
            rec._discard_offer_activities()
            if approval_stage:
                rec.with_context(offer_approval_bypass=True).stage_id = approval_stage.id
            rec._notify_offer_decision("approved")

    def action_reject_offer(self):
        self._check_can_approve_offer()
        for rec in self:
            rec.offer_approval_state = "rejected"
            rec._discard_offer_activities()
            rec._notify_offer_decision("rejected")

    def action_reset_to_draft_offer(self):
        offer_submission_stage = self.env["hr.recruitment.stage"].search(
            [("name", "=", "Offer Submission")],
            limit=1,
        )
        
        for rec in self:
            rec._discard_offer_activities()
            rec.offer_approval_state = "draft"
            if offer_submission_stage and rec.stage_id.id != offer_submission_stage.id:
                rec.with_context(offer_approval_bypass=True).stage_id = offer_submission_stage.id
            rec.message_post(
                body=_("Offer reset to draft by %s.") % self.env.user.name
            )

    # ---------------------------------------------------------------
    # Helpers
    # ---------------------------------------------------------------
    def _check_can_approve_offer(self):
        if not self.env.user.is_recruitment_offer_approver:
            raise UserError(
                _("You are not authorized to approve or reject offers.")
            )

    def _discard_offer_activities(self):
        """Remove any pending approval activities so they disappear
        immediately for the approver(s), whatever the outcome."""
        self.ensure_one()
        if self.offer_activity_ids:
            self.offer_activity_ids.unlink()
            self.offer_activity_ids = [(5, 0, 0)]

    def _notify_offer_decision(self, decision):
        self.ensure_one()
        if self.offer_submitted_by_id:
            self.activity_schedule(
                "mail.mail_activity_data_todo",
                summary=_("Offer %s") % (decision.capitalize(),),
                note=_("The offer for %s has been %s by %s.")
                % (self.partner_name or self.display_name, decision, self.env.user.name),
                user_id=self.offer_submitted_by_id.id,
            )
        partner_ids = (
            self.offer_submitted_by_id.partner_id.ids
            if self.offer_submitted_by_id
            else []
        )
        self.message_post(
            body=_("Offer has been %s by %s.") % (decision, self.env.user.name),
            partner_ids=partner_ids,
        )

    # ---------------------------------------------------------------
    # Guard rails
    # ---------------------------------------------------------------
    def write(self, vals):
        if "stage_id" in vals and not self.env.context.get("offer_approval_bypass"):

            Stage = self.env["hr.recruitment.stage"]

            offer_submission_stage = Stage.search(
                [("name", "=", "Offer Submission")], limit=1
            )

            if offer_submission_stage:
                new_stage = Stage.browse(vals["stage_id"])

                for rec in self:

                    # 1. Prevent skipping Offer Submission
                    if (
                        rec.stage_id.sequence < offer_submission_stage.sequence
                        and new_stage.sequence > offer_submission_stage.sequence
                    ):
                        raise UserError(
                            _(
                                "You must move the applicant to the Offer Submission stage before proceeding to later stages."
                            )
                        )

                    # 2. When in Offer Submission, approval is required before moving forward
                    if (
                        rec.stage_id.id == offer_submission_stage.id
                        and new_stage.sequence > offer_submission_stage.sequence
                        and rec.offer_approval_state != "approved"
                    ):
                        raise UserError(
                            _(
                                "Please approve the offer before moving to the next stage."
                            )
                        )

        return super().write(vals)
    # def write(self, vals):
    #     if "stage_id" in vals and not self.env.context.get("offer_approval_bypass"):

    #         offer_submission_stage = self.env.ref(
    #             "recruitment_offer_approval.stage_offer_submission",
    #             raise_if_not_found=False,
    #         )

    #         if offer_submission_stage:
    #             new_stage = self.env["hr.recruitment.stage"].browse(vals["stage_id"])

    #             for rec in self:
    #                 # Restrict only when applicant is currently in Offer Submission
    #                 if rec.stage_id.id == offer_submission_stage.id:

    #                     # Moving forward?
    #                     if (
    #                         new_stage.sequence > offer_submission_stage.sequence
    #                         and rec.offer_approval_state != "approved"
    #                     ):
    #                         raise UserError(
    #                             _(
    #                                 "Please approve the offer before moving to the next stage."
    #                             )
    #                         )

    #     return super().write(vals)
    