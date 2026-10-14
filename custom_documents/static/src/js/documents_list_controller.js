/** @odoo-module **/

import { useState, useSubEnv } from "@odoo/owl";
import { useService } from "@web/core/utils/hooks";
import { _t } from "@web/core/l10n/translation";
import { ConfirmationDialog } from "@web/core/confirmation_dialog/confirmation_dialog";
import { download } from "@web/core/network/download";
import { ListController } from "@web/views/list/list_controller";
import { Dropdown } from "@web/core/dropdown/dropdown";
import { useDocumentsNewMenu } from "./documents_new_menu";
import { useDocumentsFileViewer } from "./documents_file_viewer_hook";

export class DocumentsListController extends ListController {
    static template = "custom_documents.ListView";
    static components = {
        ...ListController.components,
        Dropdown,
    };

    setup() {
        super.setup();
        this.documentsNew = useDocumentsNewMenu(this);
        this.documentsFileViewer = useDocumentsFileViewer(this);
        this.notification = useService("notification");

        // documents.folder rows are not part of model.root.selection (they
        // aren't real documents.document records), so the base
        // hasSelectedRecords getter never sees them. This reactive bag is
        // shared with DocumentsListRenderer via env, so a folder checkbox
        // toggle there is visible to the controller's toolbar logic below.
        this.documentsFolderSelection = useState({ ids: new Set() });
        useSubEnv({ documentsFolderSelection: this.documentsFolderSelection });
    }

    get hasSelectedRecords() {
        return super.hasSelectedRecords || this.documentsFolderSelection.ids.size > 0;
    }

    get hasSelectedFolders() {
        return this.documentsFolderSelection.ids.size > 0;
    }

    discardFolderSelection() {
        this.documentsFolderSelection.ids.clear();
    }

    /**
     * Extend the default Export / Duplicate / Archive / Unarchive / Delete
     * items so they also work when the selection includes documents.folder
     * rows, which live outside model.root.selection.
     */
    getStaticActionMenuItems() {
        const items = super.getStaticActionMenuItems();
        const folderIds = () => Array.from(this.documentsFolderSelection.ids);

        items.export = {
            ...items.export,
            isAvailable: () => this.isExportEnable || this.hasSelectedFolders,
            callback: async () => {
                if (this.model.root.selection.length) {
                    this.exportRecords(); // opens the native field-picker dialog for documents
                }
                if (this.hasSelectedFolders) {
                    await this.exportSelectedFolders(folderIds());
                }
            },
        };

        items.duplicate = {
            ...items.duplicate,
            isAvailable: () => this.activeActions.duplicate || this.hasSelectedFolders,
            callback: async () => {
                if (this.model.root.selection.length) {
                    await this.model.root.duplicateRecords();
                }
                if (this.hasSelectedFolders) {
                    const ids = folderIds();
                    await Promise.all(
                        ids.map((id) => this.orm.call("documents.folder", "copy", [id]))
                    );
                    this.discardFolderSelection();
                    await this.model.load();
                }
            },
        };

        items.archive = {
            ...items.archive,
            isAvailable: () => this.archiveEnabled || this.hasSelectedFolders,
            callback: async () => {
                if (this.model.root.selection.length) {
                    await this.model.root.toggleArchiveWithConfirmation(
                        true,
                        this.archiveDialogProps
                    );
                }
                if (this.hasSelectedFolders) {
                    await this.orm.write("documents.folder", folderIds(), { active: false });
                    this.discardFolderSelection();
                    await this.model.load();
                }
            },
        };

        items.unarchive = {
            ...items.unarchive,
            isAvailable: () => this.archiveEnabled || this.hasSelectedFolders,
            callback: async () => {
                if (this.model.root.selection.length) {
                    await this.model.root.toggleArchiveWithConfirmation(false);
                }
                if (this.hasSelectedFolders) {
                    await this.orm.write("documents.folder", folderIds(), { active: true });
                    this.discardFolderSelection();
                    await this.model.load();
                }
            },
        };

        items.delete = {
            ...items.delete,
            callback: () => this.onDeleteSelectedRecordsAndFolders(),
        };

        return items;
    }

    /**
     * Simple, dialog-free export for folders: downloads an .xlsx with a
     * fixed set of columns, using the same generic /web/export/xlsx route
     * the native ExportDataDialog itself calls internally. Folders don't
     * get the field-picker UI since documents.folder has no comparable
     * "exportable fields" setup to documents.document.
     */
    async exportSelectedFolders(folderIds) {
        const fields = [
            { name: "name", label: _t("Name") },
            { name: "folder_type", label: _t("Type") },
            { name: "document_count", label: _t("Document Count") },
            { name: "parent_folder_id", label: _t("Parent Workspace") },
        ];
        await download({
            data: {
                data: JSON.stringify({
                    import_compat: false,
                    context: this.model.root.context,
                    domain: [["id", "in", folderIds]],
                    fields,
                    groupby: [],
                    ids: folderIds,
                    model: "documents.folder",
                }),
            },
            url: "/web/export/xlsx",
        });
    }

    async onDeleteSelectedRecordsAndFolders() {
        const folderIds = Array.from(this.documentsFolderSelection.ids);

        if (!folderIds.length) {
            return this.onDeleteSelectedRecords(); // unchanged native behavior
        }

        const confirmed = await new Promise((resolve) => {
            this.dialogService.add(ConfirmationDialog, {
                title: _t("Delete"),
                body: _t(
                    "Are you sure you want to delete the selected folder(s)? " +
                    "Everything inside them will be deleted as well."
                ),
                confirm: () => resolve(true),
                cancel: () => resolve(false),
            });
        });
        if (!confirmed) {
            return;
        }

        if (this.model.root.selection.length) {
            await this.model.root.deleteRecords();
        }
        try {
            await this.orm.unlink("documents.folder", folderIds);
        } catch (error) {
            this.notification.add(
                _t(
                    "Some folders could not be deleted (the Company/Employee root drives can't be removed)."
                ),
                { type: "danger" }
            );
        }
        this.discardFolderSelection();
        await this.model.load();
    }

    async openRecord(record, mode) {
        if (record.data.state === "requested") {
            this.documentsNew.openRequestedUpload(record.resId);
            return;
        }
        if (this.documentsFileViewer.isPreviewable(record.data)) {
            const opened = this.documentsFileViewer.open(record);
            if (opened) {
                return;
            }
        }
        return super.openRecord(record, mode);
    }
}