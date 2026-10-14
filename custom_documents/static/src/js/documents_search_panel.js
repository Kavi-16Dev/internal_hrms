/** @odoo-module **/

import { SearchPanel } from "@web/search/search_panel/search_panel";
import { useService } from "@web/core/utils/hooks";
import { _t } from "@web/core/l10n/translation";

/**
 * Fixed list of "drive" categories shown at the top of the Documents
 * search panel, exactly mirroring what used to be separate items under
 * the "Documents" top-menu dropdown (Documents > All / Company / My
 * Drive / Shared with me / Requests / Inbox / Recent / Trash).
 *
 * Each entry maps to the ir.actions.act_window that already implements
 * the corresponding domain/context (see documents_document_views.xml) -
 * clicking an item simply swaps to that action, in place, the same way
 * the old menu items did.
 */
const DOCUMENTS_CATEGORIES = [
    {
        id: "all",
        get label() {
            return _t("All");
        },
        icon: "fa-inbox",
        actionXmlId: "custom_documents.documents_document_action",
    },
    {
        id: "company",
        get label() {
            return _t("Company");
        },
        icon: "fa-building-o",
        actionXmlId: "custom_documents.documents_document_action_company_drive",
    },
    {
        id: "my_drive",
        get label() {
            return _t("My Drive");
        },
        icon: "fa-hdd-o",
        actionXmlId: "custom_documents.documents_document_action_my_drive",
    },
    {
        id: "shared_with_me",
        get label() {
            return _t("Shared with me");
        },
        icon: "fa-share-alt",
        actionXmlId: "custom_documents.documents_document_action_shared_with_me",
    },
    {
        id: "requests",
        get label() {
            return _t("Requests");
        },
        icon: "fa-file-o",
        actionXmlId: "custom_documents.documents_document_action_requests",
    },
    {
        id: "inbox",
        get label() {
            return _t("Inbox");
        },
        icon: "fa-inbox",
        actionXmlId: "custom_documents.documents_document_action_inbox",
    },
    {
        id: "recent",
        get label() {
            return _t("Recent");
        },
        icon: "fa-history",
        actionXmlId: "custom_documents.documents_document_action_recent",
    },
    {
        id: "trash",
        get label() {
            return _t("Trash");
        },
        icon: "fa-trash-o",
        actionXmlId: "custom_documents.documents_document_action_trash",
    },
];

export class DocumentsSearchPanel extends SearchPanel {
    // Scoped copies of web.SearchPanel / web.SearchPanelContent (see
    // documents_search_panel.xml) - only this component uses them, so the
    // fixed category list never leaks into other search panels.
    static template = "custom_documents.SearchPanel";
    static subTemplates = {
        ...SearchPanel.subTemplates,
    };

    setup() {
        super.setup();
        this.actionService = useService("action");
    }

    /**
     * @returns {Object[]} the fixed All/Company/My Drive/... entries.
     */
    get documentsCategories() {
        return DOCUMENTS_CATEGORIES;
    }

    /**
     * The currently active fixed category, resolved from the
     * `documents_sidebar_category` context key set on each of the six
     * act_window actions (defaults to "all" when unset, e.g. when this
     * search panel is reused by another model/action).
     * @returns {string}
     */
    get activeDocumentsCategory() {
        return (this.env.searchModel.globalContext || {}).documents_sidebar_category || "all";
    }

    /**
     * Switches to the action tied to the clicked category, replacing the
     * current breadcrumb - the exact same navigation the old "Documents"
     * top-menu dropdown items used to perform.
     * @param {Object} category one entry of DOCUMENTS_CATEGORIES
     */
    async selectDocumentsCategory(category) {
        if (category.id === this.activeDocumentsCategory) {
            return;
        }
        await this.actionService.doAction(category.actionXmlId, {
            clearBreadcrumbs: true,
        });
    }
}
