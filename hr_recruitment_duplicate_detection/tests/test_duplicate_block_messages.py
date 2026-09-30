# -*- coding: utf-8 -*-
from odoo.exceptions import ValidationError
from odoo.tests.common import TransactionCase


class TestDuplicateBlockMessages(TransactionCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.job = cls.env['hr.job'].create({'name': 'Odoo Consultant'})
        cls.Applicant = cls.env['hr.applicant']
        cls.phone_field = next(
            (field for field in ('partner_phone', 'mobile', 'partner_mobile')
             if field in cls.Applicant._fields),
            None,
        )

    def _create(self, email=None, phone=None):
        vals = {
            'partner_name': 'Existing Candidate',
            'job_id': self.job.id,
        }
        if email is not None:
            vals['email_from'] = email
        if phone is not None and self.phone_field:
            vals[self.phone_field] = phone
        return self.Applicant.create(vals)

    def test_email_only_message(self):
        self._create(email='duplicate@example.com', phone='9999999999')
        vals = {
            'partner_name': 'New Candidate',
            'job_id': self.job.id,
            'email_from': 'duplicate@example.com',
        }
        if self.phone_field:
            vals[self.phone_field] = '8888888888'
        with self.assertRaises(ValidationError) as error:
            self.Applicant.create(vals)
        self.assertEqual(
            str(error.exception),
            "Duplicate application blocked: An application already exists "
            "for the position 'Odoo Consultant' with the same email address.",
        )

    def test_phone_only_message(self):
        self._create(email='existing@example.com', phone='9999999999')
        vals = {
            'partner_name': 'New Candidate',
            'job_id': self.job.id,
            'email_from': 'new@example.com',
        }
        if self.phone_field:
            vals[self.phone_field] = '9999999999'
        else:
            self.skipTest('This Odoo installation has no supported applicant phone field.')
        with self.assertRaises(ValidationError) as error:
            self.Applicant.create(vals)
        self.assertEqual(
            str(error.exception),
            "Duplicate application blocked: An application already exists "
            "for the position 'Odoo Consultant' with the same Phone Number.",
        )

    def test_email_and_phone_message(self):
        self._create(email='both@example.com', phone='9999999999')
        vals = {
            'partner_name': 'New Candidate',
            'job_id': self.job.id,
            'email_from': 'both@example.com',
        }
        if self.phone_field:
            vals[self.phone_field] = '9999999999'
        else:
            self.skipTest('This Odoo installation has no supported applicant phone field.')
        with self.assertRaises(ValidationError) as error:
            self.Applicant.create(vals)
        self.assertEqual(
            str(error.exception),
            "Duplicate application blocked: An application already exists "
            "for the position 'Odoo Consultant' with the same email address and Phone number.",
        )
