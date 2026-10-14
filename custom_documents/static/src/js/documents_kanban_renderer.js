/** @odoo-module **/

import { onWillStart, useRef, useState } from "@odoo/owl";
import { useService } from "@web/core/utils/hooks";
import { KanbanRenderer } from "@web/views/kanban/kanban_renderer";
import { _t } from "@web/core/l10n/translation";

function fileToBase64(file) {
    return new Promise((resolve, reject) => {
        const reader = new FileReader();
        reader.onload = () => resolve(reader.result.split(",")[1] || "");
        reader.onerror = () => reject(reader.error);
        reader.readAsDataURL(file);
    });
}

/**
 * Documents-specific kanban renderer.
 *
 * The Documents screen is a mixed browser: folders are shown first and the
 * actual documents are shown below them. Folders are real documents.folder
 * records, not fake documents.document records, so opening a folder always
 * uses the same server-side action and preserves access rules.
 */
export class DocumentsKanbanRenderer extends KanbanRenderer {
    static template = "custom_documents.DocumentsKanbanRenderer";

    setup() {
        super.setup();
        this.orm = useService("orm");
        this.action = useService("action");
        this.notification = useService("notification");
        this.folderState = useState({ folders: [], loading: true });
        this.requestedUploadState = useState({ documentId: false, uploading: false });
        this.requestedUploadInput = useRef("documentsRequestedUploadInput");

        onWillStart(async () => {
            await this.loadDocumentFolders();
        });
    }

    get documentsContext() {
        return this.env.searchModel?.globalContext || {};
    }

    get showFolderBrowser() {
        const category = this.documentsContext.documents_sidebar_category || "all";
        return ["all", "company"].includes(category) || !!this.documentsContext.documents_folder_id;
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
            console.error("Documents folder browser failed to load", error);
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

    openRequestedUpload(documentId) {
        this.requestedUploadState.documentId = Number(documentId) || false;
        if (!this.requestedUploadState.documentId || !this.requestedUploadInput.el) {
            return;
        }
        this.requestedUploadInput.el.value = "";
        this.requestedUploadInput.el.click();
    }

    async onRequestedUploadChange(ev) {
        const file = ev.target?.files?.[0];
        const documentId = this.requestedUploadState.documentId;
        if (!file || !documentId) {
            this.requestedUploadState.documentId = false;
            return;
        }

        this.requestedUploadState.uploading = true;
        try {
            const datas = await fileToBase64(file);
            await this.orm.call(
                "documents.document",
                "action_upload_requested_file",
                [[documentId], datas, file.name, file.type || false]
            );
            this.notification.add(_t("Requested document uploaded."), { type: "success" });
            if (this.props.list?.load) {
                await this.props.list.load();
            }
        } catch (error) {
            this.notification.add(_t("The requested document upload failed. Please try again."), {
                type: "danger",
            });
            throw error;
        } finally {
            this.requestedUploadState.documentId = false;
            this.requestedUploadState.uploading = false;
            if (this.requestedUploadInput.el) {
                this.requestedUploadInput.el.value = "";
            }
        }
    }

    async openDocumentFolder(folder) {
        try {
            const action = await this.orm.call(
                "documents.folder",
                "action_open_documents",
                [[folder.id]],
            );

            // Odoo 19's action service normalizes `action.views` with
            // `.map()`.  Keep the client resilient to an old/cached server
            // response that may still return only `view_mode`.  The server
            // implementation now always returns `views`, but this guard
            // prevents the browser from crashing during a rolling upgrade.
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
            await this.action.doAction(action, { clearBreadcrumbs: true });
        } catch (error) {
            this.notification.add(_t("The folder could not be opened."), {
                type: "danger",
            });
            throw error;
        }
    }
}
