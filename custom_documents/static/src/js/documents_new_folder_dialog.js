/** @odoo-module **/

import { Component, useState } from "@odoo/owl";
import { Dialog } from "@web/core/dialog/dialog";
import { useService } from "@web/core/utils/hooks";
import { _t } from "@web/core/l10n/translation";

export class DocumentsNewFolderDialog extends Component {
    static template = "custom_documents.NewFolderDialog";
    static components = { Dialog };
    static props = {
        parentFolderId: { type: [Number, Boolean], optional: true },
        title: { type: String, optional: true },
        nameLabel: { type: String, optional: true },
        confirmLabel: { type: String, optional: true },
        onSaved: { type: Function, optional: true },
        close: { type: Function, optional: true },
    };

    setup() {
        this.orm = useService("orm");
        this.notification = useService("notification");
        this.title = this.props.title || _t("New Folder");
        this.nameLabel = this.props.nameLabel || _t("Folder Name");
        this.confirmLabel = this.props.confirmLabel || _t("Create");
        this.state = useState({
            name: "",
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
            const createdIds = await this.orm.create("documents.folder", [
                {
                    name: this.state.name.trim(),
                    parent_folder_id: this.props.parentFolderId || false,
                },
            ]);
            this.notification.add(_t("Folder created."), { type: "success" });
            this.props.onSaved && this.props.onSaved(createdIds && createdIds[0]);
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
