# -*- coding: utf-8 -*-
from .common import DuplicateDetectionCommon


class TestFindDuplicateApplicants(DuplicateDetectionCommon):

    def setUp(self):
        super().setUp()
        if not self.PHONE_FIELD:
            self.skipTest('No phone-like field found on hr.applicant')

    def test_no_email_or_phone_returns_empty(self):
        applicant = self._create_applicant(self.job_a)
        matches, matched_email, matched_phone = applicant._find_duplicate_applicants()
        self.assertFalse(matches)
        self.assertFalse(matched_email)
        self.assertFalse(matched_phone)

    def test_matches_by_email_only(self):
        original = self._create_applicant(
            self.job_a, email='dup@example.com', phone='1111111111'
        )
        candidate = self.HrApplicant.new({
            'job_id': self.job_a.id,
            'email_from': 'DUP@example.com',
            self.PHONE_FIELD: '2222222222',
        })
        matches, matched_email, matched_phone = candidate._find_duplicate_applicants()
        self.assertEqual(matches, original)
        self.assertTrue(matched_email)
        self.assertFalse(matched_phone)

    def test_matches_by_phone_only(self):
        original = self._create_applicant(
            self.job_a, email='original@example.com', phone='9876543210'
        )
        candidate = self.HrApplicant.new({
            'job_id': self.job_a.id,
            'email_from': 'new@example.com',
            self.PHONE_FIELD: '(987) 654-3210',
        })
        matches, matched_email, matched_phone = candidate._find_duplicate_applicants()
        self.assertEqual(matches, original)
        self.assertFalse(matched_email)
        self.assertTrue(matched_phone)

    def test_matches_by_both_email_and_phone(self):
        original = self._create_applicant(
            self.job_a, email='dup@example.com', phone='9876543210'
        )
        candidate = self.HrApplicant.new({
            'job_id': self.job_a.id,
            'email_from': 'dup@example.com',
            self.PHONE_FIELD: '9876543210',
        })
        matches, matched_email, matched_phone = candidate._find_duplicate_applicants()
        self.assertEqual(matches, original)
        self.assertTrue(matched_email)
        self.assertTrue(matched_phone)

    def test_same_contact_on_different_job_is_not_duplicate(self):
        self._create_applicant(
            self.job_a, email='dup@example.com', phone='9876543210'
        )
        candidate = self.HrApplicant.new({
            'job_id': self.job_b.id,
            'email_from': 'dup@example.com',
            self.PHONE_FIELD: '9876543210',
        })
        matches, matched_email, matched_phone = candidate._find_duplicate_applicants()
        self.assertFalse(matches)
        self.assertFalse(matched_email)
        self.assertFalse(matched_phone)

    def test_same_contact_on_same_job_is_duplicate(self):
        original = self._create_applicant(
            self.job_a, email='dup@example.com', phone='9876543210'
        )
        candidate = self.HrApplicant.new({
            'job_id': self.job_a.id,
            'email_from': 'dup@example.com',
            self.PHONE_FIELD: '9876543210',
        })
        matches, matched_email, matched_phone = candidate._find_duplicate_applicants()
        self.assertEqual(matches, original)
        self.assertTrue(matched_email)
        self.assertTrue(matched_phone)

    def test_no_job_id_returns_empty(self):
        self._create_applicant(
            self.job_a, email='dup@example.com', phone='9876543210'
        )
        candidate = self.HrApplicant.new({
            'email_from': 'dup@example.com',
            self.PHONE_FIELD: '9876543210',
        })
        matches, matched_email, matched_phone = candidate._find_duplicate_applicants()
        self.assertFalse(matches)
        self.assertFalse(matched_email)
        self.assertFalse(matched_phone)

    def test_excludes_self(self):
        applicant = self._create_applicant(
            self.job_a, email='solo@example.com', phone='1234567890'
        )
        matches, matched_email, matched_phone = applicant._find_duplicate_applicants()
        self.assertFalse(matches)

    def test_multiple_existing_duplicates_all_returned(self):
        first = self._create_applicant(
            self.job_a, email='multi@example.com', phone='1111111111'
        )
        second = self._create_applicant(
            self.job_a, email='multi@example.com', phone='2222222222'
        )
        candidate = self.HrApplicant.new({
            'job_id': self.job_a.id,
            'email_from': 'multi@example.com',
            self.PHONE_FIELD: '3333333333',
        })
        matches, matched_email, matched_phone = candidate._find_duplicate_applicants()
        self.assertEqual(matches, first | second)
        self.assertTrue(matched_email)
        self.assertFalse(matched_phone)

    def test_phone_normalization_matches_different_formats(self):
        original = self._create_applicant(
            self.job_a, phone='9876543210'
        )
        candidate = self.HrApplicant.new({
            'job_id': self.job_a.id,
            self.PHONE_FIELD: '(987) 654-3210',
        })
        matches, matched_email, matched_phone = candidate._find_duplicate_applicants()
        self.assertEqual(matches, original)
        self.assertTrue(matched_phone)
