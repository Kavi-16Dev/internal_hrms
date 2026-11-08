/** @odoo-module **/

import { Component, onWillStart, useState } from "@odoo/owl";
import { Dialog } from "@web/core/dialog/dialog";
import { useService } from "@web/core/utils/hooks";
import { _t } from "@web/core/l10n/translation";

/**
 * "Info & tags" Actions-menu entry of the list / kanban views: name, tags
 * and details of ONE document (or, read-only, of one workspace).  Same
 * content as the Info panel of the file viewer.
 */
export class DocumentsInfoDialog extends Component {
    static template = "custom_documents.InfoDialog";
    static components = { Dialog };
    static props = {
        resId: { type: Number },
        resModel: { type: String, optional: true }, // documents.document (default) | documents.folder
        onChanged: { type: Function, optional: true },
        close: { type: Function, optional: true },
    };

    setup() {
        this.orm = useService("orm");
        this.title = _t("Info & tags");
        this.isFolder = this.props.resModel === "documents.folder";
        this.state = useState({ loading: true, info: null, name: "" });

        onWillStart(async () => {
            if (this.isFolder) {
                const [data] = await this.orm.read("documents.folder", [this.props.resId], [
                    "name",
                    "parent_folder_id",
                    "folder_type",
                    "document_count",
                ]);
                this.state.info = data;
            } else {
                const [data] = await this.orm.read("documents.document", [this.props.resId], [
                    "name",
                    "folder_id",
                    "owner_id",
                    "partner_id",
                    "tag_ids",
                    "create_date",
                    "file_size",
                    "res_name",
                    "lock_uid",
                ]);
                const allTags = await this.orm.searchRead("documents.tag", [], ["name", "color"]);
                this.state.info = { ...data, allTags };
            }
            this.state.name = this.state.info.name || "";
            this.state.loading = false;
        });
    }

    get model() {
        return this.props.resModel || "documents.document";
    }

    async onNameChange(ev) {
        const newName = ev.target.value.trim();
        if (!newName || newName === this.state.info.name) {
            ev.target.value = this.state.info.name;
            return;
        }
        await this.orm.call(this.model, "action_rename", [[this.props.resId], newName]);
        this.state.info.name = newName;
        this.props.onChanged && this.props.onChanged();
    }

    isTagSelected(tagId) {
        return (this.state.info.tag_ids || []).includes(tagId);
    }

    async onToggleTag(tagId) {
        const current = this.state.info.tag_ids || [];
        const newIds = current.includes(tagId)
            ? current.filter((id) => id !== tagId)
            : [...current, tagId];
        await this.orm.write("documents.document", [this.props.resId], {
            tag_ids: [[6, 0, newIds]],
        });
        this.state.info.tag_ids = newIds;
        this.props.onChanged && this.props.onChanged();
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

    onClose() {
        this.props.close();
    }
}
