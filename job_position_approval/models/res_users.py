# -*- coding: utf-8 -*-
from odoo import fields, models


class customResUsers(models.Model):
    _inherit = 'res.users'

    job_position_approver = fields.Boolean(
        string="Job Position Approver",
        help="If checked, this user acts as Recruitment Administrator and can "
             "Approve/Reject, Close (Unpublish) and Archive Job Positions.",
    )
