/** @odoo-module **/

import { _t } from "@web/core/l10n/translation";
import { registerHtmlFieldHistoryFormView } from "./kavi_html_field_history";
import { RecruitmentFormView } from "@hr_recruitment/views/recruitment_form_view";

/**
 * hr.job form: matches js_class="kavi_hr_job_form" set on the <form> root
 * in views/hr_job_views.xml. Adds "Budgeting Information History" and
 * "Key Roles and Responsibilities History" to the Action (cog) menu.
 *
 * IMPORTANT: hr_recruitment's own `hr_job_survey` view (inherited from the
 * same `hr.view_hr_job_form`) already sets js_class="recruitment_form_view"
 * on this form, whose RecruitmentFormController customizes the archive
 * confirmation message. Since only one js_class ends up applied to the
 * <form> tag, we build our history controller on TOP of
 * RecruitmentFormView (instead of the plain web FormView) so that
 * archive-message customization isn't silently lost - Version History is
 * added, nothing else is taken away.
 */
registerHtmlFieldHistoryFormView("kavi_hr_job_form", [
    {
        name: "budgeting_information",
        title: _t("Budgeting Information History"),
        emptyMessage: _t("The budgeting information was empty at the time."),
        emptyNotification: _t(
            "Budgeting Information has no past content that could be restored at the moment."
        ),
    },
    {
        name: "key_responsibilities",
        title: _t("Key Roles and Responsibilities History"),
        emptyMessage: _t("The key roles and responsibilities were empty at the time."),
        emptyNotification: _t(
            "Key Roles and Responsibilities has no past content that could be restored at the moment."
        ),
    },
], RecruitmentFormView);
