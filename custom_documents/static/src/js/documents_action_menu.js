/** @odoo-module **/

import { useService } from "@web/core/utils/hooks";
import { _t } from "@web/core/l10n/translation";
import { DocumentsRenameDialog } from "./documents_rename_dialog";
import { DocumentsShortcutDialog } from "./documents_shortcut_dialog";
import { DocumentsInfoDialog } from "./documents_info_dialog";
import { DocumentsVersionsDialog } from "./documents_versions_dialog";
import { DocumentsSplitPdfDialog } from "./documents_split_pdf_dialog";

// Second group of the Actions menu (the first one holds Export, Duplicate...).
const DOCUMENT_ACTIONS_GROUP_NUMBER = 2;
const VERSIONS_GROUP_NUMBER = 3;
const LOCK_GROUP_NUMBER = 4;

/**
 * Move to Trash, Rename, Info & tags, Move, Create Shortcut and Copy Links
 * entries of the Actions menu of the list and kanban views, like the
 * reference Documents app.
 *
 * Add/Remove star, Split PDF, Manage Versions and Lock/Unlock work on
 * exactly one selected file.
 *
 * Move to Trash works on any selection (files and folders).  The other five
 * work on exactly one selected file or folder (Create Shortcut: files only).
 *
 * @param {Object} controller the list / kanban controller component
 * @returns {{ getItems: Function }} getItems() -> entries to merge into
 *          getStaticActionMenuItems()
 */
