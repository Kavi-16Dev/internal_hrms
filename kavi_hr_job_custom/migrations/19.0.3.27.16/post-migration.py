# -*- coding: utf-8 -*-
"""Safe finalization for 19.0.3.27.16.

No ORM operations are performed here. The migration only backfills the Salary
Structure history mirror using SQL after the pre-migration has guaranteed the
physical columns exist. Contact Person is intentionally not backfilled here:
it is a display/cache field and any ORM recomputation can safely occur after
the registry is fully loaded.
"""

def migrate(cr, version):
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
