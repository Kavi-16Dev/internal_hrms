/** @odoo-module **/

import { Component, onWillStart, useState } from "@odoo/owl";
import { Dialog } from "@web/core/dialog/dialog";
import { useService } from "@web/core/utils/hooks";
import { _t } from "@web/core/l10n/translation";

/**
 * Shared dialog for the "Move" and "Create Shortcut" Actions-menu entries:
 * both boil down to "pick a destination workspace", they only differ in
 * title/confirm label and which server method they call.
 */
export class DocumentsMoveDialog extends Component {
    static template = "custom_documents.MoveDialog";
    static components = { Dialog };
    static props = {
        documentId: { type: Number },
        mode: { type: String }, // 'move' | 'shortcut' | 'move_folder' (documentId is then a workspace id)
        onDone: { type: Function, optional: true },
        close: { type: Function, optional: true },
    };

    setup() {
        this.orm = useService("orm");
        this.action = useService("action");
        this.notification = useService("notification");
        this.isShortcut = this.props.mode === "shortcut";
        this.isFolderMove = this.props.mode === "move_folder";
        this.title = this.isShortcut ? _t("Create Shortcut") : _t("Move");
        this.confirmLabel = this.isShortcut ? _t("Create Shortcut") : _t("Move");
        this.state = useState({
            folders: [],
            folderId: false,
            isSaving: false,
        });

        onWillStart(async () => {
            const folders = await this.orm.call("documents.folder", "name_search", ["", []], {
                limit: 300,
            });
            this.state.folders = folders
                .filter(([id]) => !(this.isFolderMove && id === this.props.documentId))
                .map(([id, display_name]) => ({ id, display_name }));
        });
    }

    get isConfirmDisabled() {
        return !this.state.folderId || this.state.isSaving;
    }

    async onConfirm() {
        if (this.isConfirmDisabled) {
            return;
        }
        this.state.isSaving = true;
        try {
            const method = this.isShortcut ? "action_create_shortcut" : "action_move";
            const model = this.isFolderMove ? "documents.folder" : "documents.document";
            const result = await this.orm.call(model, method, [
                [this.props.documentId],
                this.state.folderId,
            ]);
            this.notification.add(
                this.isShortcut
                    ? _t("Shortcut created.")
                    : this.isFolderMove
                    ? _t("Workspace moved.")
                    : _t("Document moved."),
                { type: "success" }
            );
            this.props.onDone && this.props.onDone(result);
            this.props.close();
        } catch (error) {
            this.state.isSaving = false;
            throw error;
        }
    }

    onDiscard() {
        this.props.close();
    }
}
