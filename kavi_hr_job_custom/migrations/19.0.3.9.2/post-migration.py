# -*- coding: utf-8 -*-
"""
post-migration script for 19.0.3.9.2.

BUG: "Key Roles and Responsibilities History" always shows "The key roles
and responsibilities were empty at the time." for its latest/current
revision, even on Job Positions where the field visibly holds real content
(e.g. a full bullet list under the "Offer Letter Components" tab) - while
"Budgeting Information History" correctly shows real text as soon as it's
edited and saved.

ROOT CAUSE (two combined issues, both now fixed going forward):

1) views/hr_job_views.xml: budgeting_information is rendered by THIS
   module's own view with options="{'collaborative': true}" - the option
   that makes the OdooEditor embed step-history markers into saved HTML,
   which handle_history_divergence()/the native html.field.history.mixin
   need to build a real diff. key_responsibilities is rendered by a
   DIFFERENT view (Studio/other, the "Offer Letter Components" page) that
   never had that option. Fixed by an xpath in hr_job_views.xml that
   patches the EXISTING field's widget options directly, without touching
   its page or creating any new field.

2) models/hr_job.py write(): key_responsibilities already held real
   content on many records BEFORE this module ever wired up native
   history tracking for it (unlike budgeting_information, which started
   genuinely empty under this module's tracking). The native mixin's
   patch chain for it was therefore never seeded with a baseline
   describing that pre-existing content, so every revision kept showing
   "empty" no matter how much real content the field held. write() now
   detects "real content, but no native-history entry yet" the moment the
   field is next written to, and clears its metadata first so that write
   becomes its first genuine tracked revision.

Fix (2) only takes effect the NEXT time each Job Position's
key_responsibilities is actually edited and saved - it does not retroactively
create a "before" snapshot for content nobody has touched since. This
migration does the equivalent one-time cleanup for every EXISTING Job
Position right now: any stale/incomplete html_field_history_metadata entry
for key_responsibilities is cleared (does NOT touch the field's actual
visible content, and does NOT touch hr.job.version.history), so the dialog
starts clean and the very next edit anyone makes to that field is captured
correctly - exactly the same safe, metadata-only pattern the 19.0.3.9.0
migration already used for the related "false" bug.
"""
from odoo import api, SUPERUSER_ID

JOB_NATIVE_HISTORY_FIELDS = ('budgeting_information', 'key_responsibilities')


def migrate(cr, version):
    env = api.Environment(cr, SUPERUSER_ID, {})
    _clear_stale_native_history(env['hr.job'], JOB_NATIVE_HISTORY_FIELDS)


def _clear_stale_native_history(model, field_names):
    records = model.sudo().search([])
    for record in records:
        metadata = dict(record.html_field_history_metadata or {})
        changed = False
        for fname in field_names:
            if fname not in record._fields:
                continue
            # Only clear fields that have NO recorded native-history entry
            # yet (the exact "real content, never actually tracked" gap
            # this fix addresses). Fields that already have a working
            # entry (e.g. budgeting_information, once edited) are left
            # completely untouched - this never discards real, already
            # -working history.
            if not metadata.get(fname):
                if metadata.pop(fname, None) is not None:
                    changed = True
        if changed:
            record.write({'html_field_history_metadata': metadata})
