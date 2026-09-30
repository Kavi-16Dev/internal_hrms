# -*- coding: utf-8 -*-
"""Pre-migration guard for 19.0.3.27.17.

The Vendor Contact Person is now a non-stored computed/inverse field backed
by ``contact_person_id.name``.  No ``contact_person`` SQL column is required.
Keep the Salary Structure history column present on partially upgraded
databases because it remains a stored Html field."""

def migrate(cr, version):
    cr.execute("""
        ALTER TABLE hr_applicant
        ADD COLUMN IF NOT EXISTS kavi_salary_structure_history text
    """)
