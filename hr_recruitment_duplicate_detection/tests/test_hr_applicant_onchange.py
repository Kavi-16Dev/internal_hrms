# -*- coding: utf-8 -*-
from unittest.mock import patch

from .common import DuplicateDetectionCommon


class TestDuplicateFieldLabel(DuplicateDetectionCommon):

    def test_email_and_phone_both_matched(self):
        self.assertEqual(self.HrApplicant._duplicate_field_label(True, True), 'Email and Phone')

    def test_phone_only_matched(self):
        self.assertEqual(self.HrApplicant._duplicate_field_label(False, True), 'Phone number')

    def test_email_only_matched(self):
        self.assertEqual(self.HrApplicant._duplicate_field_label(True, False), 'Email address')

    def test_neither_matched_falls_back_to_email_label(self):
        self.assertEqual(self.HrApplicant._duplicate_field_label(False, False), 'Email address')


class TestOnchangeCheckDuplicateContact(DuplicateDetectionCommon):

    def setUp(self):
        super().setUp()
        self.original = self._create_applicant(self.job_a, email='original@example.com')

    def test_no_warning_when_no_duplicate(self):
        applicant = self.HrApplicant.new({
            'partner_name': 'New Candidate', 'job_id': self.job_a.id, 'email_from': 'unique@example.com',
        })
        result = applicant._onchange_check_duplicate_contact()
        self.assertIsNone(result)

    def test_warning_contains_only_duplicate_information(self):
        applicant = self.HrApplicant.with_context(website_id=1).new({
            'partner_name': 'New Candidate', 'job_id': self.job_a.id, 'email_from': 'original@example.com',
        })
        result = applicant._onchange_check_duplicate_contact()
        self.assertIsNotNone(result)
        self.assertEqual(
            result['warning']['message'],
            "An application already exists for this Email address for the position 'Odoo Developer'.",
        )
        self.assertNotIn('You can still save this record', result['warning']['message'])
        self.assertNotIn('flagged as a duplicate', result['warning']['message'])
        self.assertNotIn('Please use a different', result['warning']['message'])

    def test_phone_warning_contains_only_duplicate_information(self):
        phone_field = self.PHONE_FIELD
        if not phone_field:
            self.skipTest('No supported phone field exists on hr.applicant')
        applicant = self.HrApplicant.with_context(website_id=1).new({
            'partner_name': 'New Candidate', 'job_id': self.job_a.id, phone_field: '+91 9876543210',
        })
        self._create_applicant(self.job_a, email='different@example.com', phone='+919876543210')
        result = applicant._onchange_check_duplicate_contact()
        self.assertIsNotNone(result)
        self.assertEqual(
            result['warning']['message'],
            "An application already exists for this Phone number for the position 'Odoo Developer'.",
        )
        self.assertNotIn('You can still save this record', result['warning']['message'])
        self.assertNotIn('flagged as a duplicate', result['warning']['message'])

    def test_skips_when_ocr_extraction_pending(self):
        applicant = self.HrApplicant.with_context(website_id=1).new({
            'partner_name': 'New Candidate', 'job_id': self.job_a.id, 'email_from': 'original@example.com',
        })
        with patch.object(type(applicant), '_is_ocr_extraction_pending', return_value=True):
            result = applicant._onchange_check_duplicate_contact()
        self.assertIsNone(result)

    def test_warning_title(self):
        applicant = self.HrApplicant.with_context(website_id=1).new({
            'partner_name': 'New Candidate', 'job_id': self.job_a.id, 'email_from': 'original@example.com',
        })
        result = applicant._onchange_check_duplicate_contact()
        self.assertEqual(result['warning']['title'], 'Duplicate Application')
