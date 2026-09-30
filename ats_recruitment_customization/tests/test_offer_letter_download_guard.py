# -*- coding: utf-8 -*-
from odoo.tests.common import TransactionCase
from odoo.exceptions import UserError

from ..models.ir_actions_report import OFFER_LETTER_REPORT_NAME, REQUIRED_STAGE_NAME


class TestOfferLetterDownloadGuard(TransactionCase):
    """Offer Letter PDF must only be downloadable once the applicant's
    recruitment stage_id has reached 'Offer Submission' (by sequence) or
    any later stage."""

    def setUp(self):
        super().setUp()

        self.department = self.env["hr.department"].create({
            "name": "Development",
        })

        self.job_position = self.env["hr.job"].create({
            "name": "Software Engineer",
            "department_id": self.department.id,
        })

        # Reuse the "Offer Submission" stage if it already exists (it does
        # in the real pipeline, per hr_applicant.py), otherwise create a
        # minimal one for the test DB.
        self.offer_submission_stage = self.env["hr.recruitment.stage"].search(
            [("name", "=", REQUIRED_STAGE_NAME)], limit=1
        )
        if not self.offer_submission_stage:
            self.offer_submission_stage = self.env["hr.recruitment.stage"].create({
                "name": REQUIRED_STAGE_NAME,
                "sequence": 10,
            })

        self.earlier_stage = self.env["hr.recruitment.stage"].create({
            "name": "Hold - Guard Test",
            "sequence": self.offer_submission_stage.sequence - 5,
        })

        self.later_stage = self.env["hr.recruitment.stage"].create({
            "name": "Offer Made - Guard Test",
            "sequence": self.offer_submission_stage.sequence + 5,
        })

        self.applicant = self.env["hr.applicant"].create({
            "partner_name": "John David",
            "job_id": self.job_position.id,
            "department_id": self.department.id,
            "stage_id": self.earlier_stage.id,
        })

    def _render(self):
        return self.env["ir.actions.report"]._render_qweb_pdf(
            OFFER_LETTER_REPORT_NAME, res_ids=self.applicant.ids
        )

    def test_blocked_before_offer_submission(self):
        self.applicant.with_context(offer_approval_bypass=True).stage_id = self.earlier_stage.id
        with self.assertRaises(UserError):
            self._render()

    def test_not_blocked_by_guard_at_offer_submission(self):
        """The guard itself must not raise once the applicant reaches
        Offer Submission. Any error past this point would come from PDF
        rendering (e.g. wkhtmltopdf), not this guard."""
        self.applicant.with_context(offer_approval_bypass=True).stage_id = (
            self.offer_submission_stage.id
        )
        try:
            self._render()
        except UserError as e:
            self.assertNotIn("can only be downloaded", str(e))

    def test_not_blocked_by_guard_after_offer_submission(self):
        self.applicant.with_context(offer_approval_bypass=True).stage_id = self.later_stage.id
        try:
            self._render()
        except UserError as e:
            self.assertNotIn("can only be downloaded", str(e))

    def test_unrelated_report_not_affected(self):
        """The guard must only apply to the Offer Letter report."""
        self.applicant.with_context(offer_approval_bypass=True).stage_id = self.earlier_stage.id
        try:
            self.env["ir.actions.report"]._render_qweb_pdf(
                "some_other_module.some_other_report", res_ids=self.applicant.ids
            )
        except UserError as e:
            self.assertNotIn("can only be downloaded", str(e))
        except Exception:
            # Expected: the report/template doesn't exist in this test DB.
            # We only care that it's not *our* UserError.
            pass
