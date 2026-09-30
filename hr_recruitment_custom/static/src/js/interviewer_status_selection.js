/** @odoo-module **/

import { SelectionField, selectionField } from "@web/views/fields/selection/selection_field";
import { registry } from "@web/core/registry";


/**
 * Interviewer Status Selection
 *
 * This widget intentionally reuses Odoo's SelectionField UI. The only
 * difference is the label source:
 *
 *   normal  -> record.data.legend_normal
 *   blocked -> record.data.legend_blocked
 *   waiting -> record.data.legend_waiting
 *   done    -> record.data.legend_done
 *   hold_2  -> record.data.legend_hold_2
 *
 * The record already contains these fields because they are present in the
 * applicant form (the fifth one is added by this module as an invisible
 * field). Therefore, changing a Stage Tooltip immediately changes the label
 * displayed by Interviewer Status without changing the field's type or value.
 */
export class InterviewerStatusSelectionField extends SelectionField {
    static template = SelectionField.template;
    static components = SelectionField.components;
    static props = SelectionField.props;
    static defaultProps = SelectionField.defaultProps;

    get options() {
        if (this.type !== "selection") {
            return super.options;
        }

        const baseOptions = super.options;
        return baseOptions.map(([value, label]) => {
            const legend = this.props.record.data[`legend_${value}`];
            return [value, legend || label];
        });
    }
}

export const interviewerStatusSelectionField = {
    ...selectionField,
    component: InterviewerStatusSelectionField,
    displayName: "Interviewer Status Selection",
};

registry.category("fields").add(
    "interviewer_status_selection",
    interviewerStatusSelectionField
);
