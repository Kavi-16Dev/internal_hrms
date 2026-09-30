# -*- coding: utf-8 -*-
from odoo import models, _
from odoo.exceptions import UserError

OFFER_LETTER_REPORT_NAME = "ats_recruitment_customization.report_offer_letter"

# Gate is on the hr.recruitment stage_id pipeline (the top statusbar:
# ... -> Hold -> Offer Submission -> Offer Made -> Offer Accepted ->
# Rejected -> Joined -> ...), NOT on the offer_approval_state statusbar
# inside the Offer Letter Components tab. Downloadable once the applicant's
# stage reaches "Offer Submission" (by sequence) and remains downloadable
# in every later stage, whatever it's named. Same stage name your
# hr_applicant.py already looks up for is_offer_submission_stage / the
# write() stage-skip guard - keep it consistent if that ever changes.
REQUIRED_STAGE_NAME = "Offer Submission"


class IrActionsReport(models.Model):
    _inherit = "ir.actions.report"

    def _render_qweb_pdf(self, report_ref, res_ids=None, data=None):
        """Block downloading the Offer Letter PDF unless the applicant's
        recruitment stage has reached 'Offer Submission' or later (by
        stage sequence).

        This is enforced here (server-side, at render time) rather than by
        hiding a button, so it applies no matter how the report is
        triggered - the auto-generated Print menu entry, a direct report
        URL, etc.
        """
        report_name = (
            report_ref if isinstance(report_ref, str)
            else getattr(report_ref, "report_name", False)
        )

        if report_name == OFFER_LETTER_REPORT_NAME and res_ids:
            applicants = self.env["hr.applicant"].browse(res_ids)

            required_stage = self.env["hr.recruitment.stage"].search(
                [("name", "=", REQUIRED_STAGE_NAME)], limit=1
            )

            if not required_stage:
                raise UserError(
                    _(
                        'The "%(stage)s" recruitment stage could not be found. '
                        'Please contact your administrator.'
                    )
                    % {"stage": REQUIRED_STAGE_NAME}
                )

            not_eligible = applicants.filtered(
                lambda a: a.stage_id.sequence < required_stage.sequence
            )

            if not_eligible:
                details = ", ".join(
                    "%s (%s)" % (
                        a.partner_name or a.display_name,
                        a.stage_id.name or _("No Stage"),
                    )
                    for a in not_eligible
                )
                raise UserError(
                    _(
                        'The Offer Letter can only be downloaded once the '
                        'application reaches the "%(stage)s" stage or later.\n\n'
                        'Not yet eligible: %(details)s'
                    )
                    % {"stage": REQUIRED_STAGE_NAME, "details": details}
                )

        return super()._render_qweb_pdf(report_ref, res_ids=res_ids, data=data)
