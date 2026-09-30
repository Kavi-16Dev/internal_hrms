# -*- coding: utf-8 -*-
"""Pre-migration for 19.0.3.27.19.

Ensure the stable Salary Structure HTML mirror exists before the registry
upgrade. The mirror is the field used by Odoo's native html.field.history
mixin, regardless of whether the ATS exposes Salary Structure as
``offer_salary_structure`` (HTML) or ``salary_structure`` (plain text).
"""

def migrate(cr, version):
    cr.execute("""
        ALTER TABLE hr_applicant
        ADD COLUMN IF NOT EXISTS kavi_salary_structure_history text
    """)
