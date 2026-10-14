/** @odoo-module **/

import { useRef, useState } from "@odoo/owl";
import { useService } from "@web/core/utils/hooks";
import { _t } from "@web/core/l10n/translation";
import { DocumentsLinkDialog } from "./documents_link_dialog";
import { DocumentsNewFolderDialog } from "./documents_new_folder_dialog";

/**
 * Reads a File object and returns its content as a base64 string
 * (without the "data:<mimetype>;base64," prefix), the way Odoo's
 * Binary fields expect it.
 *
 * @param {File} file
 * @returns {Promise<string>}
 */
function fileToBase64(file) {
    return new Promise((resolve, reject) => {
        const reader = new FileReader();
        reader.onload = () => resolve(reader.result.split(",")[1] || "");
        reader.onerror = () => reject(reader.error);
        reader.readAsDataURL(file);
    });
}

/**
 * Hook used by the Documents kanban/list controllers to power the
 * Enterprise-style "New" split button: Upload / Request / Link /
 * Spreadsheet / Folder.
 *
 * @param {Component} component the owning view controller (kanban or list)
 */
export function useDocumentsNewMenu(component) {
    const orm = useService("orm");
    const actionService = useService("action");
    const dialogService = useService("dialog");
    const notification = useService("notification");

    const state = useState({
        acceptedExtensions: "*",
        isUploading: false,
        requestedDocumentId: false,
        isFulfillingRequest: false,
    });
    const fileInputRef = useRef("documentsNewFileInput");

    /**
     * Figures out which Workspace newly created records should be filed
     * under, based on the context of the action currently being displayed
     * (Company Drive, a specific folder, ...). Falls back to the current
     * user's own "My Drive" (resolved server-side) when nothing more
     * specific is known - this covers the "All", "Recent", "Shared with
     * me" and "Trash" screens, exactly like a personal cloud-storage app
     * would.
     */
    async function resolveFolderId() {
        // In Odoo 19 the active action context is exposed by the search
        // model.  The controller props do not reliably contain the action
        // context, so always prefer globalContext for uploads.  This is
        // important for the Employee -> Documents flow: the selected
        // employee folder must receive the uploaded file, not My Drive.
        const searchContext =
            (component.env && component.env.searchModel && component.env.searchModel.globalContext) || {};
        const propsContext = (component.props && component.props.context) || {};
        const ctx = { ...propsContext, ...searchContext };

        const folderId = ctx.documents_folder_id || ctx.default_folder_id;
        if (folderId) {
            return folderId;
        }
        if (ctx.default_folder_is_company_drive) {
            return orm.call("documents.folder", "get_company_drive_id", []);
        }
        return orm.call("documents.folder", "get_my_drive_id", []);
    }

    async function reload() {
        if (component.model) {
            await component.model.load();
        }
    }

    function openFilePicker(acceptedExtensions) {
        if (!fileInputRef.el) {
            return;
        }
        state.acceptedExtensions = acceptedExtensions;
        fileInputRef.el.value = "";
        // Let the DOM update the `accept` attribute before opening the
        // native file picker.
        Promise.resolve().then(() => fileInputRef.el.click());
    }

    return {
        state,
        fileInputRef,

        openUpload() {
            openFilePicker("*");
        },

        openRequestedUpload(documentId) {
            state.requestedDocumentId = Number(documentId) || false;
            state.isFulfillingRequest = !!state.requestedDocumentId;
            openFilePicker("*");
        },

        openSpreadsheet() {
            openFilePicker(".xlsx,.xls,.ods,.csv");
        },

        async onFileInputChange(ev) {
            const files = ev.target && ev.target.files ? [...ev.target.files] : [];
            const requestedDocumentId = state.requestedDocumentId;
            if (!files.length) {
                state.requestedDocumentId = false;
                state.isFulfillingRequest = false;
                return;
            }

            if (requestedDocumentId) {
                state.isFulfillingRequest = true;
                try {
                    // A requested document represents exactly one requested
                    // file, so only the first selected file is used.
                    const file = files[0];
                    const datas = await fileToBase64(file);
                    await orm.call(
                        "documents.document",
                        "action_upload_requested_file",
                        [[requestedDocumentId], datas, file.name, file.type || false]
                    );
                    notification.add(_t("Requested document uploaded."), {
                        type: "success",
                    });
                    await reload();
                } catch (error) {
                    notification.add(_t("The requested document upload failed. Please try again."), {
                        type: "danger",
                    });
                    throw error;
                } finally {
                    state.requestedDocumentId = false;
                    state.isFulfillingRequest = false;
                    if (fileInputRef.el) {
                        fileInputRef.el.value = "";
                    }
                }
                return;
            }

            state.isUploading = true;
            try {
                const folderId = await resolveFolderId();
                for (const file of files) {
                    const datas = await fileToBase64(file);
                    await orm.create("documents.document", [
                        {
                            name: file.name,
                            datas,
                            type: "binary",
                            folder_id: folderId,
                        },
                    ]);
                }
                notification.add(
                    files.length === 1
                        ? _t("Document uploaded.")
                        : _t("Documents uploaded."),
                    { type: "success" }
                );
                await reload();
            } catch (error) {
                notification.add(_t("The upload failed. Please try again."), {
                    type: "danger",
                });
                throw error;
            } finally {
                state.isUploading = false;
                if (fileInputRef.el) {
                    fileInputRef.el.value = "";
                }
            }
        },

        async openRequestWizard() {
            const ctx = (component.props && component.props.context) || {};
            const additionalContext = {};
            // If the user is already inside a specific workspace, request the
            // file there. From the Documents root, let the server default to
            // the company's Inbox, matching the reference Request dialog.
            if (ctx.default_folder_id) {
                additionalContext.default_folder_id = ctx.default_folder_id;
            } else if (ctx.default_folder_is_company_drive) {
                additionalContext.default_folder_is_company_drive = 1;
            }
            if (ctx.default_resource_model) {
                additionalContext.default_resource_model = ctx.default_resource_model;
            }
            if (ctx.default_resource_id) {
                additionalContext.default_resource_id = ctx.default_resource_id;
            }
            actionService.doAction("custom_documents.documents_request_wizard_action", {
                additionalContext,
                onClose: () => reload(),
            });
        },

        async openLinkDialog() {
            const folderId = await resolveFolderId();
            dialogService.add(DocumentsLinkDialog, {
                folderId,
                onSaved: () => reload(),
            });
        },

        async openNewFolderDialog() {
            const ctx = (component.props && component.props.context) || {};
            let parentFolderId = ctx.default_folder_id || false;
            if (!parentFolderId && ctx.default_folder_is_company_drive) {
                parentFolderId = await orm.call("documents.folder", "get_company_drive_id", []);
            }
            dialogService.add(DocumentsNewFolderDialog, {
                parentFolderId,
                onSaved: () => reload(),
            });
        },
    };
}
