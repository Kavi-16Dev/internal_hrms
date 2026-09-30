# -*- coding: utf-8 -*-
"""
post-migration script for 19.0.3.8.0.

BUG: clicking the native "Key Roles and Responsibilities History" (or
"Budgeting Information History" / "Salary Structure History" /
"Confidential Notes History") entry in the cog menu could raise

    IndexError: list assignment index out of range

from Odoo core (html_editor/models/diff_utils.py apply_patch, called via
html_field_history_mixin.py's html_field_history_get_content_at_revision).

Root cause: this module's own "Restore" button (action_restore_history in
hr_job_version_history_wizard.py / hr_applicant_version_history_wizard.py)
restores a field's value from our separate structured audit trail
(hr.job.version.history / hr.applicant.version.history) by writing a
plain HTML string directly - not through the live collaborative Html
editor. Odoo's native per-field history (`html_field_history_metadata`,
added by html.field.history.mixin) only knows how to replay patches that
were produced by that editor; once a field's content changes through any
other channel, those stored patches no longer match the field's actual
content, and replaying them to reconstruct an older revision walks past
the end of the (now differently-sized) content.

models/hr_job.py / models/hr_applicant.py now prevent this going forward
(_kavi_reset_native_html_history(), called right after every restore).
This migration is the one-time cleanup for records that were already
affected BEFORE that fix existed: it simply drops the stale per-field
entries from html_field_history_metadata, for every hr.job / hr.applicant
record that has any. This does NOT touch the fields' actual content
(Key Roles and Responsibilities, Budgeting Information, Salary
Structure, Confidential Notes all keep whatever text they currently
have) and does NOT touch hr.job.version.history / hr.applicant.version.
history (our own structured audit trail is untouched) - it only clears
the native mixin's now-invalid internal bookkeeping, so its "<Field>
History" dialog starts tracking fresh from here instead of crashing.
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
