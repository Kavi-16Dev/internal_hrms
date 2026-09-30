# -*- coding: utf-8 -*-
from unittest.mock import patch

from .common import DuplicateDetectionCommon


class TestIsOcrDigitizedRecord(DuplicateDetectionCommon):

    def test_false_when_extract_state_field_absent(self):
        # On installs without the Resume OCR/"Digitize Document" pipeline
        # (extract_state not a real field on hr.applicant), this must
        # simply be False rather than raising.
        applicant = self._create_applicant(self.job_a)
        if 'extract_state' in applicant._fields:
            self.skipTest('extract_state is present on this install; not exercising the absent-field path')
        self.assertFalse(applicant._is_ocr_digitized_record())

    def test_is_ocr_extraction_pending_false_when_field_absent(self):
        applicant = self._create_applicant(self.job_a)
        if 'extract_state' in applicant._fields:
            self.skipTest('extract_state is present on this install; not exercising the absent-field path')
        self.assertFalse(applicant._is_ocr_extraction_pending())


class TestDetectSourceType(DuplicateDetectionCommon):

    def test_job_board_keyword_via_medium(self):
        applicant = self._create_applicant(
            self.job_a, medium_id=self.medium_job_board.id, source_id=self.source_linkedin.id)
        self.assertEqual(applicant._detect_source_type(), 'job_board')

    def test_job_board_keyword_via_source_only(self):
        applicant = self._create_applicant(self.job_a, source_id=self.source_linkedin.id)
        self.assertEqual(applicant._detect_source_type(), 'job_board')

    def test_email_keyword_via_medium(self):
        applicant = self._create_applicant(
            self.job_a, medium_id=self.medium_email.id, source_id=self.source_recruitment_inbox.id)
        self.assertEqual(applicant._detect_source_type(), 'email')

    def test_portal_keyword_via_medium(self):
        applicant = self._create_applicant(
            self.job_a, medium_id=self.medium_website.id, source_id=self.source_careers_page.id)
        self.assertEqual(applicant._detect_source_type(), 'portal')

    def test_portal_keyword_via_source_career(self):
        applicant = self._create_applicant(self.job_a, source_id=self.source_careers_page.id)
        self.assertEqual(applicant._detect_source_type(), 'portal')

    def test_other_when_no_keyword_and_no_utm_set(self):
        applicant = self._create_applicant(self.job_a)
        self.assertEqual(applicant._detect_source_type(), 'other')

    def test_other_when_utm_present_but_no_keyword_matches(self):
        applicant = self._create_applicant(
            self.job_a, medium_id=self.medium_other.id, source_id=self.source_other.id)
        self.assertEqual(applicant._detect_source_type(), 'other')

    def test_website_id_context_forces_portal_even_without_utm(self):
        applicant = self._create_applicant(self.job_a)
        self.assertEqual(
            applicant.with_context(website_id=1)._detect_source_type(), 'portal')

    def test_website_id_context_forces_portal_even_with_job_board_utm(self):
        # The context signal (public Apply form) is authoritative and
        # wins even if UTM Source/Medium happen to look like a job board -
        # matches the documented "cannot be bypassed by missing UTM
        # configuration" guarantee in the other direction too.
        applicant = self._create_applicant(
            self.job_a, medium_id=self.medium_job_board.id, source_id=self.source_linkedin.id)
        self.assertEqual(
            applicant.with_context(website_id=1)._detect_source_type(), 'portal')

    def test_ocr_digitized_record_is_always_email_ignoring_keywords(self):
        applicant = self._create_applicant(
            self.job_a, medium_id=self.medium_website.id, source_id=self.source_careers_page.id)
        with patch.object(type(applicant), '_is_ocr_digitized_record', return_value=True):
            self.assertEqual(applicant._detect_source_type(), 'email')

    def test_ocr_digitized_record_wins_over_website_id_context(self):
        # This is the critical guarantee from the docstring: a digitized/
        # OCR record must NEVER classify as 'portal' (which would make
        # it eligible for the hard block), even if it somehow also
        # carries a website_id in context.
        applicant = self._create_applicant(self.job_a)
        with patch.object(type(applicant), '_is_ocr_digitized_record', return_value=True):
            self.assertEqual(
                applicant.with_context(website_id=1)._detect_source_type(), 'email')

    def test_application_source_type_field_is_removed(self):
        applicant = self._create_applicant(self.job_a)
        self.assertNotIn('application_source_type', applicant._fields)

