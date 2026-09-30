# -*- coding: utf-8 -*-

"""Pre-migration 19.0.3.27.12.

Create the native HTML mirror column before any post-migration code can read
hr.applicant.  IF NOT EXISTS makes this safe for databases that already have
the column.
"""

def migrate(cr, version):
    cr.execute("""
        ALTER TABLE hr_applicant
        ADD COLUMN IF NOT EXISTS kavi_salary_structure_history text
    """)
