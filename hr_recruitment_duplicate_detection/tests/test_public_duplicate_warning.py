from odoo.tests import TransactionCase

from odoo.addons.hr_recruitment_duplicate_detection.controllers.main import WebsiteHrRecruitmentDuplicate


class TestPublicDuplicateWarning(TransactionCase):
    """Verify the exact Email/Phone-only public warning contract."""

    def test_only_email_duplicate_uses_dynamic_job_name(self):
        message = WebsiteHrRecruitmentDuplicate._duplicate_warning_message(
            'Odoo Consultant', True, False
        )
        self.assertEqual(
            message,
            "An application already exists for the position 'Odoo Consultant' "
            "with the same email address.",
        )
        self.assertNotIn('Name', message)

    def test_only_phone_duplicate_uses_dynamic_job_name(self):
        message = WebsiteHrRecruitmentDuplicate._duplicate_warning_message(
            'Python Developer', False, True
        )
        self.assertEqual(
            message,
            "An application already exists for the position 'Python Developer' "
            "with the same Phone Number.",
        )
        self.assertNotIn('Name', message)

    def test_email_and_phone_duplicate_uses_dynamic_job_name(self):
        message = WebsiteHrRecruitmentDuplicate._duplicate_warning_message(
            'HR Manager', True, True
        )
        self.assertEqual(
            message,
            "An application already exists for the position 'HR Manager' "
            "with the same email address and Phone number.",
        )
        self.assertNotIn('Name', message)

    def test_job_name_is_not_hardcoded(self):
        for job_name in ('Odoo Consultant', 'Python Developer', 'HR Manager'):
            message = WebsiteHrRecruitmentDuplicate._duplicate_warning_message(
                job_name, True, True
            )
            self.assertIn(job_name, message)
            if job_name != 'Odoo Consultant':
                self.assertNotIn('Odoo Consultant', message)

    def test_no_duplicate(self):
        self.assertIsNone(
            WebsiteHrRecruitmentDuplicate._duplicate_warning_message(
                'Odoo Consultant', False, False
            )
        )

    def test_warning_message_has_no_extra_sentence(self):
        message = WebsiteHrRecruitmentDuplicate._duplicate_warning_message(
            'Odoo Consultant', True, True
        )
        self.assertNotIn('Please use a different Email and Phone', message)
        self.assertNotIn('Please use a different Email', message)
        self.assertNotIn('Please use a different Phone', message)

    def test_missing_job_name_returns_no_warning(self):
        self.assertIsNone(
            WebsiteHrRecruitmentDuplicate._duplicate_warning_message('', True, True)
        )
