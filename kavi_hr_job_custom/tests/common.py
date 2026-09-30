# -*- coding: utf-8 -*-
from odoo.tests.common import TransactionCase


class KaviHrJobCustomCommon(TransactionCase):
    """Shared fixtures for kavi_hr_job_custom tests.

    Kept intentionally simple/reusable: a Job Position, an Applicant on
    that job, a Recruitment Manager user, and the two hr.job.tracked.field
    records that data/hr_job_tracked_field_data.xml installs (referenced
    directly instead of recreated, so tests also verify that data file is
    loaded correctly).
    """

    @classmethod
    def setUpClass(cls):
        super().setUpClass()

        cls.HrJob = cls.env['hr.job']
        cls.HrApplicant = cls.env['hr.applicant']
        cls.JobHistory = cls.env['hr.job.version.history']
        cls.ApplicantHistory = cls.env['hr.applicant.version.history']
        cls.TrackedField = cls.env['hr.job.tracked.field']
        cls.ResumeLine = cls.env['hr.applicant.resume.line']

        cls.tracked_budgeting = cls.env.ref(
            'kavi_hr_job_custom.tracked_field_budgeting_information')
        cls.tracked_key_resp = cls.env.ref(
            'kavi_hr_job_custom.tracked_field_key_responsibilities')

        cls.manager_user = cls._create_user(
            'kavi_manager', ['hr_recruitment.group_hr_recruitment_manager'])

        cls.job = cls.HrJob.with_user(cls.manager_user).create({
            'name': 'Senior Odoo Developer',
        })
        cls.applicant = cls.HrApplicant.with_user(cls.manager_user).create({
            'partner_name': 'Jane Candidate',
            'job_id': cls.job.id,
        })

    @classmethod
    def _create_user(cls, login, group_xmlids):
        groups = cls.env['res.groups']
        for xmlid in group_xmlids:
            groups |= cls.env.ref(xmlid)
        return cls.env['res.users'].with_context(no_reset_password=True).create({
            'name': login,
            'login': login,
            'email': '%s@example.com' % login,
            'group_ids': [(6, 0, groups.ids)],
        })
