# -*- coding: utf-8 -*-

from odoo import api, fields, models, _
from odoo.exceptions import AccessError


class HrApplicant(models.Model):
    _inherit = "hr.applicant"

    is_current_user_recruiter = fields.Boolean(
        string="Can Change Stage",
        compute="_compute_is_current_user_recruiter",
    )

    is_interviewer = fields.Boolean(
        string="Is Interviewer",
        compute="_compute_is_interviewer",
    )

    @api.depends("user_id")
    def _compute_is_current_user_recruiter(self):
        is_officer = self.env.user.has_group(
            "hr_recruitment.group_hr_recruitment_user"
        )

        is_manager = self.env.user.has_group(
            "hr_recruitment.group_hr_recruitment_manager"
        )

        for applicant in self:
            applicant.is_current_user_recruiter = (
                is_officer or is_manager
            )

    @api.depends("interviewer_ids")
    def _compute_is_interviewer(self):
        current_user = self.env.user

        for applicant in self:
            applicant.is_interviewer = (
                current_user in applicant.interviewer_ids
            )

    def write(self, vals):

        # Allow Odoo internal / automated operations
        if self.env.su:
            return super().write(vals)

        # ---------------------------------------------------------
        # INTERVIEWER RESTRICTION
        # ---------------------------------------------------------
        # If the current user is selected in the applicant's
        # Interviewers field, they cannot edit the applicant.
        # This check is done before the Officer/Manager check.
        # ---------------------------------------------------------

        interviewer_applicants = self.filtered(
            lambda applicant: self.env.user in applicant.interviewer_ids
        )

        if interviewer_applicants:
            raise AccessError(_(
                "You are an Interviewer for this applicant and "
                "do not have permission to edit the applicant."
            ))

        # ---------------------------------------------------------
        # RECRUITMENT OFFICER / MANAGER
        # ---------------------------------------------------------
        # Officers and Managers can manage all applicants.
        # They can also change the pipeline stage.
        # ---------------------------------------------------------

        if (
            self.env.user.has_group(
                "hr_recruitment.group_hr_recruitment_user"
            )
            or self.env.user.has_group(
                "hr_recruitment.group_hr_recruitment_manager"
            )
        ):
            return super().write(vals)

        # ---------------------------------------------------------
        # OTHER USERS
        # ---------------------------------------------------------

        if "stage_id" in vals:
            self._check_stage_change_allowed(
                vals.get("stage_id")
            )

        return super().write(vals)

    def _check_stage_change_allowed(self, new_stage_id):

        for applicant in self:

            # No actual stage change
            if new_stage_id == applicant.stage_id.id:
                continue

            raise AccessError(_(
                "You do not have permission to change the "
                "pipeline stage of candidate '%(candidate)s'."
            ) % {
                "candidate": applicant.partner_name
                or applicant.display_name,
            })