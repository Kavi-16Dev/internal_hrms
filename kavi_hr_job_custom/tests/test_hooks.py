# -*- coding: utf-8 -*-
from odoo import _

from odoo.addons.kavi_hr_job_custom.hooks import post_init_hook

from .common import KaviHrJobCustomCommon


class TestPostInitHook(KaviHrJobCustomCommon):

    def test_backfill_creates_baseline_for_job_missing_history(self):
        self.JobHistory.search([('job_id', '=', self.job.id)]).unlink()
        self.assertFalse(self.JobHistory.search([('job_id', '=', self.job.id)]))

        post_init_hook(self.env)

        rows = self.JobHistory.search([('job_id', '=', self.job.id)])
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows.field_name, '__baseline__')
        self.assertEqual(rows.new_value, self.job.name)

    def test_backfill_creates_baseline_for_applicant_missing_history(self):
        self.ApplicantHistory.search([('applicant_id', '=', self.applicant.id)]).unlink()

        post_init_hook(self.env)

        rows = self.ApplicantHistory.search([('applicant_id', '=', self.applicant.id)])
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows.field_name, '__baseline__')

    def test_backfill_does_not_duplicate_existing_history(self):
        # self.job already has its baseline row from create().
        count_before = self.JobHistory.search_count([('job_id', '=', self.job.id)])
        post_init_hook(self.env)
        count_after = self.JobHistory.search_count([('job_id', '=', self.job.id)])
        self.assertEqual(count_before, count_after)
