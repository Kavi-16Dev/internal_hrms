# -*- coding: utf-8 -*-
from odoo.tests.common import TransactionCase


class DuplicateDetectionCommon(TransactionCase):
    """Shared fixtures for hr_recruitment_duplicate_detection tests.

    Two Job Positions (so "scoped to the same job" rules are always
    exercisable), a small set of reusable UTM Source/Medium records
    covering each `_detect_source_type()` bucket (job board, email,
    portal-by-keyword, and a neutral UTM pair), and PHONE_FIELD -
    whichever of partner_phone/mobile/partner_mobile actually exists on
    this hr.applicant (per _get_contact_values()'s own field-existence
    check), so these tests work regardless of which phone field name
    this Odoo 19 install/other installed modules ended up using.
    """

    @classmethod
    def setUpClass(cls):
        super().setUpClass()

        cls.HrApplicant = cls.env['hr.applicant']
        cls.HrJob = cls.env['hr.job']
        cls.UtmSource = cls.env['utm.source']
        cls.UtmMedium = cls.env['utm.medium']

        cls.job_a = cls.HrJob.create({'name': 'Odoo Developer'})
        cls.job_b = cls.HrJob.create({'name': 'Business Analyst'})

        # Whichever phone-like field _get_contact_values() will actually
        # find first on this model - see models/hr_applicant.py.
        cls.PHONE_FIELD = next(
            (f for f in ('partner_phone', 'mobile', 'partner_mobile') if f in cls.HrApplicant._fields),
            None,
        )

        # --- UTM fixtures for _detect_source_type() buckets ---
        cls.medium_job_board = cls._get_or_create_medium('Job Board')
        cls.source_linkedin = cls._get_or_create_source('LinkedIn Easy Apply')

        cls.medium_email = cls._get_or_create_medium('Email')
        cls.source_recruitment_inbox = cls._get_or_create_source('Recruitment Inbox')

        cls.medium_website = cls._get_or_create_medium('Website')
        cls.source_careers_page = cls._get_or_create_source('Careers Page')

        cls.medium_other = cls._get_or_create_medium('Referral Program')
        cls.source_other = cls._get_or_create_source('Employee Referral')

    @classmethod
    def _get_or_create_source(cls, name):
        return cls.UtmSource.search([('name', '=', name)], limit=1) or cls.UtmSource.create({'name': name})

    @classmethod
    def _get_or_create_medium(cls, name):
        return cls.UtmMedium.search([('name', '=', name)], limit=1) or cls.UtmMedium.create({'name': name})

    @classmethod
    def _make_applicant_vals(cls, job, email=None, phone=None, **extra):
        vals = {'partner_name': 'Candidate', 'job_id': job.id}
        if email is not None:
            vals['email_from'] = email
        if phone is not None and cls.PHONE_FIELD:
            vals[cls.PHONE_FIELD] = phone
        vals.update(extra)
        return vals

    @classmethod
    def _create_applicant(cls, job, email=None, phone=None, **extra):
        return cls.HrApplicant.create(cls._make_applicant_vals(job, email, phone, **extra))
