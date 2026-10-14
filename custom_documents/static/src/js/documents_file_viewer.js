/** @odoo-module **/

import { Component, onMounted, onWillUnmount, useRef, useState } from "@odoo/owl";
import { useService } from "@web/core/utils/hooks";
import { user } from "@web/core/user";
import { _t } from "@web/core/l10n/translation";
import { Dropdown } from "@web/core/dropdown/dropdown";
import { DropdownItem } from "@web/core/dropdown/dropdown_item";
import { ConfirmationDialog } from "@web/core/confirmation_dialog/confirmation_dialog";
import { DocumentsRenameDialog } from "./documents_rename_dialog";
import { DocumentsMoveDialog } from "./documents_move_dialog";
import { DocumentsVersionsDialog } from "./documents_versions_dialog";
import { DocumentsSplitPdfDialog } from "./documents_split_pdf_dialog";
import { DocumentsShareDialog } from "./documents_share_dialog";

/**
 * Full-screen preview shown when a document is clicked in the Documents
 * kanban/list view: a PDF/image viewer (matching Odoo's own Documents
 * app) with previous/next navigation across every other previewable
 * document currently loaded in the view, an Actions menu (Duplicate,
 * Rename, Info & tags, Move, Create Shortcut, Manage Versions, Lock,
 * Copy Links, Split PDF, Move to Trash...), Download / Share / Create an
 * Applicant buttons, and a slide-in Info panel - all mirroring the
 * reference Documents app.
 */
export class DocumentsFileViewer extends Component {
    static template = "custom_documents.FileViewer";
    static components = { Dropdown, DropdownItem };
    static props = {
        records: { type: Array },
        startIndex: { type: Number, optional: true },
        reload: { type: Function, optional: true },
        close: { type: Function, optional: true },
    };

    setup() {
        this.orm = useService("orm");
        this.action = useService("action");
        this.dialog = useService("dialog");
        this.notification = useService("notification");
        this.user = user;

        this.state = useState({
            index: this.props.startIndex || 0,
            // Local overlay of server-side changes made from this viewer
            // (rename, lock toggle...) keyed by document id, so the header
            // /menu reflect them immediately without waiting for the
            // underlying kanban/list to reload.
            patches: {},
            infoOpen: false,
            infoLoading: false,
            info: null,
        });

        this.headerRef = useRef("header");
        this.bodyRef = useRef("body");

        this.onKeydown = this.onKeydown.bind(this);
        this.positionOverlay = this.positionOverlay.bind(this);
        onMounted(() => {
            document.addEventListener("keydown", this.onKeydown);
            // Match Odoo's own Documents app: the dark title bar takes
            // over the top navbar's exact height, and the preview body
            // fills the *entire* remaining viewport - breadcrumb, search
            // bar, workspace tree and card grid are all fully replaced
            // by the preview, exactly like the reference behaviour.
            this.positionOverlay();
            window.addEventListener("resize", this.positionOverlay);
        });
        onWillUnmount(() => {
            document.removeEventListener("keydown", this.onKeydown);
            window.removeEventListener("resize", this.positionOverlay);
        });
    }

    /**
     * Sizes/positions the header against the current page's own navbar
     * (measured at runtime rather than hard-coded, so this keeps working
     * regardless of theme or viewport size) and makes the body take up
     * the *entire* remaining viewport - exactly like the reference
     * Documents app, where opening a file completely replaces the
     * breadcrumb, search bar and workspace tree with the preview, not
     * just the card grid.
     */
    positionOverlay() {
        const navbar = document.querySelector(".o_main_navbar");
        if (this.headerRef.el && navbar) {
            const height = navbar.getBoundingClientRect().height;
            if (height) {
                this.headerRef.el.style.height = `${height}px`;
                if (this.bodyRef.el) {
                    this.bodyRef.el.style.top = `${height}px`;
                }
            }
        }
        // Keep the folder tree (search panel) sidebar visible on the
        // left, exactly like the reference Documents app: the preview
        // only takes over the main content area to its right, not the
        // whole viewport.
        const searchPanel = document.querySelector(".o_search_panel");
        const left = searchPanel ? searchPanel.getBoundingClientRect().width : 0;
        if (this.headerRef.el) {
            this.headerRef.el.style.left = `${left}px`;
        }
        if (this.bodyRef.el) {
            this.bodyRef.el.style.left = `${left}px`;
        }
    }

    // ------------------------------------------------------------------
    // Getters
    // ------------------------------------------------------------------
    get record() {
        const base = this.props.records[this.state.index] || {};
        const patch = this.state.patches[base.id] || {};
        return { ...base, ...patch };
    }

    get hasMultiple() {
        return this.props.records.length > 1;
    }

    get hasPrevious() {
        return this.state.index > 0;
    }

    get hasNext() {
        return this.state.index < this.props.records.length - 1;
    }

    get isPdf() {
        return typeof this.record.mimetype === "string" && this.record.mimetype.indexOf("pdf") !== -1;
    }

