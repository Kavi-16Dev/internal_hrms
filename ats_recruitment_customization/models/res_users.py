# -*- coding: utf-8 -*-
from odoo import fields, models


class ResUsers(models.Model):
    _inherit = "res.users"

    is_recruitment_offer_approver = fields.Boolean(
        string="Can Approve/Reject Offers",
        help="If enabled, this user will see the Approve and Reject buttons "
        "on applicants in the Offer Submission stage, and will receive the "
        "approval activity whenever a Recruitment User submits an offer.",
    )