export function useDocumentsActionMenu(controller) {
    const orm = useService("orm");
    const dialog = useService("dialog");
    const notification = useService("notification");

    const selectedRecords = () => controller.model.root.selection || [];
    const documentIds = () => selectedRecords().map((record) => record.resId).filter(Boolean);
    const folderIds = () =>
        controller.documentsFolderSelection
            ? Array.from(controller.documentsFolderSelection.ids)
            : [];

    const totalSelected = () => documentIds().length + folderIds().length;
    const singleDocumentId = () =>
        totalSelected() === 1 && documentIds().length === 1 ? documentIds()[0] : false;
    const singleFolderId = () =>
        totalSelected() === 1 && folderIds().length === 1 ? folderIds()[0] : false;
    const isTrashView = () =>
        (controller.model.root.context || {}).documents_sidebar_category === "trash";

    // The selected file's record, for labels that depend on its data.
    const singleRecord = () => {
        const id = singleDocumentId();
        return id ? selectedRecords().find((record) => record.resId === id) : null;
    };
    const lockUserId = () => {
        const value = singleRecord()?.data?.lock_uid;
        return Array.isArray(value) ? value[0] : value?.id || value?.resId || false;
    };
    const isPdf = () => {
        const mimetype = singleRecord()?.data?.mimetype;
        return typeof mimetype === "string" && mimetype.includes("pdf");
    };

    async function refresh() {
        if (controller.discardFolderSelection) {
            controller.discardFolderSelection();
        }
        await controller.model.load();
    }

    return {
        getItems() {
            return {
                documents_trash: {
                    isAvailable: () => totalSelected() > 0 && !isTrashView(),
                    sequence: 35,
                    icon: "fa fa-trash",
                    description: _t("Move to Trash"),
                    callback: async () => {
                        const documents = documentIds();
                        const folders = folderIds();
                        if (documents.length) {
                            await orm.call("documents.document", "action_archive", [documents]);
                        }
                        if (folders.length) {
                            await orm.write("documents.folder", folders, { active: false });
                        }
                        notification.add(_t("Moved to Trash."), { type: "success" });
                        await refresh();
                    },
                },
                documents_rename: {
                    isAvailable: () => !!(singleDocumentId() || singleFolderId()),
                    sequence: 60,
                    groupNumber: DOCUMENT_ACTIONS_GROUP_NUMBER,
                    icon: "fa fa-pencil-square-o",
                    description: _t("Rename"),
                    callback: async () => {
                        const documentId = singleDocumentId();
                        const folderId = singleFolderId();
                        const resModel = documentId ? "documents.document" : "documents.folder";
                        const resId = documentId || folderId;
                        const [data] = await orm.read(resModel, [resId], ["name"]);
                        dialog.add(DocumentsRenameDialog, {
                            documentId: resId,
                            resModel,
                            currentName: data.name || "",
                            onRenamed: () => refresh(),
                        });
                    },
                },
                documents_info: {
                    isAvailable: () => !!(singleDocumentId() || singleFolderId()),
                    sequence: 61,
                    groupNumber: DOCUMENT_ACTIONS_GROUP_NUMBER,
                    icon: "fa fa-info-circle",
                    description: _t("Info & tags"),
                    callback: () => {
                        const documentId = singleDocumentId();
                        dialog.add(
                            DocumentsInfoDialog,
                            {
                                resId: documentId || singleFolderId(),
                                resModel: documentId ? "documents.document" : "documents.folder",
                                onChanged: () => controller.model.load(),
                            },
                            { onClose: () => refresh() }
                        );
                    },
                },
                documents_move: {
                    isAvailable: () => !!(singleDocumentId() || singleFolderId()),
                    sequence: 62,
                    groupNumber: DOCUMENT_ACTIONS_GROUP_NUMBER,
                    icon: "fa fa-arrow-circle-right",
                    description: _t("Move"),
                    callback: async () => {
                        const documentId = singleDocumentId();
                        const resModel = documentId ? "documents.document" : "documents.folder";
                        const resId = documentId || singleFolderId();
                        const [data] = await orm.read(resModel, [resId], ["name"]);
                        dialog.add(DocumentsShortcutDialog, {
                            resId,
                            resModel,
                            name: data.name || "",
                            mode: "move",
                            onDone: () => refresh(),
                        });
                    },
                },
                documents_shortcut: {
                    isAvailable: () => !!(singleDocumentId() || singleFolderId()),
                    sequence: 63,
                    groupNumber: DOCUMENT_ACTIONS_GROUP_NUMBER,
                    icon: "fa fa-external-link-square",
                    description: _t("Create Shortcut"),
                    callback: async () => {
                        const documentId = singleDocumentId();
                        const resModel = documentId ? "documents.document" : "documents.folder";
                        const resId = documentId || singleFolderId();
                        const [data] = await orm.read(resModel, [resId], ["name"]);
                        dialog.add(DocumentsShortcutDialog, {
                            resId,
                            resModel,
                            name: data.name || "",
                            onDone: () => refresh(),
                        });
                    },
                },
                documents_star: {
                    isAvailable: () => !!singleDocumentId(),
                    sequence: 65,
                    groupNumber: DOCUMENT_ACTIONS_GROUP_NUMBER,
                    icon: "fa fa-star-o",
                    description: singleRecord()?.data?.is_favorited
                        ? _t("Remove star")
                        : _t("Add star"),
                    callback: async () => {
                        await orm.call("documents.document", "action_toggle_favorite", [
                            [singleDocumentId()],
                        ]);
                        await refresh();
                    },
                },
                documents_split_pdf: {
                    isAvailable: () => !!singleDocumentId() && isPdf(),
                    sequence: 20,
                    icon: "fa fa-scissors",
                    description: _t("Split PDF"),
                    callback: () => {
                        dialog.add(DocumentsSplitPdfDialog, {
                            documentId: singleDocumentId(),
                            onSplit: () => refresh(),
                        });
                    },
                },
                documents_versions: {
                    isAvailable: () => !!singleDocumentId(),
                    sequence: 70,
                    groupNumber: VERSIONS_GROUP_NUMBER,
                    icon: "fa fa-history",
                    description: _t("Manage Versions"),
                    callback: () => {
                        dialog.add(DocumentsVersionsDialog, {
                            documentId: singleDocumentId(),
                            onRestored: () => refresh(),
                        });
                    },
                },
                documents_lock: {
                    isAvailable: () => !!singleDocumentId(),
                    sequence: 80,
                    groupNumber: LOCK_GROUP_NUMBER,
                    icon: "fa fa-lock",
                    description: lockUserId() ? _t("Unlock") : _t("Lock"),
                    callback: async () => {
                        const documentId = singleDocumentId();
                        await orm.call("documents.document", "action_toggle_lock", [[documentId]]);
                        const [data] = await orm.read("documents.document", [documentId], [
                            "lock_uid",
                        ]);
                        notification.add(
                            data.lock_uid ? _t("Document locked.") : _t("Document unlocked."),
                            { type: "success" }
                        );
                        await refresh();
                    },
                },
                documents_copy_link: {
                    isAvailable: () => !!(singleDocumentId() || singleFolderId()),
                    sequence: 64,
                    groupNumber: DOCUMENT_ACTIONS_GROUP_NUMBER,
                    icon: "fa fa-link",
                    description: _t("Copy Links"),
                    callback: async () => {
                        const documentId = singleDocumentId();
                        const url = await orm.call(
                            documentId ? "documents.document" : "documents.folder",
                            "action_copy_link",
                            [[documentId || singleFolderId()]]
                        );
                        try {
                            await navigator.clipboard.writeText(url);
                            notification.add(_t("Link copied to clipboard."), { type: "success" });
                        } catch {
                            notification.add(url, { type: "info", sticky: true, title: _t("Link") });
                        }
                    },
                },
            };
        },
    };
}
