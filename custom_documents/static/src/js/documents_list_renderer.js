/** @odoo-module **/

import { onWillStart, useState } from "@odoo/owl";
import { useService } from "@web/core/utils/hooks";
import { ListRenderer } from "@web/views/list/list_renderer";
import { _t } from "@web/core/l10n/translation";

export class DocumentsListRenderer extends ListRenderer {
    static template = "custom_documents.DocumentsListRenderer";

    setup() {
        super.setup();
        this.orm = useService("orm");
        this.action = useService("action");
        this.notification = useService("notification");
        this.folderState = useState({
            folders: [],
            loading: true,
        });

        onWillStart(async () => {
            await this.loadDocumentFolders();
        });
    }

    get documentsContext() {
        return this.env.searchModel?.globalContext || {};
    }

    get showFolderBrowser() {
        const category =
            this.documentsContext.documents_sidebar_category || "all";
        return (
            ["all", "company"].includes(category) ||
            !!this.documentsContext.documents_folder_id
        );
    }

    async loadDocumentFolders() {
        if (!this.showFolderBrowser) {
            this.folderState.folders = [];
            this.folderState.loading = false;
            return;
        }

        try {
            this.folderState.folders = await this.orm.call(
                "documents.folder",
                "get_documents_view_folders",
                [
                    this.documentsContext.documents_sidebar_category || "all",
                    this.documentsContext.documents_folder_id || false,
                ],
            );
        } catch (error) {
            console.error("Documents folder list failed to load", error);
            this.folderState.folders = [];
            this.notification.add(_t("The folders could not be loaded."), {
                type: "warning",
            });
        } finally {
            this.folderState.loading = false;
        }
    }

    get documentFolders() {
        return this.folderState.folders;
    }

    // --- Folder selection: backed by state shared with the controller ---

    get folderSelection() {
        return this.env.documentsFolderSelection;
    }

    toggleFolderSelection(folder) {
        const ids = this.folderSelection.ids;
        if (ids.has(folder.id)) {
            ids.delete(folder.id);
        } else {
            ids.add(folder.id);
        }
    }

    isFolderSelected(folder) {
        return this.folderSelection.ids.has(folder.id);
    }

    // --- Opening folders ---

    async openDocumentFolder(folder) {
        try {
            const action = await this.orm.call(
                "documents.folder",
                "action_open_documents",
                [[folder.id]],
            );

            if (action && !Array.isArray(action.views)) {
                action.views = [
                    [false, "kanban"],
                    [false, "list"],
                    [false, "form"],
                ];
            }
            if (action && !action.view_mode) {
                action.view_mode = "kanban,list,form";
            }

            await this.action.doAction(action, {
                clearBreadcrumbs: true,
            });
        } catch (error) {
            this.notification.add(_t("The folder could not be opened."), {
                type: "danger",
            });
            throw error;
        }
    }

    onFolderKeydown(folder, ev) {
        if (ev.key === "Enter" || ev.key === " ") {
            ev.preventDefault();
            ev.stopPropagation();
            this.openDocumentFolder(folder);
        }
    }
}