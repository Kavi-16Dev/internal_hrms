# -*- coding: utf-8 -*-
"""Post-migration for 19.0.3.27.19.

Fix the Salary Structure native Version History chain.

The previous migration populated the hidden mirror with SQL but did not
synchronize it with the current ATS ``offer_salary_structure`` field.
Moreover, if the mirror had previously been initialized from the wrong
technical field, its native history could point at a different value.

This migration:
1. Detects the currently deployed Salary Structure column(s).
2. Synchronizes the hidden HTML mirror to the current business value.
3. Clears ONLY the native mirror history when the mirror value had to be
   corrected, because revisions generated against the old mirror content are
   no longer valid.
4. Does not create a fake history revision. The first real Salary Structure
   edit after this upgrade creates the revision, exactly like Confidential
   Notes.
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


def _html_escape_text_sql(column_sql):
    return (
        "'<p>' || "
        "replace(replace(replace(COALESCE(" + column_sql + ", ''), "
        "'&', '&amp;'), '<', '&lt;'), '>', '&gt;') || "
        "'</p>'"
    )


def migrate(cr, version):
    table = 'hr_applicant'

    has_offer = _column_exists(cr, table, 'offer_salary_structure')
    has_salary = _column_exists(cr, table, 'salary_structure')
    if not has_offer and not has_salary:
        return

    # Current ATS deployments use offer_salary_structure. If it is empty,
    # fall back to the legacy salary_structure column when that column exists.
    if has_offer and has_salary:
        desired_sql = """
            CASE
                WHEN COALESCE(offer_salary_structure, '') <> ''
                    THEN offer_salary_structure
                WHEN COALESCE(salary_structure, '') <> ''
                    THEN {salary_html}
                ELSE ''
            END
        """.format(salary_html=_html_escape_text_sql('salary_structure'))
    elif has_offer:
        desired_sql = """
            COALESCE(offer_salary_structure, '')
        """
    else:
        desired_sql = _html_escape_text_sql('salary_structure')

    # Synchronize the hidden mirror to the real Salary Structure field.
    cr.execute("""
        UPDATE hr_applicant
           SET kavi_salary_structure_history = {desired}
    """.format(desired=desired_sql))

    # When offer_salary_structure is present it is the field displayed in the
    # current Applicant form. Any older mirror revisions may have been built
    # from the legacy salary_structure value, so they are not safe to expose
    # through the native HistoryDialog. Clear ONLY the Salary Structure mirror
    # history; Confidential Notes and all other native HTML histories remain.
    if has_offer:
        cr.execute("""
            UPDATE hr_applicant
               SET html_field_history =
                   COALESCE(html_field_history, jsonb_build_object())
                   - 'kavi_salary_structure_history'
             WHERE COALESCE(kavi_salary_structure_history, '') <> ''
        """)

    # The structured history table is intentionally left untouched. It is
    # the audit trail and may contain useful historical entries.
