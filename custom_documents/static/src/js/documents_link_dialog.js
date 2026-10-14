/** @odoo-module **/

import { Component, useState } from "@odoo/owl";
import { Dialog } from "@web/core/dialog/dialog";
import { useService } from "@web/core/utils/hooks";
import { _t } from "@web/core/l10n/translation";

export class DocumentsLinkDialog extends Component {
    static template = "custom_documents.LinkDialog";
    static components = { Dialog };
    static props = {
        folderId: { type: [Number, Boolean], optional: true },
        onSaved: { type: Function, optional: true },
        close: { type: Function, optional: true },
    };

    setup() {
        this.orm = useService("orm");
        this.notification = useService("notification");
        this.title = _t("Save Link");
        this.state = useState({
            name: "",
            url: "",
            isSaving: false,
        });
    }

    get isConfirmDisabled() {
        return !this.state.name.trim() || !this.state.url.trim() || this.state.isSaving;
    }

    async onConfirm() {
        if (this.isConfirmDisabled) {
            return;
        }
        this.state.isSaving = true;
        try {
            await this.orm.create("documents.document", [
                {
                    name: this.state.name.trim(),
                    url: this.state.url.trim(),
                    type: "url",
                    folder_id: this.props.folderId || false,
                },
            ]);
            this.notification.add(_t("Link saved."), { type: "success" });
            this.props.onSaved && this.props.onSaved();
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
