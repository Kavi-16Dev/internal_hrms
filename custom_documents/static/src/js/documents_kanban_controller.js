/** @odoo-module **/

import { KanbanController } from "@web/views/kanban/kanban_controller";
import { Dropdown } from "@web/core/dropdown/dropdown";
import { useDocumentsNewMenu } from "./documents_new_menu";
import { useService } from "@web/core/utils/hooks";
import { useDocumentsFileViewer } from "./documents_file_viewer_hook";
import { useDocumentsSelectionActions } from "./documents_selection_actions";
import { useDocumentsActionMenu } from "./documents_action_menu";

export class DocumentsKanbanController extends KanbanController {
    static template = "custom_documents.KanbanView";
    static components = {
        ...KanbanController.components,
        Dropdown,
    };

    setup() {
        super.setup();
        this.documentsNew = useDocumentsNewMenu(this);
        this.documentsFileViewer = useDocumentsFileViewer(this);
        // Download / Share buttons of the selection bar.
        this.documentsSelection = useDocumentsSelectionActions(this);
        // Move to Trash / Rename / Info & tags / Move / Create Shortcut / Copy Links.
        this.documentsActionMenu = useDocumentsActionMenu(this);
        this.documentsOrm = useService("orm");
    }

    getStaticActionMenuItems() {
        return {
            ...super.getStaticActionMenuItems(),
            ...(this.documentsActionMenu?.getItems() || {}),
        };
    }

    /**
     * Open the full-screen preview instead of the classic form view
     * when the clicked document has a file (or link) to show, exactly
     * like Odoo's own Documents app.
     */
    async openRecord(record, mode) {
        // A requested document is a placeholder, not a record that should
        // open in the form view. Clicking its card is the upload action:
        // open the browser's native file picker exactly like the reference
        // Documents UI.
        if (record.data.state === "requested") {
            this.documentsNew.openRequestedUpload(record.resId);
            return;
        }
        // A shortcut to a workspace opens that workspace.
        const shortcutFolder = record.data.shortcut_folder_id;
        if (shortcutFolder) {
            const folderId = Array.isArray(shortcutFolder)
                ? shortcutFolder[0]
                : shortcutFolder.id || shortcutFolder.resId;
            const action = await this.documentsOrm.call("documents.folder", "action_open_documents", [
                [folderId],
            ]);
            return this.actionService.doAction(action);
        }
        if (this.documentsFileViewer.isPreviewable(record.data)) {
            const opened = this.documentsFileViewer.open(record);
            if (opened) {
                return;
            }
            // open() failed and already notified the user; fall through
            // to the normal form view instead of doing nothing.
        }
        return super.openRecord(record, mode);
    }
}
