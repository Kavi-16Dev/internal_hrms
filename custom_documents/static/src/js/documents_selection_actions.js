/** @odoo-module **/

import { useService } from "@web/core/utils/hooks";
import { _t } from "@web/core/l10n/translation";
import { download } from "@web/core/network/download";
import { DocumentsShareDialog } from "./documents_share_dialog";

/**
 * Download / Share buttons of the selection bar, shown next to the Actions
 * menu as soon as files and/or folders are selected (list and kanban).
 *
 * Files are the records of the view (``model.root.selection``).  Folders are
 * not records of the view: the list controller keeps their ids in
 * ``documentsFolderSelection`` (see DocumentsListController).
 *
 * @param {Object} controller the list / kanban controller component
 * @returns {{
 *   selectedCount: number,
 *   shareDisabled: boolean,
 *   shareTitle: string,
 *   onDownload: Function,
 *   onShare: Function,
 * }}
 */
export function useDocumentsSelectionActions(controller) {
    const orm = useService("orm");
    const dialog = useService("dialog");
    const notification = useService("notification");

    const selectedRecords = () => controller.model.root.selection || [];
    const documentIds = () => selectedRecords().map((record) => record.resId).filter(Boolean);
    const folderIds = () =>
        controller.documentsFolderSelection
            ? Array.from(controller.documentsFolderSelection.ids)
            : [];

    return {
        get selectedCount() {
            return documentIds().length + folderIds().length;
        },

        /** Sharing works on one file or one folder at a time. */
        get shareDisabled() {
            return this.selectedCount !== 1;
        },

        get shareTitle() {
            return this.shareDisabled ? _t("Select a single file or folder to share it") : "";
        },

        /**
         * One file is downloaded as is; several files and/or folders come as
         * a zip (a folder keeps its sub-folders).  The server only includes
         * what the user is allowed to read.
         */
        async onDownload() {
            const documents = documentIds();
            const folders = folderIds();
            if (!documents.length && !folders.length) {
                return;
            }
            const info = await orm.call("documents.document", "get_download_info", [
                documents,
                folders,
            ]);
            if (!info.count) {
                notification.add(_t("There is nothing to download in this selection."), {
                    type: "warning",
                });
                return;
            }
            if (info.attachment_id) {
                window.location = `/web/content/${info.attachment_id}?download=true`;
                return;
            }
            await download({
                url: "/documents/download",
                data: {
                    document_ids: JSON.stringify(documents),
                    folder_ids: JSON.stringify(folders),
                },
            });
        },

        onShare() {
            const documents = documentIds();
            const folders = folderIds();
            if (documents.length + folders.length !== 1) {
                return;
            }
            if (folders.length) {
                dialog.add(DocumentsShareDialog, { folderId: folders[0] });
                return;
            }
            const record = selectedRecords()[0];
            const props = { documentId: documents[0] };
            if (typeof record.data?.name === "string") {
                props.documentName = record.data.name;
            }
            dialog.add(DocumentsShareDialog, props);
        },
    };
}
