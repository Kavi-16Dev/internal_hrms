/** @odoo-module **/

import { KanbanController } from "@web/views/kanban/kanban_controller";
import { Dropdown } from "@web/core/dropdown/dropdown";
import { useDocumentsNewMenu } from "./documents_new_menu";
import { useDocumentsFileViewer } from "./documents_file_viewer_hook";

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
