/** @odoo-module **/

import { Component, onWillStart, useState } from "@odoo/owl";
import { Dialog } from "@web/core/dialog/dialog";
import { useService } from "@web/core/utils/hooks";
import { _t } from "@web/core/l10n/translation";
import { DocumentsNewFolderDialog } from "./documents_new_folder_dialog";
import { DocumentsMoveConfirmDialog } from "./documents_move_confirm_dialog";

/**
 * Destination picker of the "Create Shortcut" and "Move" Actions-menu
 * entries, for a file or a workspace (folder): pick a destination in the
 * folder tree, then
 *   - "Create a shortcut in <destination>" / "Move to <destination>"
 *     (Move first asks for confirmation, showing the access settings the
 *     item will take from the destination),
 *   - "Create a folder in <destination>" (to make the destination first),
 *   - "Discard".
 */
export class DocumentsShortcutDialog extends Component {
    static template = "custom_documents.ShortcutDialog";
    static components = { Dialog };
    static props = {
        resId: { type: Number },
        resModel: { type: String }, // documents.document | documents.folder
        name: { type: String, optional: true },
        mode: { type: String, optional: true }, // 'shortcut' (default) | 'move'
        onDone: { type: Function, optional: true },
        close: { type: Function, optional: true },
    };

    setup() {
        this.orm = useService("orm");
        this.dialog = useService("dialog");
        this.notification = useService("notification");
        this.state = useState({
            tree: [],
            selectedId: false,
            selectedName: "",
            search: "",
            collapsed: {},
            isSaving: false,
        });

        onWillStart(async () => {
            await this.loadTree();
            // My Drive is the default destination, like the reference.
            const first = this.state.tree[0];
            if (first) {
                this.select(first);
            }
        });
    }

    get isMove() {
        return this.props.mode === "move";
    }

    get title() {
        return this.isMove
            ? _t("Move: %s", this.props.name || "")
            : _t("Create shortcut to: %s", this.props.name || "");
    }

    async loadTree() {
        const tree = await this.orm.call("documents.folder", "get_shortcut_destination_tree", []);
        // A workspace cannot be moved into itself (nor its sub-workspaces).
        this.state.tree =
            this.isMove && this.props.resModel === "documents.folder"
                ? this._without(tree, this.props.resId)
                : tree;
    }

    _without(nodes, excludedId) {
        return nodes
            .filter((node) => node.id !== excludedId)
            .map((node) => ({ ...node, children: this._without(node.children, excludedId) }));
    }

    select(node) {
        this.state.selectedId = node.id;
        this.state.selectedName = node.name;
    }

    // ------------------------------------------------------------------
    // Tree + search
    // ------------------------------------------------------------------
    _matches(node, term) {
        return (
            node.name.toLowerCase().includes(term) ||
            node.children.some((child) => this._matches(child, term))
        );
    }

    /** Roots to display: all of them, or only the branches matching the search. */
    get visibleTree() {
        const term = this.state.search.trim().toLowerCase();
        return term ? this.state.tree.filter((node) => this._matches(node, term)) : this.state.tree;
    }

    visibleChildren(node) {
        const term = this.state.search.trim().toLowerCase();
        return term ? node.children.filter((child) => this._matches(child, term)) : node.children;
    }

    isExpanded(node) {
        // While searching, show every matching branch open.
        return !!this.state.search.trim() || !this.state.collapsed[node.id];
    }

    toggle(node) {
        this.state.collapsed[node.id] = this.isExpanded(node);
    }

    clearSearch() {
        this.state.search = "";
    }

    // ------------------------------------------------------------------
    // Footer buttons
    // ------------------------------------------------------------------
    get isActionDisabled() {
        return !this.state.selectedId || this.state.isSaving;
    }

    get confirmLabel() {
        if (this.isMove) {
            return this.state.selectedName
                ? _t("Move to %s", this.state.selectedName)
                : _t("Move to");
        }
        return this.state.selectedName
            ? _t("Create a shortcut in %s", this.state.selectedName)
            : _t("Create a shortcut");
    }

    get createFolderLabel() {
        return this.state.selectedName
            ? _t("Create a folder in %s", this.state.selectedName)
            : _t("Create a folder");
    }

    onConfirm() {
        if (this.isActionDisabled) {
            return;
        }
        if (this.isMove) {
            // Announce the access settings the item will take, then move.
            this.dialog.add(DocumentsMoveConfirmDialog, {
                destinationId: this.state.selectedId,
                destinationName: this.state.selectedName,
                onConfirm: () => this._run("action_move", _t("Moved.")),
            });
            return;
        }
        return this._run("action_create_shortcut", _t("Shortcut created."));
    }

    async _run(method, message) {
        this.state.isSaving = true;
        try {
            const result = await this.orm.call(this.props.resModel, method, [
                [this.props.resId],
                this.state.selectedId,
            ]);
            this.notification.add(message, { type: "success" });
            this.props.onDone && this.props.onDone(result);
            this.props.close();
        } catch (error) {
            this.state.isSaving = false;
            throw error;
        }
    }

    onCreateFolder() {
        if (this.isActionDisabled) {
            return;
        }
        this.dialog.add(DocumentsNewFolderDialog, {
            parentFolderId: this.state.selectedId,
            title: _t("Create a folder in %s", this.state.selectedName),
            nameLabel: _t("Name"),
            confirmLabel: _t("Save"),
            onSaved: async (newFolderId) => {
                await this.loadTree();
                if (newFolderId) {
                    this.state.collapsed[this.state.selectedId] = false;
                    const found = this._find(this.state.tree, newFolderId);
                    if (found) {
                        this.select(found);
                    }
                }
            },
        });
    }

    _find(nodes, id) {
        for (const node of nodes) {
            if (node.id === id) {
                return node;
            }
            const inChild = this._find(node.children, id);
            if (inChild) {
                return inChild;
            }
        }
        return null;
    }

    onDiscard() {
        this.props.close();
    }
}
