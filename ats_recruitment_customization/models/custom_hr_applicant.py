from odoo import models, fields, api

class CustomHrApplicant(models.Model):
    _inherit = 'hr.applicant'

    offer_date = fields.Date(string="Offer Date")
    joining_date = fields.Date(string="Joining Date")
    job_address = fields.Char(string="Job address")
    # company_name = fields.Char(string="Company Name")
    # manager_name = fields.Char(string="Manager Name")
    salary_structure = fields.Html(string="Salary Structure")
    # roles_responsibilities = fields.Html(string="Roles & Responsibilities")
    salary_note = fields.Html(string="Note")

    # compensation = fields.Char(string="Compensation")
    # medical_retirement_benefits = fields.Char(string="Medical Insurance and Retirement Benefits")
    # reimbursement_of_expenses = fields.Char(string="Reimbursement of Expenses")
    # terms_and_conditions = fields.Html(string="General Terms and Conditions")
    # right_to_transfer = fields.Char(string="Right to Transfer etc")
    # company_policies = fields.Char(string="Adherence to Company’s Policies")
    # maintain_confidentiality = fields.Char(string="Maintain Confidentiality")

   