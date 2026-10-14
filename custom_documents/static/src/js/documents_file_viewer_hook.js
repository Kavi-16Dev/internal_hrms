/** @odoo-module **/

import { useService } from "@web/core/utils/hooks";
import { DocumentsFileViewer } from "./documents_file_viewer";

/**
 * Whether a documents.document record should open in the full-screen
 * preview instead of falling back to the classic form view: it needs
 * an actual file attached, or to be a "Link" document. Placeholder
 * documents that are still waiting to be uploaded ("Requested") keep
 * opening the form, since that's where the "Mark Fulfilled" / upload
 * widget lives.
 *
 * @param {Object} data record.data of a documents.document datapoint
 * @returns {boolean}
 */
export function isDocumentPreviewable(data) {
    if (!data || data.state === "requested") {
        return false;
    }
    if (data.type === "url") {
        return !!data.url;
    }
    return !!getAttachmentId(data);
}

/**
 * Many2one fields on record.data come through as an {id, display_name}
 * object in Odoo's relational model - not the legacy [id, name] array.
 * This reads the id defensively so it keeps working either way.
 *
 * @param {Object} data record.data of a documents.document datapoint
 * @returns {number|false}
 */
function getAttachmentId(data) {
    const value = data && data.attachment_id;
    if (!value) {
        return false;
    }
    if (Array.isArray(value)) {
        return value[0] || false;
    }
    return value.id || false;
}

/**
 * Hook giving the Documents kanban/list controllers a way to open the
 * full-screen file viewer for a clicked record, and to page through
 * every other previewable record currently loaded in the view (arrow
 * keys / nav arrows), the way Odoo's own Documents app behaves.
 *
 * @param {Component} component the owning view controller (must expose
 *  `component.model.root.records`)
 */
export function useDocumentsFileViewer(component) {
    const dialogService = useService("dialog");
    const notification = useService("notification");

    return {
        isPreviewable: isDocumentPreviewable,

        open(record) {
            try {
                const allRecords = component.model.root.records;
                const previewRecords = allRecords
                    .filter((rec) => isDocumentPreviewable(rec.data))
                    .map((rec) => ({
                        id: rec.resId,
                        name: rec.data.name || "",
                        mimetype: rec.data.mimetype || false,
                        type: rec.data.type || "binary",
                        url: rec.data.url || false,
                        state: rec.data.state || "uploaded",
                        active: rec.data.active !== false,
                        attachmentId: getAttachmentId(rec.data),
                        showCreateApplicant: !!rec.data.show_create_applicant,
                        lockUid: rec.data.lock_uid || false,
                    }));

                if (!previewRecords.length) {
                    // Nothing in the currently loaded set is previewable
                    // (shouldn't happen since we just checked this record,
                    // but guards against a stale/filtered model root).
                    console.warn(
                        "[custom_documents] No previewable records found; falling back."
                    );
                    return false;
                }

                const startIndex = Math.max(
                    previewRecords.findIndex((rec) => rec.id === record.resId),
                    0
                );
                dialogService.add(DocumentsFileViewer, {
                    records: previewRecords,
                    startIndex,
                    reload: () => component.model.load(),
                });
                return true;
            } catch (error) {
                // Never fail silently: log the real error and tell the
                // user something broke, instead of the click doing
                // nothing with no explanation.
                console.error("[custom_documents] Failed to open file viewer:", error);
                notification.add(
                    `Could not open the preview (${error.message || error}). ` +
                        "Opening the record form instead.",
                    { type: "warning", sticky: true }
                );
                return false;
            }
        },
    };
}
