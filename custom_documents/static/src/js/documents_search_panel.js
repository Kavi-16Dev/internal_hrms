/** @odoo-module **/

import { onWillStart, useState } from "@odoo/owl";
import { browser } from "@web/core/browser/browser";
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
// Every click on a menu / folder opens an action, i.e. builds a NEW search
// panel.  The tree and which branches the user collapsed must therefore live
// outside the component, or the sidebar would reset on every click.
const DOCUMENTS_SIDEBAR_EXPANDED_KEY = "custom_documents.sidebar_expanded";
const TREE_STORAGE_KEY = "custom_documents.sidebar_tree_collapsed";
let cachedFolderTree = null;

function readCollapsedState() {
    try {
        return JSON.parse(browser.localStorage.getItem(TREE_STORAGE_KEY)) || {};
    } catch {
        return {};
    }
}

function writeCollapsedState(state) {
    try {
        browser.localStorage.setItem(TREE_STORAGE_KEY, JSON.stringify(state));
    } catch {
        // Storage unavailable: the state still lives for this page.
    }
}

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
        this.orm = useService("orm");
        this.notification = useService("notification");
        // The sidebar open/closed choice is remembered per action by Odoo,
        // and every menu / folder is another action - so it looked reset on
        // each click.  Use one global preference instead (open by default).
        this.keyExpandSidebar = DOCUMENTS_SIDEBAR_EXPANDED_KEY;
        const sidebarPreference = browser.localStorage.getItem(this.keyExpandSidebar);
        this.state.sidebarExpanded = sidebarPreference === null ? true : sidebarPreference === "true";
        // tree: {category id: [{id, name, children}]}
        // collapsed: {key: true} - only branches the user closed by hand;
        // everything else is open, and stays open across navigation.
        this.treeState = useState({
            tree: cachedFolderTree || {},
            collapsed: readCollapsedState(),
        });
        if (cachedFolderTree) {
            // Show the last known tree at once (no flicker) and refresh it
            // in the background.
            this.loadFolderTree();
        } else {
            onWillStart(async () => {
                await this.loadFolderTree();
            });
        }
    }

    /**
     * Odoo force-collapses a search panel that has no section (here: no tag
     * exists, now that the Workspaces section is gone), which closed our
     * folder tree on every page load.  The tree is the panel's real content,
     * so keep the user's own open/closed choice.
     */
    updateActiveValues() {
        const sidebarExpanded = this.state.sidebarExpanded;
        super.updateActiveValues(...arguments);
        this.state.sidebarExpanded = sidebarExpanded;
    }

    async loadFolderTree() {
        try {
            cachedFolderTree = await this.orm.call(
                "documents.folder",
                "get_sidebar_folder_tree",
                []
            );
            this.treeState.tree = cachedFolderTree;
        } catch (error) {
            // The sidebar must stay usable even if the tree cannot load.
            console.error("Documents sidebar folder tree failed to load", error);
        }
    }

    /** Folder currently open in the main area (from the action context). */
    get activeFolderId() {
        return (this.env.searchModel.globalContext || {}).documents_folder_id || false;
    }

    folderTree(category) {
        return this.treeState.tree[category.id] || [];
    }

    /**
     * Menus and folders are open by default and stay open; they only close
     * when the user collapses them with the caret.  The folder being viewed
     * is always kept visible.
     */
    isTreeExpanded(key, nodes) {
        if (this._containsActive(nodes)) {
            return true;
        }
        return !this.treeState.collapsed[key];
    }

    _containsActive(nodes) {
        const active = this.activeFolderId;
        return (
            !!active &&
            nodes.some((node) => node.id === active || this._containsActive(node.children))
        );
    }

    toggleTree(key, nodes) {
        const collapsed = { ...this.treeState.collapsed };
        if (this.isTreeExpanded(key, nodes)) {
            collapsed[key] = true;
        } else {
            delete collapsed[key];
        }
        this.treeState.collapsed = collapsed;
        writeCollapsedState(collapsed);
    }

    /** Open a folder of the tree, same navigation as the folder cards. */
    async openTreeFolder(node) {
        try {
            const action = await this.orm.call("documents.folder", "action_open_documents", [
                [node.id],
            ]);
            await this.actionService.doAction(action, { clearBreadcrumbs: true });
        } catch (error) {
            this.notification.add(_t("The folder could not be opened."), { type: "danger" });
            throw error;
        }
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
        // Clicking the active menu while inside one of its folders goes back
        // to the menu's root.
        if (category.id === this.activeDocumentsCategory && !this.activeFolderId) {
            return;
        }
        await this.actionService.doAction(category.actionXmlId, {
            clearBreadcrumbs: true,
        });
    }
}
