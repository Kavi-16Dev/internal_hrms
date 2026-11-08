/** @odoo-module **/

import { Component, onWillStart, useRef, useState } from "@odoo/owl";
import { Dialog } from "@web/core/dialog/dialog";
import { ConfirmationDialog } from "@web/core/confirmation_dialog/confirmation_dialog";
import { useService } from "@web/core/utils/hooks";
import { _t } from "@web/core/l10n/translation";
import { deserializeDateTime, formatDateTime } from "@web/core/l10n/dates";

/**
 * "Manage Versions" Actions-menu entry: the current file, the previous
 * versions (saved automatically each time the file is replaced), an
 * "Upload New Version" button and Download / Delete (and Restore) per file.
 */
export class DocumentsVersionsDialog extends Component {
    static template = "custom_documents.VersionsDialog";
    static components = { Dialog };
    static props = {
        documentId: { type: Number },
        // Called after anything changed the document's file.
        onRestored: { type: Function, optional: true },
        close: { type: Function, optional: true },
    };

    setup() {
        this.orm = useService("orm");
        this.dialog = useService("dialog");
        this.notification = useService("notification");
        this.fileInputRef = useRef("fileInput");
        this.state = useState({
            isLoading: true,
            isBusy: false,
            documentName: "",
            lockedByOther: false,
            current: false,
            versions: [],
        });

        onWillStart(() => this.loadVersions());
    }

    get dialogTitle() {
        return this.state.documentName
            ? _t('Manage Versions of "%s"', this.state.documentName)
            : _t("Manage Versions");
    }

    _prepare(entry) {
        return {
            ...entry,
            dateLabel: entry.date ? formatDateTime(deserializeDateTime(entry.date)) : "",
            downloadUrl: entry.attachment_id
                ? `/web/content/${entry.attachment_id}?download=true`
                : false,
            icon: this.iconFor(entry.mimetype),
        };
    }

    iconFor(mimetype) {
        if ((mimetype || "").includes("pdf")) {
            return "fa-file-pdf-o text-danger";
        }
        if ((mimetype || "").startsWith("image/")) {
            return "fa-file-image-o text-primary";
        }
        return "fa-file-o text-secondary";
    }

    async loadVersions() {
        this.state.isLoading = true;
        const data = await this.orm.call(
            "documents.document",
            "get_version_history",
            [[this.props.documentId]]
        );
        this.state.documentName = data.document_name;
        this.state.lockedByOther = data.is_locked_by_other;
        this.state.current = data.current ? this._prepare(data.current) : false;
        this.state.versions = data.versions.map((version) => this._prepare(version));
        this.state.isLoading = false;
    }

    async _afterChange(message) {
        if (message) {
            this.notification.add(message, { type: "success" });
        }
        this.props.onRestored && this.props.onRestored();
        await this.loadVersions();
    }

    // ------------------------------------------------------------------
    // Upload New Version
    // ------------------------------------------------------------------
    onUploadClick() {
        if (this.fileInputRef.el) {
            this.fileInputRef.el.value = "";
            this.fileInputRef.el.click();
        }
    }

    async onFileChosen(ev) {
        const file = ev.target.files && ev.target.files[0];
        if (!file) {
            return;
        }
        this.state.isBusy = true;
        try {
            const datas = await new Promise((resolve, reject) => {
                const reader = new FileReader();
                reader.onload = () => resolve(reader.result.split(",")[1] || "");
                reader.onerror = () => reject(reader.error);
                reader.readAsDataURL(file);
            });
            await this.orm.call("documents.document", "action_upload_new_version", [
                [this.props.documentId],
                datas,
                file.name,
                file.type || false,
            ]);
            await this._afterChange(_t("New version uploaded."));
        } finally {
            this.state.isBusy = false;
        }
    }

    // ------------------------------------------------------------------
    // Delete / Restore
    // ------------------------------------------------------------------
    onDeleteCurrent() {
        this.dialog.add(ConfirmationDialog, {
            title: _t("Delete the current version?"),
            body: _t(
                "The most recent previous version will become the current file again."
            ),
            confirmLabel: _t("Delete"),
            confirm: async () => {
                await this.orm.call("documents.document", "action_delete_current_version", [
                    [this.props.documentId],
                ]);
                await this._afterChange(_t("Version deleted."));
            },
            cancel: () => {},
        });
    }

    onDeleteVersion(versionId) {
        this.dialog.add(ConfirmationDialog, {
            title: _t("Delete this version?"),
            body: _t("This file version will be permanently deleted."),
            confirmLabel: _t("Delete"),
            confirm: async () => {
                await this.orm.call("documents.document.version", "action_delete_version", [
                    [versionId],
                ]);
                await this._afterChange(_t("Version deleted."));
            },
            cancel: () => {},
        });
    }

    async onRestore(versionId) {
        await this.orm.call("documents.document.version", "action_restore", [[versionId]]);
        await this._afterChange(_t("Version restored."));
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

    onClose() {
        this.props.close();
    }
}
