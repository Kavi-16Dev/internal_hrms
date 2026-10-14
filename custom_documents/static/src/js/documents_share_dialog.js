/** @odoo-module **/

import { Component, onWillStart, useState } from "@odoo/owl";
import { Dialog } from "@web/core/dialog/dialog";
import { useService } from "@web/core/utils/hooks";
import { _t } from "@web/core/l10n/translation";

/**
 * Share dialog matching the Odoo Documents flow shown in the reference video:
 *
 *   Share: <document>
 *   - add internal people / email addresses
 *   - role (Viewer / Editor)
 *   - Notify toggle
 *   - optional message
 *   - document link chip
 *   - General access / Access through link
 *   - Share / Copy Links / Discard
 *
 * This is deliberately a custom OWL dialog so Community does not depend on
 * Enterprise-only Documents sharing widgets.
 */
export class DocumentsShareDialog extends Component {
    static template = "custom_documents.ShareDialog";
    static components = { Dialog };
    static props = {
        documentId: { type: Number },
        documentName: { type: String, optional: true },
        onShared: { type: Function, optional: true },
        close: { type: Function, optional: true },
    };

    setup() {
        this.orm = useService("orm");
        this.notification = useService("notification");
        this.state = useState({
            loading: true,
            saving: false,
            documentName: this.props.documentName || "",
            shareUrl: "",
            users: [],
            owner: null,
            selectedUsers: [],
            mode: "invite",
            search: "",
            suggestions: [],
            showSuggestions: false,
            role: "viewer",
            notify: true,
            message: "",
            internalAccess: "none",
        });

        onWillStart(async () => {
            await this.load();
        });
    }

    get title() {
        return _t("Share: %s", this.state.documentName || "Document");
    }

    get canShare() {
        return !this.state.saving && this.state.selectedUsers.length > 0;
    }

    get selectedIds() {
        return this.state.selectedUsers.map((user) => user.id);
    }

    get roleLabel() {
        return this.state.role === "editor" ? _t("Editor") : _t("Viewer");
    }

    get generalAccessLabel() {
        if (this.state.internalAccess === "editor") {
            return _t("Internal Users — Editor");
        }
        if (this.state.internalAccess === "viewer") {
            return _t("Internal Users — Viewer");
        }
        return _t("None");
    }

    async load() {
        try {
            const data = await this.orm.call(
                "documents.share",
                "get_share_dialog_data",
                [this.props.documentId]
            );
            this.state.documentName = data.document.name;
            this.state.shareUrl = data.share_url || "";
            this.state.users = data.users || [];
            this.state.owner = data.owner || null;
            this.state.selectedUsers = [];
            // Always open in invite mode so an already-shared document can
            // receive another recipient without first entering the summary screen.
            this.state.mode = "invite";
            this.state.internalAccess = data.general_access || "none";
        } finally {
            this.state.loading = false;
        }
    }

    async onSearchInput(ev) {
        this.state.search = ev.target.value;
        this.state.showSuggestions = true;
        if (!this.state.search.trim()) {
            this.state.suggestions = [];
            return;
        }
        this.state.suggestions = await this.orm.call(
            "documents.share",
            "search_share_users",
            [this.state.search.trim()]
        );
    }

    onFocusSearch() {
        this.state.showSuggestions = true;
    }

    onBlurSearch() {
        // Delay so a suggestion click is processed before hiding the menu.
        setTimeout(() => {
            this.state.showSuggestions = false;
        }, 150);
    }

    isSelected(userId) {
        return this.state.selectedUsers.some((user) => user.id === userId);
    }

    addUser(user) {
        if (!this.isSelected(user.id)) {
            this.state.selectedUsers.push(user);
        }
        this.state.search = "";
        this.state.suggestions = [];
        this.state.showSuggestions = false;
    }

    removeUser(userId) {
        this.state.selectedUsers = this.state.selectedUsers.filter(
            (user) => user.id !== userId
        );
    }

    onRoleChange(ev) {
        this.state.role = ev.target.value;
        if (this.state.internalAccess !== "none") {
            this.state.internalAccess = this.state.role;
        }
    }

    onGeneralAccessChange(ev) {
        this.state.internalAccess = ev.target.value;
        if (ev.target.value === "editor") {
            this.state.role = "editor";
        } else if (ev.target.value === "viewer") {
            this.state.role = "viewer";
        }
    }

    async onCopyLink() {
        if (!this.state.shareUrl) {
            return;
        }
        try {
            await navigator.clipboard.writeText(this.state.shareUrl);
            this.notification.add(_t("Link copied to clipboard."), {
                type: "success",
            });
        } catch {
            this.notification.add(this.state.shareUrl, {
                type: "info",
                sticky: true,
                title: _t("Link"),
            });
        }
    }

    async onShare() {
        if (!this.canShare) {
            this.notification.add(_t("Please select at least one person."), {
                type: "warning",
            });
            return;
        }

        this.state.saving = true;
        try {
            const result = await this.orm.call(
                "documents.share",
                "action_share_internal",
                [
                    this.props.documentId,
                    this.selectedIds,
                    this.state.role,
                    this.state.notify,
                    this.state.message || false,
                    this.state.internalAccess,
                ]
            );
            this.state.shareUrl = result.share_url || this.state.shareUrl;
            this.state.users = result.users || this.state.users;
            this.state.owner = result.owner || this.state.owner;
            this.state.selectedUsers = [];
            this.state.search = "";
            this.state.suggestions = [];
            this.state.mode = "overview";
            this.notification.add(
                _t("Successfully Shared. Member added."),
                { type: "success" }
            );
            if (this.props.onShared) {
                await this.props.onShared(result);
            }
        } finally {
            this.state.saving = false;
        }
    }

    onDiscard() {
        this.props.close();
    }
}
