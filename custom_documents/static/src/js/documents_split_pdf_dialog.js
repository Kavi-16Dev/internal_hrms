/** @odoo-module **/

import { Component, useState } from "@odoo/owl";
import { Dialog } from "@web/core/dialog/dialog";
import { useService } from "@web/core/utils/hooks";
import { _t } from "@web/core/l10n/translation";

/**
 * "Split PDF" Actions-menu entry: cuts the current PDF into several new
 * documents according to the page ranges typed in (e.g. "1-2,3,4-5"),
 * filed in the same workspace as the original, which is left untouched.
 */
export class DocumentsSplitPdfDialog extends Component {
    static template = "custom_documents.SplitPdfDialog";
    static components = { Dialog };
    static props = {
        documentId: { type: Number },
        onSplit: { type: Function, optional: true },
        close: { type: Function, optional: true },
    };

    setup() {
        this.orm = useService("orm");
        this.notification = useService("notification");
        this.title = _t("Split PDF");
        this.state = useState({
            ranges: "",
            isSaving: false,
        });
    }

    get isConfirmDisabled() {
        return !this.state.ranges.trim() || this.state.isSaving;
    }

    async onConfirm() {
        if (this.isConfirmDisabled) {
            return;
        }
        this.state.isSaving = true;
        try {
            const newDocumentIds = await this.orm.call("documents.document", "action_split_pdf", [
                [this.props.documentId],
                this.state.ranges.trim(),
            ]);
            this.notification.add(_t("PDF split successfully."), { type: "success" });
            this.props.onSplit && this.props.onSplit(newDocumentIds);
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
