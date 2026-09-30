/** @odoo-module **/

import { _t } from "@web/core/l10n/translation";
import { registry } from "@web/core/registry";
import { CopyButton } from "@web/core/copy_button/copy_button";
import { Component } from "@odoo/owl";
import { standardFieldProps } from "@web/views/fields/standard_field_props";

export class KaviEmailTrackerField extends Component {
    static template = "kavi_hr_job_custom.KaviEmailTrackerField";
    static components = { CopyButton };

    static props = {
        ...standardFieldProps,
        trackingUrlField: { type: String, optional: true },
    };

    get emailValue() {
        return this.props.record.data[this.props.name] || "";
    }

    get trackingUrl() {
        const fieldName = this.props.trackingUrlField || "email_url";
        return this.props.record.data[fieldName] || "";
    }

    get hasValue() {
        return Boolean(this.emailValue);
    }

    get displayLabel() {
        // The Tracker/Vendors UI intentionally shows the same label as
        // Odoo's standard Email tracker: "Email".  The actual generated
        // tracking URL remains the href and the value copied by the
        // link icon.
        return _t("Email");
    }

    get hasTrackingUrl() {
        return Boolean(this.trackingUrl);
    }

    get copyContent() {
        return this.trackingUrl.replace(/^mailto:/i, "");
    }

    get copySuccessText() {
        return _t("Copied");
    }
}

export const kaviEmailTrackerField = {
    component: KaviEmailTrackerField,
    displayName: _t("Kavi Email Tracker"),
    supportedTypes: ["char"],
    extractProps: ({ options }) => ({
        trackingUrlField: options.tracking_url_field || "email_url",
    }),
};

registry.category("fields").add("kavi_email_tracker", kaviEmailTrackerField);
