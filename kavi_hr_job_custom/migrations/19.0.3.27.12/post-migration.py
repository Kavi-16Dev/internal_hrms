# -*- coding: utf-8 -*-

"""Post-migration 19.0.3.27.12.

Initialize the hidden HTML mirror directly in SQL.  This avoids ORM searches
while the registry is being upgraded and is safe on partially upgraded DBs.
The value is deliberately plain text wrapped as minimal HTML; the native HTML
history mechanism will create revisions for subsequent writes.
"""

def migrate(cr, version):
    cr.execute("""
        ALTER TABLE hr_applicant
        ADD COLUMN IF NOT EXISTS kavi_salary_structure_history text
    """)
    cr.execute("""
        UPDATE hr_applicant
           SET kavi_salary_structure_history =
               CASE
                   WHEN salary_structure IS NULL OR salary_structure = ''
                       THEN NULL
                   ELSE '<p>' || replace(replace(replace(salary_structure, '&', '&amp;'), '<', '&lt;'), '>', '&gt;') || '</p>'
               END
         WHERE kavi_salary_structure_history IS NULL
    """)
