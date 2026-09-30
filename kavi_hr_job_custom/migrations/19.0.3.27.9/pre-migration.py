# -*- coding: utf-8 -*-
"""Pre-migration for 19.0.3.27.9.

The Salary Structure HTML-history mirror was introduced in this release.
Create its physical PostgreSQL column before the 27.9 post-migration touches
hr.applicant, including on databases where a previous partial upgrade left
the ORM field definition out of sync with PostgreSQL.
"""

def migrate(cr, version):
    cr.execute(
        """
        ALTER TABLE hr_applicant
        ADD COLUMN IF NOT EXISTS kavi_salary_structure_history text
        """
    )
