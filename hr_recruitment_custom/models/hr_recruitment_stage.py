# -*- coding: utf-8 -*-
from odoo import fields, models, _


class HrRecruitmentStage(models.Model):
    _inherit = "hr.recruitment.stage"

    legend_hold_2 = fields.Char(
        string="New Status",
        default=lambda self: _("New Status"),
        translate=True,
        required=True,
        readonly=False,
        copy=True,
        help="Custom fifth kanban label shown in the Recruitment stage tooltips.",
    )

