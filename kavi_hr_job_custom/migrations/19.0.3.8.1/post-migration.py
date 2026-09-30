# -*- coding: utf-8 -*-
"""
post-migration script for 19.0.3.8.1.

WHY THIS FOLDER EXISTS SEPARATELY FROM 19.0.3.8.0
---------------------------------------------------
migrations/19.0.3.8.0/post-migration.py already contains this exact
cleanup, and models/hr_job.py / models/hr_applicant.py already prevent
the corruption from happening again going forward. In theory that
should have been enough.

In practice, Odoo only runs a migrations/<version>/post-migration.py
script when the module's version *currently recorded in
ir_module_module* is strictly lower than <version>. If this module was
ever installed/upgraded before with its manifest version already equal
to (or higher than) 19.0.3.8.0 - for example, an earlier delivery of
this same fix that never got exercised, or a manual DB edit - then
re-running `-u kavi_hr_job_custom` with the 19.0.3.8.0 code again does
NOT re-trigger that script, and any Job Position / Applicant whose
html_field_history_metadata was already corrupted before this fix
existed keeps crashing "Key Roles and Responsibilities History" (or
Budgeting Information / Salary Structure / Confidential Notes) with

    IndexError: list assignment index out of range

forever, because the one-time cleanup that would have fixed it never
actually ran on that database.

Bumping the version to 19.0.3.8.1 and duplicating the (idempotent,
side-effect-free-when-nothing-is-stale) cleanup here guarantees it runs
at least once more on this upgrade, regardless of what version was
previously recorded - closing that gap for good. It's safe to run even
if 19.0.3.8.0's script already ran successfully: pop()-ing a key that
isn't there is a no-op, so already-clean records are simply skipped.

hr_job.py / hr_applicant.py also now defensively self-heal any future
occurrence of this at the moment the History dialog is opened (see
html_field_history_get_content_at_revision() overrides), so this
should genuinely be the last time a stale-history record needs a
migration to fix it.
"""
from odoo import api, SUPERUSER_ID

JOB_NATIVE_HISTORY_FIELDS = ('budgeting_information', 'key_responsibilities')
APPLICANT_NATIVE_HISTORY_FIELDS = ('salary_structure', 'confidential_notes')


def migrate(cr, version):
    env = api.Environment(cr, SUPERUSER_ID, {})
    _reset_native_html_history(env['hr.job'], JOB_NATIVE_HISTORY_FIELDS)
    _reset_native_html_history(env['hr.applicant'], APPLICANT_NATIVE_HISTORY_FIELDS)


def _reset_native_html_history(model, field_names):
    # Plain search([]) rather than a domain on html_field_history_metadata:
    # it's a Json field, and not every Odoo/PostgreSQL version supports
    # useful domain operators on Json columns, so this stays simple and
    # correct rather than relying on that.
    records = model.sudo().search([])
    for record in records:
        metadata = dict(record.html_field_history_metadata or {})
        changed = False
        for fname in field_names:
            if metadata.pop(fname, None) is not None:
                changed = True
        if changed:
            record.write({'html_field_history_metadata': metadata})
