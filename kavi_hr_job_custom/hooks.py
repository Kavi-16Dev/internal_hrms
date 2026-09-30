# -*- coding: utf-8 -*-
"""
post_init_hook: guarantees every Job Position (hr.job) and every
Applicant (hr.applicant) that already exists in the database has at
least one Version History row.

Why this exists
----------------
Version History is, by nature, a CHANGE log: a row only gets created
when a tracked field is actually edited and saved (see write() in
models/hr_job.py and models/hr_applicant.py). That is exactly how
standard Odoo field tracking works too - nothing shows in the chatter
for a field that was never touched.

That is correct behaviour for changes made *after* this feature exists,
but it means every record that existed *before* you installed/upgraded
to this version of the module - and hasn't been edited since - still
has zero rows, so clicking "Version History" on it correctly reports
"No Version History Yet" over and over. Since a user shouldn't have to
manually edit every single Job Position / Applicant just to make the
button "work", this hook runs once per install/upgrade and creates one
baseline row for every record that doesn't already have history, so
"Version History" opens the same detail form you already see working
correctly on records you've edited, everywhere else too.

Going forward, create() on hr.job / hr.applicant (see models/hr_job.py
and models/hr_applicant.py) does the same thing for every NEW record,
so this backfill is only ever needed once for records created before
this module version.
"""
from odoo import _


def post_init_hook(env):
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
            'field_label': _('Job Position Created'),
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
            'field_label': _('Applicant Created'),
            'old_value': '',
            'new_value': applicant.partner_name or applicant.display_name or '',
        })
