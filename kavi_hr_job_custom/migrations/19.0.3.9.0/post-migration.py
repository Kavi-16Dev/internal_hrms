# -*- coding: utf-8 -*-
"""
post-migration script for 19.0.3.9.0.

BUG: "Key Roles and Responsibilities History" no longer crashed (fixed in
19.0.3.8.x), but its oldest timeline entry displayed the literal text
"false" instead of a real previous value - unlike "Budgeting Information
History", which only ever shows real content. Same underlying field,
just reused as requested - not a new one.

ROOT CAUSE: an Html field that has never been written through the ORM
is the Python boolean False at the ORM level, not ''. key_responsibilities
pre-existed this module (and this module's native html.field.history.mixin
wiring for it) with real content already on some records, populated
through some path that never actually went through write() with that
field in vals (e.g. directly in a data/demo file, or a raw SQL/pre-existing
column). The FIRST time write() ran with key_responsibilities in vals
after native history tracking was wired up, models/hr_job.py's write()
asked the mixin to diff the field's "before" value - which could still be
that raw False - against the new content. False got stored straight into
the patch chain and the History dialog rendered it as "false".
models/hr_job.py (and hr_applicant.py) now prevent this going forward by
normalizing a still-False native-history field to '' - and dropping any
already-bogus metadata for it - right before the mixin ever diffs it.

This migration is the one-time repair for records already affected:
1) Any of the four native-history Html fields still storing the raw
   boolean False gets normalized to '' (does not touch fields that
   already hold real content - False is falsy but '' is also falsy, and
   dict.pop()/an ORM write of '' is a safe no-op either way).
2) Any of those fields' now-untrustworthy entries in
   html_field_history_metadata are dropped, so the "<Field> History"
   dialog starts tracking fresh from the record's current, real content -
   the same clean starting point a field that never had this bug (like
   Budgeting Information) already has.

This does NOT touch the fields' actual visible content on any record,
and does NOT touch hr.job.version.history / hr.applicant.version.history
(this module's own structured audit trail is untouched either).
"""
from odoo import api, SUPERUSER_ID

JOB_NATIVE_HISTORY_FIELDS = ('budgeting_information', 'key_responsibilities')
APPLICANT_NATIVE_HISTORY_FIELDS = ('salary_structure', 'confidential_notes')


def migrate(cr, version):
    env = api.Environment(cr, SUPERUSER_ID, {})
    _repair_native_html_history(env['hr.job'], JOB_NATIVE_HISTORY_FIELDS)
    _repair_native_html_history(env['hr.applicant'], APPLICANT_NATIVE_HISTORY_FIELDS)


def _repair_native_html_history(model, field_names):
    records = model.sudo().search([])
    for record in records:
        # 1) Normalize any still-unset (raw boolean False) native-history
        #    field to a real empty string, so it can never again be
        #    mistaken for "real" content by the diffing mixin.
        normalize_vals = {
            fname: '' for fname in field_names
            if fname in record._fields and record[fname] is False
        }
        if normalize_vals:
            record.write(normalize_vals)

        # 2) Drop any existing entry for these fields from
        #    html_field_history_metadata, regardless of whether the field
        #    itself needed normalizing above. The corruption happened at
        #    a past write - the field can easily hold real, correct
        #    content today while its stored patch CHAIN still starts
        #    from that old bogus False baseline (exactly the case in the
        #    bug report: current content is fine, but the oldest History
        #    timeline entry still showed "false"). Clearing it lets the
        #    native History dialog start tracking fresh from the
        #    record's current, real content - the same clean starting
        #    point a field that never had this bug (like Budgeting
        #    Information) already has.
        metadata = dict(record.html_field_history_metadata or {})
        changed = False
        for fname in field_names:
            if fname in record._fields and metadata.pop(fname, None) is not None:
                changed = True
        if changed:
            record.write({'html_field_history_metadata': metadata})
