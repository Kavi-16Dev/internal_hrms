# -*- coding: utf-8 -*-
"""Version 19.0.3.27.18 migration.

Salary Structure was deployed under two technical field names by different
versions of the ATS customization:

* ``offer_salary_structure`` - Html field (the field shown in newer forms)
* ``salary_structure`` - plain-text field (older deployments)

The custom Version History previously only recorded ``salary_structure``.
This migration seeds a field-specific baseline for existing applicants when
no Salary Structure history exists, so clicking Salary Structure immediately
shows the current value. Future changes are recorded by hr.applicant.write().
"""


def _column_exists(cr, table, column):
    cr.execute("""
        SELECT 1
          FROM information_schema.columns
         WHERE table_name = %s
           AND column_name = %s
         LIMIT 1
    """, (table, column))
    return bool(cr.fetchone())


def migrate(cr, version):
    table = 'hr_applicant'
    history_table = 'hr_applicant_version_history'

    has_offer = _column_exists(cr, table, 'offer_salary_structure')
    has_salary = _column_exists(cr, table, 'salary_structure')

    # Prefer the Html offer_salary_structure field when both are present.
    # It is the field used by the current ATS form and therefore exactly what
    # the user sees when opening Salary Structure History.
    if has_offer:
        cr.execute(f"""
            INSERT INTO {history_table}
                (applicant_id, field_name, field_label,
                 old_value, new_value, changed_by, changed_on)
            SELECT a.id,
                   'offer_salary_structure',
                   'Salary Structure',
                   '',
                   a.offer_salary_structure,
                   1,
                   NOW()
              FROM {table} a
             WHERE COALESCE(a.offer_salary_structure, '') <> ''
               AND NOT EXISTS (
                   SELECT 1
                     FROM {history_table} h
                    WHERE h.applicant_id = a.id
                      AND h.field_name IN ('offer_salary_structure', 'salary_structure')
               )
        """)
        return

    if has_salary:
        cr.execute(f"""
            INSERT INTO {history_table}
                (applicant_id, field_name, field_label,
                 old_value, new_value, changed_by, changed_on)
            SELECT a.id,
                   'salary_structure',
                   'Salary Structure',
                   '',
                   CASE
                       WHEN COALESCE(a.salary_structure, '') = '' THEN ''
                       ELSE '<p>' ||
                            replace(replace(replace(a.salary_structure,
                                '&', '&amp;'), '<', '&lt;'), '>', '&gt;') ||
                            '</p>'
                   END,
                   1,
                   NOW()
              FROM {table} a
             WHERE COALESCE(a.salary_structure, '') <> ''
               AND NOT EXISTS (
                   SELECT 1
                     FROM {history_table} h
                    WHERE h.applicant_id = a.id
                      AND h.field_name IN ('offer_salary_structure', 'salary_structure')
               )
        """)
