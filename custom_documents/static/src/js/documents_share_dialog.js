/** @odoo-module **/

import { Component, onWillStart, useState } from "@odoo/owl";
import { Dialog } from "@web/core/dialog/dialog";
import { useService } from "@web/core/utils/hooks";
import { _t } from "@web/core/l10n/translation";

/**
 * Share dialog matching the Odoo Documents flow shown in the reference video:
 *
 *   Share: <document>
 *   - Add People / Add Groups
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
            selectedGroups: [],
            // "people" | "groups": the Add People / Add Groups radio.
            target: "people",
            canManageAccess: true,
            generalInternal: "none",
            generalLink: "none",
            search: "",
            suggestions: [],
            showSuggestions: false,
            role: "viewer",
            notify: true,
            message: "",
        });

        onWillStart(async () => {
            await this.load();
        });
    }

    get title() {
        return _t("Share: %s", this.state.documentName || "Document");
    }

    get hasSelection() {
        return this.state.selectedUsers.length + this.state.selectedGroups.length > 0;
    }

    get canShare() {
        return !this.state.saving && this.hasSelection;
    }

    get internalHint() {
        return {
            none: _t("Only people with access can open with the link"),
            viewer: _t("Can only view. Cannot rename, move, or delete."),
            editor: _t("Can view and edit. Cannot delete."),
        }[this.state.generalInternal];
    }

    get linkHint() {
        return {
            none: _t("No one on the internet can access"),
            viewer: _t("Anyone on the internet with the link can view"),
            editor: _t("Anyone on the internet with the link can view and download"),
        }[this.state.generalLink];
    }

    get selectedIds() {
        return this.state.selectedUsers.map((user) => user.id);
    }

    get roleLabel() {
        return this.state.role === "editor" ? _t("Editor") : _t("Viewer");
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
            this.state.selectedGroups = [];
            this.applyGeneralAccess(data);
        } finally {
            this.state.loading = false;
        }
    }

    applyGeneralAccess(data) {
        const access = data.general_access || {};
        this.state.generalInternal = access.internal || "none";
        this.state.generalLink = access.link || "none";
        this.state.canManageAccess = data.can_manage_access !== false;
    }

    onTargetChange(target) {
        this.state.target = target;
        this.state.search = "";
        this.state.suggestions = [];
        this.state.showSuggestions = false;
    }

    async onSearchInput(ev) {
        this.state.search = ev.target.value;
        this.state.showSuggestions = true;
        const method =
            this.state.target === "groups" ? "search_share_groups" : "search_share_users";
        // Groups are listed as soon as the field is focused; people only
        // once something has been typed.
        if (!this.state.search.trim() && this.state.target !== "groups") {
            this.state.suggestions = [];
            return;
        }
        this.state.suggestions = await this.orm.call("documents.share", method, [
            this.state.search.trim(),
        ]);
    }

    async onFocusSearch(ev) {
        this.state.showSuggestions = true;
        if (this.state.target === "groups" && !this.state.suggestions.length) {
            await this.onSearchInput(ev);
        }
    }

    onBlurSearch() {
        // Delay so a suggestion click is processed before hiding the menu.
        setTimeout(() => {
            this.state.showSuggestions = false;
        }, 150);
    }

    get selectionKey() {
        return this.state.target === "groups" ? "selectedGroups" : "selectedUsers";
    }

    addSuggestion(item) {
        const list = this.state[this.selectionKey];
        if (!list.some((entry) => entry.id === item.id)) {
            list.push(item);
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

    removeGroup(groupId) {
        this.state.selectedGroups = this.state.selectedGroups.filter(
            (group) => group.id !== groupId
        );
    }

    /**
     * General Access dropdowns are saved immediately, like the Enterprise
     * dialog: there is no extra "apply" step.
     */
    async onGeneralAccessChange(kind, ev) {
        const value = ev.target.value;
        const previous = kind === "internal" ? this.state.generalInternal : this.state.generalLink;
        if (kind === "internal") {
            this.state.generalInternal = value;
        } else {
            this.state.generalLink = value;
        }
        try {
            const data = await this.orm.call("documents.share", "set_general_access", [
                this.props.documentId,
                kind === "internal" ? value : null,
                kind === "link" ? value : null,
            ]);
            this.applyGeneralAccess(data);
            if (this.props.onShared) {
                await this.props.onShared(data);
            }
        } catch (error) {
            if (kind === "internal") {
                this.state.generalInternal = previous;
            } else {
                this.state.generalLink = previous;
            }
            throw error;
        }
    }

    onRoleChange(ev) {
        this.state.role = ev.target.value;
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
                    "none",
                    this.state.selectedGroups.map((group) => group.id),
                ]
            );
            this.state.shareUrl = result.share_url || this.state.shareUrl;
            this.state.users = result.users || this.state.users;
            this.state.owner = result.owner || this.state.owner;
            this.state.selectedUsers = [];
            this.state.selectedGroups = [];
            this.state.message = "";
            this.state.search = "";
            this.state.suggestions = [];
            this.applyGeneralAccess(result);
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