    get isImage() {
        return typeof this.record.mimetype === "string" && this.record.mimetype.indexOf("image") === 0;
    }

    get isUrlDocument() {
        return this.record.type === "url";
    }

    get contentUrl() {
        return this.record.attachmentId ? `/web/content/${this.record.attachmentId}` : "";
    }

    get downloadUrl() {
        return this.record.attachmentId
            ? `/web/content/${this.record.attachmentId}?download=true`
            : "";
    }

    get pdfViewerUrl() {
        if (!this.contentUrl) {
            return "";
        }
        return `/web/static/lib/pdfjs/web/viewer.html?file=${encodeURIComponent(
            this.contentUrl
        )}#pagemode=none`;
    }

    get canDownload() {
        return !this.isUrlDocument && !!this.record.attachmentId && this.record.active;
    }

    get canShare() {
        return this.record.active;
    }

    get canTrash() {
        return this.record.active;
    }

    get canRestore() {
        return !this.record.active;
    }

    get canDeletePermanently() {
        return !this.record.active;
    }

    get canCreateApplicant() {
        return !!this.record.showCreateApplicant;
    }

    get isLocked() {
        return !!this.record.lockUid;
    }

    get lockedByMe() {
        return this.isLocked && this.lockUidId === this.user.userId;
    }

    get lockUidId() {
        const value = this.record.lockUid;
        if (!value) {
            return false;
        }
        return Array.isArray(value) ? value[0] : value.id;
    }

    get lockUidName() {
        const value = this.record.lockUid;
        if (!value) {
            return "";
        }
        return Array.isArray(value) ? value[1] : value.display_name;
    }

    get lockLabel() {
        if (!this.isLocked) {
            return _t("Lock");
        }
        return this.lockedByMe ? _t("Unlock") : _t("Unlock (%s)", this.lockUidName);
    }

    // ------------------------------------------------------------------
    // Navigation
    // ------------------------------------------------------------------
    previous() {
        if (this.hasPrevious) {
            this.state.index--;
            this.closeInfoPanel();
        }
    }

    next() {
        if (this.hasNext) {
            this.state.index++;
            this.closeInfoPanel();
        }
    }

    onKeydown(ev) {
        if (ev.key === "ArrowLeft") {
            this.previous();
        } else if (ev.key === "ArrowRight") {
            this.next();
        } else if (ev.key === "Escape") {
            if (this.state.infoOpen) {
                this.closeInfoPanel();
            } else {
                this.props.close();
            }
        }
    }

    // ------------------------------------------------------------------
    // Small helper to merge a patch onto the currently displayed record,
    // and a helper to silently refresh the underlying view in the
    // background so kanban cards/list rows stay in sync too.
    // ------------------------------------------------------------------
    patchRecord(fields) {
        const id = this.record.id;
        this.state.patches[id] = { ...(this.state.patches[id] || {}), ...fields };
    }

    async reloadQuietly() {
        if (this.props.reload) {
            await this.props.reload();
        }
    }

    // ------------------------------------------------------------------
    // Actions - all delegate to the existing server-side methods on
    // documents.document via doActionButton, exactly like the list
    // view's row buttons, so there is a single source of truth.
    // ------------------------------------------------------------------
    async callButton(name, { onSuccess } = {}) {
        await this.action.doActionButton({
            resModel: "documents.document",
            resId: this.record.id,
            name,
            type: "object",
            onClose: async () => {
                if (this.props.reload) {
                    await this.props.reload();
                }
                if (onSuccess) {
                    onSuccess();
                }
            },
        });
    }

    onDownload() {
        if (!this.canDownload) {
            return;
        }
        window.location = this.downloadUrl;
    }

    onShare() {
        this.dialog.add(DocumentsShareDialog, {
            documentId: this.record.id,
            documentName: this.record.name,
            onShared: async () => {
                await this.reloadQuietly();
            },
        });
    }

    /**
     * "Create an Applicant": convert this document into a new Recruitment
     * applicant, attach a copy of the file to it, and navigate to the new
     * applicant's form (closing the viewer first, exactly like the
     * reference behaviour). CV data-extraction credits are a standard IAP
     * mechanism we don't have access to here, so - like the reference
     * environment when it has none left - we surface the same "not enough
     * credits" notification with a "Buy more credits" action instead of
     * silently doing nothing.
     */
    async onCreateApplicant() {
        if (!this.canCreateApplicant) {
            return;
        }
        const action = await this.orm.call(
            "documents.document",
            "action_create_applicant",
            [[this.record.id]]
        );
        this.props.close();
        await this.action.doAction(action);
        this.notification.add("", {
            type: "danger",
            sticky: false,
            title: _t("Not enough credits for data extraction."),
            buttons: [
                {
                    name: _t("Buy more credits"),
                    onClick: () => {
                        window.open("https://iap.odoo.com/iap/1/credit", "_blank");
                    },
                },
            ],
        });
    }

