/** @odoo-module **/

/**
 * This reproduces, field-for-field, the exact "Version History" feature
 * used on project.task's Description field
 * (project/static/src/views/project_task_form/project_task_form_controller.js):
 * a "Version History" entry in the form's Action (cog) menu, opening the
 * native HistoryDialog (diff/compare + one-click Restore), driven entirely
 * by the Html field's own embedded editor history - NOT a custom popup, NOT
 * a separate database model.
 *
 * Project only ever needed ONE such entry (Description). We have TWO Html
 * fields per model (e.g. Budgeting Information + Key Roles and
 * Responsibilities on hr.job), so this is written as a small factory that
 * takes a list of { name, title, emptyMessage, emptyNotification } field
 * descriptors.
 *
 * Rather than adding one flat Action-menu entry per field, all the fields
 * for a given form are grouped under a single "Version History" entry which
 * opens a submenu (hover/click flyout, same behaviour Odoo itself uses e.g.
 * for "Mute Conversation" in Discuss) listing one item per field. Clicking a
 * field's item opens the same HistoryDialog Project uses, just scoped to
 * that field.
 */

import { _t } from "@web/core/l10n/translation";
import { ConfirmationDialog } from "@web/core/confirmation_dialog/confirmation_dialog";
import { HistoryDialog } from "@html_editor/components/history_dialog/history_dialog";
import { useService } from "@web/core/utils/hooks";
import { Component, markup, xml } from "@odoo/owl";
import { getHtmlFieldMetadata, setHtmlFieldMetadata } from "@html_editor/fields/html_field";
import { FormController } from "@web/views/form/form_controller";
import { formView } from "@web/views/form/form_view";
import { registry } from "@web/core/registry";
import { Dropdown } from "@web/core/dropdown/dropdown";
import { DropdownItem } from "@web/core/dropdown/dropdown_item";

/**
 * Renders the "Version History" Action-menu entry as a submenu: a single
 * row ("Version History") that, on hover/click, opens a nested dropdown
 * listing one entry per tracked Html field (e.g. "Salary Structure
 * History", "Confidential Notes History").
 *
 * Odoo's own Dropdown component natively supports being nested inside
 * another Dropdown's content to build exactly this kind of flyout submenu -
 * see e.g. discuss's NotificationSettings "Mute Conversation" submenu. No
 * extra CSS/positioning logic is needed: Dropdown detects it has a parent
 * dropdown and automatically opens to the side, adds the caret, etc.
 */
class KaviVersionHistorySubmenu extends Component {
    static template = xml`
        <Dropdown menuClass="'o_kavi_version_history_submenu'">
            <button type="button" class="dropdown-item o_menu_item d-flex align-items-center">
                <i class="fa fa-history me-1 fa-fw oi-fw"/>
                <t t-esc="props.title"/>
            </button>
            <t t-set-slot="content">
                <t t-foreach="props.historyFields" t-as="field" t-key="field.name">
                    <DropdownItem class="'o_menu_item'" onSelected="() => props.onSelectField(field)">
                        <t t-esc="field.title"/>
                    </DropdownItem>
                </t>
            </t>
        </Dropdown>
    `;
    static components = { Dropdown, DropdownItem };
    static props = ["title", "historyFields", "onSelectField"];
}

/**
 * @param {Array<{name: string, title: string, emptyMessage: string, emptyNotification: string}>} historyFields
 * @param {typeof FormController} [BaseController] the controller class to extend -
 *        defaults to the plain FormController, but can be a more specific one
 *        (e.g. hr_recruitment's RecruitmentFormController) so this doesn't
 *        clobber other js_class-driven customizations already applied to the
 *        same form (e.g. the archive-confirmation message on hr.job).
 * @returns {typeof FormController}
 */
function htmlToPlainText(html) {
    const normalized = String(html || "")
        .replace(/<br\s*\/?\s*>/gi, "\n")
        .replace(/<\/(p|div|li|tr|h[1-6])\s*>/gi, "\n");
    const container = document.createElement("div");
    container.innerHTML = normalized;
    return (container.textContent || container.innerText || "")
        .replace(/\u00a0/g, " ")
        .replace(/\n{3,}/g, "\n\n")
        .trim();
}

