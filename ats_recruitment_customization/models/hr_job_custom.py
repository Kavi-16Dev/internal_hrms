from odoo import models, fields, api

class CustomHrJob(models.Model):
    _inherit = 'hr.job'

    working_hours = fields.Char(string="Working Hours")
    leave_eligibility = fields.Char(string="Leave Eligibility")
    # Key_Responsibilities =fields.Html(string="Keys Roles and Responsibilities")
    key_responsibilities =fields.Html(string="Keys Roles and Responsibilities")