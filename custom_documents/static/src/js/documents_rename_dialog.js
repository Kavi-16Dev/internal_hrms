/** @odoo-module **/

import { Component, useState } from "@odoo/owl";
import { Dialog } from "@web/core/dialog/dialog";
import { useService } from "@web/core/utils/hooks";
import { _t } from "@web/core/l10n/translation";

/**
 * "Rename" Actions-menu entry: a tiny dialog with a single Name field,
 * calling documents.document's action_rename server-side.
 */
export class DocumentsRenameDialog extends Component {
    static template = "custom_documents.RenameDialog";
    static components = { Dialog };
    static props = {
        documentId: { type: Number },
        currentName: { type: String },
        onRenamed: { type: Function, optional: true },
        close: { type: Function, optional: true },
    };

    setup() {
        this.orm = useService("orm");
        this.notification = useService("notification");
        this.title = _t("Rename");
        this.state = useState({
            name: this.props.currentName || "",
            isSaving: false,
        });
    }

    get isConfirmDisabled() {
        return !this.state.name.trim() || this.state.isSaving;
    }

    async onConfirm() {
        if (this.isConfirmDisabled) {
            return;
        }
        this.state.isSaving = true;
        try {
            await this.orm.call("documents.document", "action_rename", [
                [this.props.documentId],
                this.state.name.trim(),
            ]);
            this.props.onRenamed && this.props.onRenamed(this.state.name.trim());
            this.props.close();
        } catch (error) {
            this.state.isSaving = false;
            throw error;
        }
    }

    onDiscard() {
        this.props.close();
    }

    onNameKeydown(ev) {
        if (ev.key === "Enter") {
            this.onConfirm();
        }
    }
}
