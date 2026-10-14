/** @odoo-module **/

import { Component, onWillStart, useState } from "@odoo/owl";
import { Dialog } from "@web/core/dialog/dialog";
import { useService } from "@web/core/utils/hooks";
import { _t } from "@web/core/l10n/translation";
import { formatDateTime } from "@web/core/l10n/dates";

/**
 * "Manage Versions" Actions-menu entry: lists every automatic snapshot
 * taken each time the file was replaced, with Download / Restore per
 * version.
 */
export class DocumentsVersionsDialog extends Component {
    static template = "custom_documents.VersionsDialog";
    static components = { Dialog };
    static props = {
        documentId: { type: Number },
        onRestored: { type: Function, optional: true },
        close: { type: Function, optional: true },
    };

    setup() {
        this.orm = useService("orm");
        this.notification = useService("notification");
        this.title = _t("Manage Versions");
        this.state = useState({
            versions: [],
            isLoading: true,
        });

        onWillStart(() => this.loadVersions());
    }

    async loadVersions() {
        this.state.isLoading = true;
        const versions = await this.orm.searchRead(
            "documents.document.version",
            [["document_id", "=", this.props.documentId]],
            ["name", "create_date", "create_uid", "file_size", "attachment_id"],
            { order: "create_date desc" }
        );
        this.state.versions = versions.map((version) => ({
            ...version,
            dateLabel: version.create_date ? formatDateTime(version.create_date) : "",
            userName: version.create_uid ? version.create_uid[1] : "",
            downloadUrl: version.attachment_id
                ? `/web/content/${version.attachment_id[0]}?download=true`
                : false,
        }));
        this.state.isLoading = false;
    }

    formatSize(bytes) {
        if (!bytes) {
            return "0 B";
        }
        const units = ["B", "KB", "MB", "GB"];
        let value = bytes;
        let unitIndex = 0;
        while (value >= 1024 && unitIndex < units.length - 1) {
            value /= 1024;
            unitIndex++;
        }
        return `${value.toFixed(unitIndex ? 1 : 0)} ${units[unitIndex]}`;
    }

    async onRestore(versionId) {
        await this.orm.call("documents.document.version", "action_restore", [[versionId]]);
        this.notification.add(_t("Version restored."), { type: "success" });
        this.props.onRestored && this.props.onRestored();
        await this.loadVersions();
    }

    onClose() {
        this.props.close();
    }
}