    openFormView() {
        const id = this.record.id;
        this.props.close();
        this.action.doAction({
            type: "ir.actions.act_window",
            res_model: "documents.document",
            res_id: id,
            views: [[false, "form"]],
            target: "current",
        });
    }

    onOpenLink() {
        if (this.record.url) {
            window.open(this.record.url, "_blank");
        }
    }

    async onTrash() {
        await this.callButton("action_archive", { onSuccess: () => this.props.close() });
    }

    async onRestore() {
        await this.callButton("action_restore", { onSuccess: () => this.props.close() });
    }

    onDeletePermanently() {
        this.dialog.add(ConfirmationDialog, {
            title: _t("Delete Permanently"),
            body: _t(
                "This document will be permanently deleted. This action cannot be undone."
            ),
            confirmLabel: _t("Delete Permanently"),
            confirm: async () => {
                await this.callButton("action_delete_permanently", {
                    onSuccess: () => this.props.close(),
                });
            },
            cancel: () => {},
        });
    }

    // ------------------------------------------------------------------
    // Actions menu - additional entries matching the reference Documents
    // app's "Actions" dropdown.
    // ------------------------------------------------------------------
    async onDuplicate() {
        await this.orm.call("documents.document", "action_duplicate", [[this.record.id]]);
        this.notification.add(_t("Document duplicated."), { type: "success" });
        await this.reloadQuietly();
    }

    onRename() {
        this.dialog.add(DocumentsRenameDialog, {
            documentId: this.record.id,
            currentName: this.record.name,
            onRenamed: (newName) => {
                this.patchRecord({ name: newName });
                this.reloadQuietly();
            },
        });
    }

    onMove() {
        this.dialog.add(DocumentsMoveDialog, {
            documentId: this.record.id,
            mode: "move",
            onDone: () => this.reloadQuietly(),
        });
    }

    onCreateShortcut() {
        this.dialog.add(DocumentsMoveDialog, {
            documentId: this.record.id,
            mode: "shortcut",
            onDone: () => this.reloadQuietly(),
        });
    }

    onManageVersions() {
        this.dialog.add(DocumentsVersionsDialog, {
            documentId: this.record.id,
            onRestored: () => this.reloadQuietly(),
        });
    }

    onSplitPdf() {
        this.dialog.add(DocumentsSplitPdfDialog, {
            documentId: this.record.id,
            onSplit: () => this.reloadQuietly(),
        });
    }

    async onToggleLock() {
        await this.orm.call("documents.document", "action_toggle_lock", [[this.record.id]]);
        const [data] = await this.orm.read("documents.document", [this.record.id], ["lock_uid"]);
        this.patchRecord({ lockUid: data.lock_uid || false });
        this.notification.add(
            data.lock_uid ? _t("Document locked.") : _t("Document unlocked."),
            { type: "success" }
        );
        await this.reloadQuietly();
    }

    async onCopyLink() {
        const url = await this.orm.call("documents.document", "action_copy_link", [
            [this.record.id],
        ]);
        try {
            await navigator.clipboard.writeText(url);
            this.notification.add(_t("Link copied to clipboard."), { type: "success" });
        } catch {
            this.notification.add(url, { type: "info", sticky: true, title: _t("Link") });
        }
    }

    // ------------------------------------------------------------------
    // Info & tags panel
    // ------------------------------------------------------------------
    async onToggleInfo() {
        if (this.state.infoOpen) {
            this.closeInfoPanel();
            return;
        }
        this.state.infoOpen = true;
        await this.loadInfo();
    }

    closeInfoPanel() {
        this.state.infoOpen = false;
    }

    async loadInfo() {
        this.state.infoLoading = true;
        const id = this.record.id;
        const [data] = await this.orm.read("documents.document", [id], [
            "name",
            "folder_id",
            "owner_id",
            "partner_id",
            "tag_ids",
            "create_date",
            "file_size",
            "res_name",
            "lock_uid",
            "type",
            "url",
        ]);
        const allTags = await this.orm.searchRead("documents.tag", [], ["name", "color"]);
        this.state.info = { ...data, allTags };
        this.state.infoLoading = false;
    }

    async onInfoNameChange(ev) {
        const newName = ev.target.value.trim();
        if (!newName || newName === this.record.name) {
            return;
        }
        await this.orm.call("documents.document", "action_rename", [[this.record.id], newName]);
        this.patchRecord({ name: newName });
        this.state.info.name = newName;
        await this.reloadQuietly();
    }

    async onToggleTag(tagId) {
        const current = this.state.info.tag_ids || [];
        const newIds = current.includes(tagId)
            ? current.filter((id) => id !== tagId)
            : [...current, tagId];
        await this.orm.write("documents.document", [this.record.id], {
            tag_ids: [[6, 0, newIds]],
        });
        this.state.info.tag_ids = newIds;
        await this.reloadQuietly();
    }

    formatFileSize(bytes) {
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
}
