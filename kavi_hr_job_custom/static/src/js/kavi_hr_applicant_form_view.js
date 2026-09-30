/** @odoo-module **/

import { _t } from "@web/core/l10n/translation";
import { registerHtmlFieldHistoryFormView } from "./kavi_html_field_history";

/**
 * hr.applicant form. Salary Structure is resolved at runtime because the
 * ATS customization has used both `salary_structure` and
 * `offer_salary_structure` across deployed versions. Confidential Notes
 * continues to use its own Html field exactly as before.
 */
registerHtmlFieldHistoryFormView("kavi_hr_applicant_form", [
    {
        name: "salary_structure",
        historyFieldNames: ["kavi_salary_structure_history"],
        restoreFieldNames: ["offer_salary_structure", "salary_structure"],
        title: _t("Salary Structure History"),
        emptyMessage: _t("The salary structure was empty at the time."),
        emptyNotification: _t(
            "Salary Structure has no past content that could be restored at the moment."
        ),
    },
    {
        name: "confidential_notes",
        title: _t("Confidential Notes History"),
        emptyMessage: _t("The confidential notes were empty at the time."),
        emptyNotification: _t(
            "Confidential Notes has no past content that could be restored at the moment."
        ),
    },
]);
