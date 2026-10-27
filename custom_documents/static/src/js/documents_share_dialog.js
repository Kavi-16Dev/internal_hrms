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
 * The same dialog also shares a *folder* (pass ``folderId`` instead of
 * ``documentId``).  Access granted on a folder is inherited by its
 * sub-folders and documents: the dialog lists the people who already have
 * access through an ancestor folder, and lets the owner remove direct access.
 *
 * This is deliberately a custom OWL dialog so Community does not depend on
 * Enterprise-only Documents sharing widgets.
 */
export class DocumentsShareDialog extends Component {
    static template = "custom_documents.ShareDialog";
    static components = { Dialog };
    static props = {
        // Exactly one of documentId / folderId is expected.
        documentId: { type: Number, optional: true },
        folderId: { type: Number, optional: true },
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
            // People with access through a share on an ancestor folder.
            inheritedUsers: [],
            // Access inherited from the parent folder: {internal, link, from}.
            inheritedAccess: null,
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

    get isFolder() {
        return !!this.props.folderId;
    }

    get title() {
        return _t(
            "Share: %s",
            this.state.documentName || (this.isFolder ? _t("Folder") : _t("Document"))
        );
    }

    /** Server method names and the id argument differ for folders. */
    get targetId() {
        return this.isFolder ? this.props.folderId : this.props.documentId;
    }

    get methods() {
        return this.isFolder
            ? {
                  load: "get_folder_share_dialog_data",
                  general: "set_folder_general_access",
                  share: "action_share_folder_internal",
              }
            : {
                  load: "get_share_dialog_data",
                  general: "set_general_access",
                  share: "action_share_internal",
              };
    }

    get hasSelection() {
        return this.state.selectedUsers.length + this.state.selectedGroups.length > 0;
    }

    get canShare() {
        return !this.state.saving && this.hasSelection;
    }

    get internalHint() {
        if (this.isFolder) {
            return {
                none: _t("Only people with access can open this folder"),
                viewer: _t("Can only view the folder and everything in it."),
                editor: _t("Can view and edit the files in this folder. Cannot delete."),
            }[this.state.generalInternal];
        }
        return {
            none: _t("Only people with access can open with the link"),
            viewer: _t("Can only view. Cannot rename, move, or delete."),
            editor: _t("Can view and edit. Cannot delete."),
        }[this.state.generalInternal];
    }

    /** Hint shown when the parent folder already opens this one up. */
    get inheritedInternalHint() {
        const inherited = this.state.inheritedAccess;
        if (!this.isFolder || !inherited || !inherited.from || inherited.internal === "none") {
            return "";
        }
        const level = inherited.internal === "editor" ? _t("Editor") : _t("Viewer");
        return _t("Also inherited from %s: internal users are %s.", inherited.from, level);
    }

    get linkHint() {
        if (this.isFolder) {
            return {
                none: _t("No one on the internet can access"),
                viewer: _t("Anyone on the internet with the link can view the files"),
                editor: _t("Anyone on the internet with the link can view and download the files"),
            }[this.state.generalLink];
        }
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
                this.methods.load,
                [this.targetId]
            );
            this.applyDialogData(data);
            this.state.selectedUsers = [];
            this.state.selectedGroups = [];
        } finally {
            this.state.loading = false;
        }
    }

    /** Apply the part of a server payload shared by load / share / access changes. */
    applyDialogData(data) {
        const target = data.folder || data.document;
        if (target) {
            this.state.documentName = target.name;
        }
        this.state.shareUrl = data.share_url || this.state.shareUrl || "";
        this.state.users = data.users || [];
        this.state.inheritedUsers = data.inherited_users || [];
        this.state.inheritedAccess = data.inherited_access || null;
        this.state.owner = data.owner || null;
        this.applyGeneralAccess(data);
    }

    applyGeneralAccess(data) {
        const access = data.general_access || {};
        this.state.generalInternal = access.internal || "none";
        this.state.generalLink = access.link || "none";
        this.state.canManageAccess = data.can_manage_access !== false;
    }

    /**
     * Remove a person's direct access to the folder (folders only).  Access
     * inherited from an ancestor is not listed here: it is removed where it
     * was granted.
     */
    async onRemoveAccess(person) {
        if (!this.isFolder || !this.state.canManageAccess) {
            return;
        }
        const result = await this.orm.call(
            "documents.share",
            "action_remove_folder_access",
            [this.props.folderId, person.id]
        );
        this.applyDialogData(result);
        this.notification.add(_t("Access removed for %s.", person.name), {
            type: "success",
        });
        if (this.props.onShared) {
            await this.props.onShared(result);
        }
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
            const data = await this.orm.call("documents.share", this.methods.general, [
                this.targetId,
                kind === "internal" ? value : null,
                kind === "link" ? value : null,
            ]);
            this.applyDialogData(data);
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
            const groupIds = this.state.selectedGroups.map((group) => group.id);
            // The folder method has no per-share "internal access" argument:
            // general access is saved on the folder itself.
            const args = this.isFolder
                ? [
                      this.props.folderId,
                      this.selectedIds,
                      this.state.role,
                      this.state.notify,
                      this.state.message || false,
                      groupIds,
                  ]
                : [
                      this.props.documentId,
                      this.selectedIds,
                      this.state.role,
                      this.state.notify,
                      this.state.message || false,
                      "none",
                      groupIds,
                  ];
            const result = await this.orm.call("documents.share", this.methods.share, args);
            this.applyDialogData(result);
            this.state.selectedUsers = [];
            this.state.selectedGroups = [];
            this.state.message = "";
            this.state.search = "";
            this.state.suggestions = [];
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
