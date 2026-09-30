# -*- coding: utf-8 -*-
from unittest.mock import patch

from odoo.exceptions import ValidationError

from .common import DuplicateDetectionCommon


class TestDuplicateOnCreate(DuplicateDetectionCommon):

    def setUp(self):
        super().setUp()
        self.original = self._create_applicant(
            self.job_a, email='original@example.com', phone='9876543210'
        )

    def test_email_duplicate_is_blocked(self):
        with self.assertRaises(ValidationError):
            self.HrApplicant.create(
                self._make_applicant_vals(
                    self.job_a,
                    email='ORIGINAL@example.com',
                    phone='1111111111',
                )
            )

    def test_phone_duplicate_is_blocked(self):
        with self.assertRaises(ValidationError):
            self.HrApplicant.create(
                self._make_applicant_vals(
                    self.job_a,
                    email='new@example.com',
                    phone='(987) 654-3210',
                )
            )

    def test_email_and_phone_duplicate_are_blocked(self):
        with self.assertRaises(ValidationError):
            self.HrApplicant.create(
                self._make_applicant_vals(
                    self.job_a,
                    email='original@example.com',
                    phone='9876543210',
                )
            )

    def test_duplicate_is_blocked_for_job_board_source(self):
        with self.assertRaises(ValidationError):
            self.HrApplicant.create(
                self._make_applicant_vals(
                    self.job_a,
                    email='original@example.com',
                    phone='new-phone',
                    medium_id=self.medium_job_board.id,
                    source_id=self.source_linkedin.id,
                )
            )

    def test_duplicate_is_blocked_for_email_source(self):
        with self.assertRaises(ValidationError):
            self.HrApplicant.create(
                self._make_applicant_vals(
                    self.job_a,
                    email='new@example.com',
                    phone='9876543210',
                    medium_id=self.medium_email.id,
                    source_id=self.source_recruitment_inbox.id,
                )
            )

    def test_duplicate_is_blocked_for_backend_source(self):
        with self.assertRaises(ValidationError):
            self.HrApplicant.create(
                self._make_applicant_vals(
                    self.job_a,
                    email='original@example.com',
                    phone='new-phone',
                )
            )

    def test_duplicate_is_allowed_on_a_different_job(self):
        # Same Email as self.original, but for a different Job Position -
        # this must be allowed, not blocked.
        candidate = self.HrApplicant.create(
            self._make_applicant_vals(
                self.job_b,
                email='original@example.com',
                phone='2222222222',
            )
        )
        self.assertFalse(candidate.is_duplicate_application)
        self.assertFalse(candidate.duplicate_of_id)

    def test_duplicate_is_blocked_on_the_same_job(self):
        with self.assertRaises(ValidationError):
            self.HrApplicant.create(
                self._make_applicant_vals(
                    self.job_a,
                    email='original@example.com',
                    phone='2222222222',
                )
            )

    def test_no_duplicate_is_allowed(self):
        candidate = self.HrApplicant.create(
            self._make_applicant_vals(
                self.job_a,
                email='brand-new@example.com',
                phone='1234567890',
            )
        )
        self.assertFalse(candidate.is_duplicate_application)
        self.assertFalse(candidate.duplicate_of_id)

    def test_multi_record_create_rolls_back_when_any_record_is_duplicate(self):
        with self.assertRaises(ValidationError):
            self.HrApplicant.create([
                self._make_applicant_vals(
                    self.job_a,
                    email='fresh@example.com',
                    phone='3333333333',
                ),
                self._make_applicant_vals(
                    self.job_a,
                    email='original@example.com',
                    phone='4444444444',
                ),
            ])

    def test_skips_check_while_ocr_extraction_pending(self):
        with patch.object(
            self.HrApplicant.__class__,
            '_is_ocr_extraction_pending',
            return_value=True,
        ):
            candidate = self.HrApplicant.with_context(website_id=1).create(
                self._make_applicant_vals(
                    self.job_a,
                    email='original@example.com',
                    phone='9876543210',
                )
            )
        self.assertFalse(candidate.is_duplicate_application)
        self.assertFalse(candidate.duplicate_of_id)
