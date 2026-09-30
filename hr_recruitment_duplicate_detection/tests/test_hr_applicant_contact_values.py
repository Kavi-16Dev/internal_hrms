# -*- coding: utf-8 -*-
from .common import DuplicateDetectionCommon


class TestNormalizePhone(DuplicateDetectionCommon):
    """_normalize_phone() is a @staticmethod - test it directly without
    needing any record."""

    def test_strips_spaces_dashes_dots_and_parentheses(self):
        self.assertEqual(
            self.HrApplicant._normalize_phone('+91 98765-43210'),
            '919876543210',
        )
        self.assertEqual(
            self.HrApplicant._normalize_phone('(987) 654.3210'),
            '9876543210',
        )

    def test_strips_leading_plus_only(self):
        self.assertEqual(self.HrApplicant._normalize_phone('+919876543210'), '919876543210')

    def test_plain_digits_unchanged(self):
        self.assertEqual(self.HrApplicant._normalize_phone('9876543210'), '9876543210')

    def test_different_formats_normalize_to_same_value(self):
        a = self.HrApplicant._normalize_phone('+91 98765-43210')
        b = self.HrApplicant._normalize_phone('919876543210')
        self.assertEqual(a, b)

    def test_empty_and_false_return_empty_string(self):
        self.assertEqual(self.HrApplicant._normalize_phone(''), '')
        self.assertEqual(self.HrApplicant._normalize_phone(False), '')

    def test_internal_plus_is_only_stripped_at_start(self):
        # lstrip('+') only removes leading '+' characters - documenting
        # actual behaviour of the current implementation.
        self.assertEqual(self.HrApplicant._normalize_phone('91+876543210'), '91+876543210')


class TestGetContactValues(DuplicateDetectionCommon):

    def setUp(self):
        super().setUp()
        if not self.PHONE_FIELD:
            self.skipTest('No phone-like field (partner_phone/mobile/partner_mobile) found on hr.applicant')

    def test_email_is_lowercased_and_stripped(self):
        applicant = self._create_applicant(self.job_a, email='  Jane.Doe@EXAMPLE.com  ')
        email, _phone = applicant._get_contact_values()
        self.assertEqual(email, 'jane.doe@example.com')

    def test_phone_is_normalized(self):
        applicant = self._create_applicant(self.job_a, phone='+91 98765-43210')
        _email, phone = applicant._get_contact_values()
        self.assertEqual(phone, '919876543210')

    def test_empty_when_no_email_or_phone_set(self):
        applicant = self._create_applicant(self.job_a)
        email, phone = applicant._get_contact_values()
        self.assertEqual((email, phone), ('', ''))

    def test_both_email_and_phone_returned_together(self):
        applicant = self._create_applicant(self.job_a, email='a@example.com', phone='9876543210')
        email, phone = applicant._get_contact_values()
        self.assertEqual(email, 'a@example.com')
        self.assertEqual(phone, '9876543210')
