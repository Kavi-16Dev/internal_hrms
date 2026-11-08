/** @odoo-module **/

import { Component, onWillStart, useState } from "@odoo/owl";
import { Dialog } from "@web/core/dialog/dialog";
import { useService } from "@web/core/utils/hooks";
import { _t } from "@web/core/l10n/translation";

/**
 * "Moving to: <destination>" confirmation: tells which access settings the
 * moved file / folder will take from the destination before moving.
 */
export class DocumentsMoveConfirmDialog extends Component {
    static template = "custom_documents.MoveConfirmDialog";
    static components = { Dialog };
    static props = {
        destinationId: { type: Number },
        destinationName: { type: String },
        onConfirm: { type: Function },
        close: { type: Function, optional: true },
    };

    setup() {
        this.orm = useService("orm");
        this.state = useState({ loading: true, internal: "none", link: "none", isSaving: false });

        onWillStart(async () => {
            const [folder] = await this.orm.read("documents.folder", [this.props.destinationId], [
                "effective_access_internal",
                "effective_access_via_link",
            ]);
            this.state.internal = folder.effective_access_internal || "none";
            this.state.link = folder.effective_access_via_link || "none";
            this.state.loading = false;
        });
    }

    get title() {
        return _t("Moving to: %s", this.props.destinationName);
    }

    get internalRight() {
        return {
            none: {
                label: _t("None"),
                help: _t("Only people it is explicitly shared with can access."),
            },
            viewer: {
                label: _t("Viewer"),
                help: _t("Can only view contents. Cannot add, modify, or delete items."),
            },
            editor: {
                label: _t("Editor"),
                help: _t("Can view, add, modify, and delete items."),
            },
        }[this.state.internal];
    }

    get linkRight() {
        return {
            none: { label: _t("None"), help: _t("No one on the internet can access") },
            viewer: {
                label: _t("Viewer"),
                help: _t("Anyone with the link can view the contents."),
            },
            editor: {
                label: _t("Editor"),
                help: _t("Anyone with the link can view and download the contents."),
            },
        }[this.state.link];
    }

    async onMove() {
        if (this.state.isSaving) {
            return;
        }
        this.state.isSaving = true;
        try {
            await this.props.onConfirm();
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
