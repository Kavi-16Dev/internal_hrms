# -*- coding: utf-8 -*-
"""Schema-only repair for 19.0.3.27.16.

This migration deliberately performs only idempotent DDL before registry
post-migration code. It repairs columns that may be missing after a partial
upgrade without instantiating ORM records.
"""

def migrate(cr, version):
    cr.execute("""
        ALTER TABLE hr_recruitment_vendor
        ADD COLUMN IF NOT EXISTS contact_person varchar
    """)
    cr.execute("""
        ALTER TABLE hr_applicant
        ADD COLUMN IF NOT EXISTS kavi_salary_structure_history text
    """)
