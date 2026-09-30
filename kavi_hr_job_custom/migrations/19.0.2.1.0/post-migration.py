# -*- coding: utf-8 -*-
"""
post-migration script for 19.0.2.1.0.

IMPORTANT: post_init_hook (see hooks.py) only ever runs on a fresh
*install* of the module - never on an *upgrade* of an already-installed
one. Since almost everyone hitting the "Version History doesn't work
for records that existed before this feature" issue is upgrading an
already-installed module, that hook alone was never going to backfill
anything for them. This migration script is the mechanism Odoo actually
runs during an upgrade: any file at migrations/<version>/post-migration.py
is executed automatically the moment the module is upgraded TO that
exact version number - which is why the version in __manifest__.py was
bumped to 19.0.2.1.0 to match this folder.

This does the exact same, safe, idempotent backfill as hooks.py and
the manual "Backfill Version History (Run Once)" menu item: it only
ever creates a baseline row for a Job Position/Applicant that currently
has zero Version History rows, and never duplicates one.
"""
from odoo import api, SUPERUSER_ID


def migrate(cr, version):
    env = api.Environment(cr, SUPERUSER_ID, {})
    _backfill_job_version_history(env)
    _backfill_applicant_version_history(env)


def _backfill_job_version_history(env):
    Job = env['hr.job'].sudo()
    History = env['hr.job.version.history'].sudo()

    jobs_without_history = Job.search([('job_version_history_ids', '=', False)])
    for job in jobs_without_history:
        History.create({
            'job_id': job.id,
            'field_name': '__baseline__',
            'field_label': 'Job Position Created',
            'old_value': '',
            'new_value': job.name or '',
        })


def _backfill_applicant_version_history(env):
    Applicant = env['hr.applicant'].sudo()
    History = env['hr.applicant.version.history'].sudo()

    applicants_without_history = Applicant.search([('applicant_version_history_ids', '=', False)])
    for applicant in applicants_without_history:
        History.create({
            'applicant_id': applicant.id,
            'field_name': '__baseline__',
            'field_label': 'Applicant Created',
            'old_value': '',
            'new_value': applicant.partner_name or applicant.display_name or '',
        })
