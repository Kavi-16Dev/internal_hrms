# -*- coding: utf-8 -*-
"""Final schema-safe migration for 19.0.3.27.17.

No ORM reads/writes are performed here.  The important fix in this release
is in ``models/vendor.py``: ``contact_person`` is no longer stored in
``hr_recruitment_vendor`` and instead mirrors ``contact_person_id.name``.
This prevents registry flushes from issuing UPDATEs against a missing
``contact_person`` column."""

def migrate(cr, version):
    # Idempotent SQL-only backfill for Salary Structure history.
    cr.execute("""
        UPDATE hr_applicant
           SET kavi_salary_structure_history =
               CASE
                   WHEN salary_structure IS NULL OR salary_structure = ''
                       THEN NULL
                   ELSE '<p>' || replace(replace(replace(salary_structure, '&', '&amp;'), '<', '&lt;'), '>', '&gt;') || '</p>'
               END
         WHERE kavi_salary_structure_history IS NULL
           AND salary_structure IS NOT NULL
           AND salary_structure != ''
    """)