export function makeHtmlFieldHistoryFormController(historyFields, BaseController = FormController) {
    class HtmlFieldHistoryFormController extends BaseController {
        setup() {
            super.setup();
            this.notification = useService("notification");
        }

        /**
         * @override
         */
        getStaticActionMenuItems() {
            const items = super.getStaticActionMenuItems();
            items.kaviVersionHistory = {
                sequence: 15,
                // A callback is required (even though unused) so that
                // ActionMenus' internal item-normalization keeps our
                // Component/props on the final item instead of treating it
                // like a plain server action record (which only happens
                // for entries that define a callback).
                callback: () => {},
                Component: KaviVersionHistorySubmenu,
                props: {
                    title: _t("Version History"),
                    historyFields,
                    onSelectField: (fieldDef) => this.kaviOpenHistoryDialog(fieldDef),
                },
            };
            return items;
        }

        async kaviOpenHistoryDialog(fieldDef) {
            const record = this.model.root;
            // A business field may have more than one technical name across
            // ATS releases.  Resolve the first field that is actually loaded
            // on this form and has native Html-history metadata.
            const candidateHistoryFields = fieldDef.historyFieldNames || [
                fieldDef.historyFieldName || fieldDef.name,
            ];
            let versionedFieldName = null;
            let historyMetadata = null;
            for (const candidate of candidateHistoryFields) {
                const metadata = record.data["html_field_history_metadata"]?.[candidate];
                if (metadata) {
                    versionedFieldName = candidate;
                    historyMetadata = metadata;
                    break;
                }
            }
            if (!versionedFieldName || !historyMetadata) {
                this.notification.add(fieldDef.emptyNotification);
                return;
            }

            this.dialogService.add(HistoryDialog, {
                title: fieldDef.title,
                noContentHelper: markup`<span class='text-muted fst-italic'>${fieldDef.emptyMessage}</span>`,
                recordId: record.resId,
                recordModel: this.props.resModel,
                versionedFieldName,
                historyMetadata,
                restoreRequested: (html, close) => {
                    this.dialogService.add(ConfirmationDialog, {
                        title: _t("Are you sure you want to restore this version ?"),
                        body: _t(
                            "Restoring will replace the current content with the selected version. Any unsaved changes will be lost."
                        ),
                        confirm: () => {
                            const restoredData = {};
                            const contentMetadata = getHtmlFieldMetadata(record.data[versionedFieldName]);
                            restoredData[versionedFieldName] = setHtmlFieldMetadata(html, contentMetadata);

                            if (fieldDef.restoreFieldNames) {
                                // The hidden mirror represents the legacy
                                // plain-text salary_structure field.  When it
                                // is selected, restore the real business field
                                // as plain text as well as restoring the
                                // mirror.  For offer_salary_structure, the
                                // Html field itself is the business field.
                                const restoreNames = fieldDef.restoreFieldNames;
                                if (versionedFieldName === "kavi_salary_structure_history") {
                                    if (restoreNames.includes("salary_structure")) {
                                        restoredData.salary_structure = htmlToPlainText(html);
                                    }
                                } else if (restoreNames.includes(versionedFieldName)) {
                                    restoredData[versionedFieldName] = html;
                                }
                            } else if (fieldDef.restoreFieldName) {
                                restoredData[fieldDef.restoreFieldName] = fieldDef.restoreAsPlainText
                                    ? htmlToPlainText(html)
                                    : html;
                            }
                            record.update(restoredData);
                            close();
                        },
                        confirmLabel: _t("Restore"),
                    });
                },
            });
        }
    }
    return HtmlFieldHistoryFormController;
}

/**
 * Registers a new form view (by js_class name) whose form controller adds a
 * single "Version History" Action-menu entry - opening as a submenu with one
 * item per field in `historyFields`.
 * Use the returned js_class as `js_class="<viewName>"` on the <form> root
 * tag of the corresponding view.
 *
 * @param {string} viewName
 * @param {Array<{name: string, title: string, emptyMessage: string, emptyNotification: string}>} historyFields
 * @param {object} [baseView] the view definition to extend - defaults to the
 *        plain web `formView`, but can be another registered view (e.g.
 *        hr_recruitment's `RecruitmentFormView`) so its Controller/behavior
 *        is preserved instead of being replaced by this js_class.
 */
export function registerHtmlFieldHistoryFormView(viewName, historyFields, baseView = formView) {
    registry.category("views").add(viewName, {
        ...baseView,
        Controller: makeHtmlFieldHistoryFormController(historyFields, baseView.Controller),
    });
}
