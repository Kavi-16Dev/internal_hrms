# -*- coding: utf-8 -*-
from unittest.mock import patch

from odoo.exceptions import ValidationError

from .common import DuplicateDetectionCommon


class TestDuplicateOnWrite(DuplicateDetectionCommon):

    def setUp(self):
        super().setUp()
        self.original = self._create_applicant(
            self.job_a, email='original@example.com', phone='9876543210'
        )

    def test_editing_email_into_duplicate_is_blocked(self):
        candidate = self._create_applicant(
            self.job_a, email='unique@example.com', phone='1111111111'
        )
        with self.assertRaises(ValidationError):
            candidate.write({'email_from': 'original@example.com'})

    def test_editing_phone_into_duplicate_is_blocked(self):
        candidate = self._create_applicant(
            self.job_a, email='unique2@example.com', phone='2222222222'
        )
        with self.assertRaises(ValidationError):
            candidate.write({self.PHONE_FIELD: '9876543210'})

    def test_editing_both_into_duplicate_is_blocked(self):
        candidate = self._create_applicant(
            self.job_a, email='unique3@example.com', phone='3333333333'
        )
        with self.assertRaises(ValidationError):
            candidate.write({
                'email_from': 'original@example.com',
                self.PHONE_FIELD: '9876543210',
            })

    def test_duplicate_write_is_blocked_for_non_portal_source(self):
        candidate = self._create_applicant(
            self.job_a,
            email='unique4@example.com',
            phone='4444444444',
            medium_id=self.medium_job_board.id,
            source_id=self.source_linkedin.id,
        )
        with self.assertRaises(ValidationError):
            candidate.write({'email_from': 'original@example.com'})

    def test_editing_to_duplicate_on_different_job_is_allowed(self):
        # self.original is on job_a; this candidate is on job_b, so
        # reusing the same email is allowed - different Job Position.
        candidate = self._create_applicant(
            self.job_b, email='unique5@example.com', phone='5555555555'
        )
        candidate.write({'email_from': 'original@example.com'})
        self.assertEqual(candidate.email_from, 'original@example.com')
        self.assertFalse(candidate.is_duplicate_application)

    def test_editing_to_duplicate_on_same_job_is_blocked(self):
        candidate = self._create_applicant(
            self.job_a, email='unique6@example.com', phone='6666666660'
        )
        with self.assertRaises(ValidationError):
            candidate.write({'email_from': 'original@example.com'})

    def test_write_on_unrelated_field_does_not_trigger_check(self):
        candidate = self._create_applicant(
            self.job_a, email='unrelated-write@example.com', phone='6666666666'
        )
        candidate.write({'partner_name': 'Renamed Candidate'})
        self.assertFalse(candidate.is_duplicate_application)

    def test_skips_check_while_ocr_extraction_pending(self):
        candidate = self._create_applicant(
            self.job_a, email='pending-ocr@example.com', phone='7777777777'
        )
        with patch.object(
            type(candidate),
            '_is_ocr_extraction_pending',
            return_value=True,
        ):
            candidate.with_context(website_id=1).write({
                'email_from': 'original@example.com'
            })
        self.assertFalse(candidate.is_duplicate_application)
