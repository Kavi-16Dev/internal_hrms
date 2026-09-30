# -*- coding: utf-8 -*-
"""Pre-migration schema guard for 19.0.3.27.15."""

def migrate(cr, version):
    # These guards repair the two physical columns introduced by this module's
    # recent changes before any registry/post-migration ORM work can flush them.
    cr.execute("""
        ALTER TABLE hr_recruitment_vendor
        ADD COLUMN IF NOT EXISTS contact_person varchar
    """)
    cr.execute("""
        ALTER TABLE hr_applicant
        ADD COLUMN IF NOT EXISTS kavi_salary_structure_history text
    """)
