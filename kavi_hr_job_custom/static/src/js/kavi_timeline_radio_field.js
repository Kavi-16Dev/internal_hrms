/** @odoo-module **/

import { registry } from "@web/core/registry";
import { Component, onWillStart, onWillUpdateProps, useState } from "@odoo/owl";
import { standardFieldProps } from "@web/views/fields/standard_field_props";
import { useService } from "@web/core/utils/hooks";

// Small fixed palette so each user gets a stable-ish colored avatar badge
// without needing to store a color anywhere.
const AVATAR_COLORS = ["#6f42c1", "#0d6efd", "#20c997", "#fd7e14", "#e83e8c", "#198754", "#6610f2"];

function colorForUserId(userId) {
    const n = Math.abs(userId || 0);
    return AVATAR_COLORS[n % AVATAR_COLORS.length];
}

/**
 * Many2one field values can show up in `record.data` either as the
 * classic [id, display_name] tuple, or (depending on the Odoo version /
 * how the value got there) as a Record-like object exposing `.id`. Also
 * tolerate an already-bare integer id, just in case. Returns `false` for
 * any falsy/unset value, exactly like the tuple form did.
 */
function extractRelationId(value) {
    if (!value) {
        return false;
    }
    if (Array.isArray(value)) {
        return value[0];
    }
    if (typeof value === "object") {
        return "id" in value ? value.id : false;
    }
    return value;
}

/**
 * Renders a many2one field (history_id on the Version History wizards) as
 * a vertical timeline: a connecting line, a dot per entry (filled/caret
 * for the selected one, hollow for the rest), the change's date/time, and
 * a colored initial-letter avatar badge for who made the change - matches
 * the "Task Description History" reference image.
 *
 * Fetches its own option list (date + user) directly via ORM instead of
 * relying on name_get, so it isn't affected by how the target model's
 * display name happens to be built.
 */
export class KaviTimelineRadioField extends Component {
    static template = "kavi_hr_job_custom.TimelineRadioField";
    static props = { ...standardFieldProps };

    setup() {
        this.orm = useService("orm");
        this.state = useState({ options: [] });
        onWillStart(() => this.loadOptions(this.props));
        onWillUpdateProps((nextProps) => this.loadOptions(nextProps));
    }

    _parentDomain(props) {
        // Works for both hr.job.version.history.wizard (job_id) and
        // hr.applicant.version.history.wizard (applicant_id) without
        // needing a separate widget per model.
        const data = props.record.data;
        const domain = [];
        const jobId = extractRelationId(data.job_id);
        const applicantId = extractRelationId(data.applicant_id);
        if (jobId) {
            domain.push(["job_id", "=", jobId]);
        } else if (applicantId) {
            domain.push(["applicant_id", "=", applicantId]);
        }
        if (data.snapshot_field_name) {
            domain.push(["field_name", "=", data.snapshot_field_name]);
        }
        return domain;
    }

    async loadOptions(props) {
        const relationField = props.record.fields[props.name];
        if (!relationField || !relationField.relation) {
            this.state.options = [];
            return;
        }
        const domain = this._parentDomain(props);
        if (!domain.length) {
            this.state.options = [];
            return;
        }
        try {
            const records = await this.orm.searchRead(
                relationField.relation,
                domain,
                ["field_label", "changed_on", "changed_by"],
                { order: "changed_on desc, id desc" }
            );
            this.state.options = records.map((rec) => {
                const changedById = extractRelationId(rec.changed_by);
                const userName = Array.isArray(rec.changed_by) ? rec.changed_by[1] : "";
                return {
                    id: rec.id,
                    dateLabel: this._formatDate(rec.changed_on),
                    userName: userName,
                    initial: userName ? userName.charAt(0).toUpperCase() : "?",
                    color: colorForUserId(changedById || 0),
                };
            });
        } catch (err) {
            // Never let a failed fetch silently masquerade as "no
            // history exists" - that is exactly what made this widget
            // look broken (showing "No recorded changes yet.") for
            // records that actually DO have matching history rows.
            /* eslint-disable-next-line no-console */
            console.error("kavi_hr_job_custom: failed to load version history timeline", err);
            this.state.options = [];
        }
    }

    _formatDate(value) {
        if (!value) {
            return "";
        }
        // Server datetimes come back as "YYYY-MM-DD HH:MM:SS" in UTC.
        const parsed = new Date(value.replace(" ", "T") + "Z");
        if (isNaN(parsed.getTime())) {
            return value;
        }
        const datePart = parsed.toLocaleDateString(undefined, {
            month: "2-digit", day: "2-digit", year: "numeric",
        });
        const timePart = parsed.toLocaleTimeString(undefined, {
            hour: "2-digit", minute: "2-digit", second: "2-digit", hour12: true,
        });
        return `${datePart} ${timePart}`;
    }

    get selectedId() {
        const value = this.props.record.data[this.props.name];
        return extractRelationId(value);
    }

    /**
     * Three-state timeline, matching the "Task Description History"
     * reference: entries newer than the selected one are "done" (a
     * filled checkmark - you've already moved past them going down the
     * list), the selected entry is "current" (the caret), and entries
     * older than the selected one are "pending" (a hollow dash - not
     * reached yet). state.options is newest-first (order: "changed_on
     * desc, id desc" above), so this is a straight index comparison
     * against the selected row's position in that same list.
     */
    rowState(optId) {
        const selectedIndex = this.state.options.findIndex((o) => o.id === this.selectedId);
        const rowIndex = this.state.options.findIndex((o) => o.id === optId);
        if (selectedIndex === -1 || rowIndex === -1) {
            return "pending";
        }
        if (rowIndex < selectedIndex) {
            return "done";
        }
        if (rowIndex === selectedIndex) {
            return "current";
        }
        return "pending";
    }

    onSelect(id) {
        if (id === this.selectedId) {
            return;
        }
        this.props.record.update({ [this.props.name]: [id, ""] });
    }
}

registry.category("fields").add("kavi_timeline_radio", {
    component: KaviTimelineRadioField,
    supportedTypes: ["many2one"],
});
