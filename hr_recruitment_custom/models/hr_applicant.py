# -*- coding: utf-8 -*-
from odoo import _, api, fields, models


class HrApplicant(models.Model):
    _inherit = "hr.applicant"

    kanban_state = fields.Selection(
        selection_add=[("hold_2", "New Status")],
        ondelete={"hold_2": "set default"},
        string="Status",
    )

    # The standard Odoo applicant form already exposes the four built-in
    # stage tooltip labels (legend_normal, legend_blocked, legend_waiting,
    # legend_done). This related field exposes the fifth tooltip label to the
    # client as well, so the custom Interviewer Status widget can use it.
    legend_hold_2 = fields.Char(
        related="stage_id.legend_hold_2",
        string="Kanban New Status Explanation",
        readonly=True,
    )

    waiting_rot_activity_created = fields.Boolean(
        string="Waiting Rot Activity Created",
        default=False,
        copy=False,
        index=True,
        help="Technical flag: a 'waiting too long' activity was already created "
             "for the current waiting period. Reset when Status or Stage changes.",
    )

    @api.onchange("stage_id")
    def _onchange_stage_id_sync_kanban_state(self):
        """Reset Interviewer Status to the selected stage's normal status.

        The status value is a state key (normal/blocked/waiting/done/hold_2).
        Its displayed label is supplied dynamically by the selected stage's
        tooltip fields in the client-side Interviewer Status widget.
        """
        for applicant in self:
            applicant.kanban_state = "normal"

    def write(self, vals):
        """Keep Interviewer Status consistent whenever Stage changes."""
        if vals.get("stage_id"):
            vals = dict(vals, kanban_state="normal")
        if "kanban_state" in vals or "stage_id" in vals:
            # A new waiting period starts: allow one new activity.
            vals = dict(vals, waiting_rot_activity_created=False)
        return super().write(vals)

    @api.model_create_multi
    def create(self, vals_list):
        """Initialize new applicants in the selected stage's normal status."""
        for vals in vals_list:
            if vals.get("stage_id"):
                vals["kanban_state"] = "normal"
        return super().create(vals_list)

    @api.model
    def _cron_create_waiting_rot_activity(self):
        """Create ONE activity for the Responsible (user_id) when an applicant
        is in Waiting status and has stayed longer than its current stage's
        "Days to Rot" (rotting_threshold_days).

        Works for any stage. Uses Odoo's own ``is_rotting`` computation, which
        already ignores stages with threshold 0 and closed/refused applicants,
        and counts days from ``date_last_stage_update`` (reset by Odoo whenever
        the stage or the Status changes).
        """
        applicants = self.search([
            ("kanban_state", "=", "waiting"),
            ("is_rotting", "=", True),
            ("waiting_rot_activity_created", "=", False),
            ("user_id", "!=", False),
        ])
        for applicant in applicants:
            stage = applicant.stage_id
            applicant.activity_schedule(
                "mail.mail_activity_data_todo",
                date_deadline=fields.Date.context_today(applicant),
                user_id=applicant.user_id.id,
                summary=_("Applicant waiting too long"),
                note=_(
                    "Applicant %(name)s has been in Waiting status for %(days)s day(s) "
                    "in stage %(stage)s, which exceeds its Days to Rot (%(threshold)s).",
                    name=applicant.display_name,
                    days=applicant.rotting_days,
                    stage=stage.name,
                    threshold=stage.rotting_threshold_days,
                ),
            )
            applicant.waiting_rot_activity_created = True
        return True
