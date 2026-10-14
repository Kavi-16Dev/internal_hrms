# -*- coding: utf-8 -*-
from odoo import api, fields, models


class ResCompany(models.Model):
    _inherit = 'res.company'

    document_company_folder_id = fields.Many2one(
        'documents.folder', string='Company Drive',
        compute='_compute_document_company_folder_id')

    # ------------------------------------------------------------------
    # Trash Management
    # ------------------------------------------------------------------
    documents_deletion_delay = fields.Integer(
        string='Deletion Delay (days)', default=30,
        help='Time before documents in the Trash are permanently deleted.')

    # ------------------------------------------------------------------
    # Files Centralization
    # ------------------------------------------------------------------
    # -- Default Project Folder (only meaningful if the Project app is
    #    installed; the field itself has no hard dependency on it).
    documents_project_folder_id = fields.Many2one(
        'documents.folder', string='Default Project Folder',
        help='Folder where new projects are created.')

    # -- Human Resources ------------------------------------------------
    documents_hr_settings = fields.Boolean(string='Centralize HR Documents')
    documents_hr_folder_id = fields.Many2one(
        'documents.folder', string='Employees Folder',
        help='Centralize your employees\' documents (contracts, payslips, etc.)')
    documents_hr_subfolders = fields.Boolean(
        string='Employees Subfolders', default=True,
        help='Automatically create a private subfolder for every employee '
             'inside the Employees Folder.')
    documents_hr_contract_tag_ids = fields.Many2many(
        'documents.tag', 'documents_company_hr_contract_tag_rel',
        'company_id', 'tag_id', string='Contracts',
        help='Tags automatically applied to employee contract documents.')
    documents_hr_payslip_tag_ids = fields.Many2many(
        'documents.tag', 'documents_company_hr_payslip_tag_rel',
        'company_id', 'tag_id', string='Payslip',
        help='Tags automatically applied to employee payslip documents.')

    # -- Product ----------------------------------------------------------
    documents_product_settings = fields.Boolean(string='Centralize Product Documents')
    documents_product_folder_id = fields.Many2one(
        'documents.folder', string='Product Folder',
        help='Centralize files attached to products.')

    # -- Accounting ---------------------------------------------------------
    documents_account_settings = fields.Boolean(
        string='Centralize Accounting Documents', default=True)
    documents_account_folder_id = fields.Many2one(
        'documents.folder', string='Finance Folder',
        help='Centralize accounting files and documents.')

    # -- Approvals ----------------------------------------------------------
    documents_approval_settings = fields.Boolean(
        string='Centralize Approval Documents', default=True)
    documents_approval_folder_id = fields.Many2one(
        'documents.folder', string='Approvals Folder',
        help='Centralize files attached to Approvals.')
    documents_approval_tag_ids = fields.Many2many(
        'documents.tag', 'documents_company_approval_tag_rel',
        'company_id', 'tag_id', string='Approvals Tags')

    # -- Fleet ----------------------------------------------------------
    documents_fleet_settings = fields.Boolean(
        string='Centralize Fleet Documents', default=True)
    documents_fleet_folder_id = fields.Many2one(
        'documents.folder', string='Fleet Folder',
        help='Centralize your Fleet\' documents (fines, etc.)')
    documents_fleet_tag_ids = fields.Many2many(
        'documents.tag', 'documents_company_fleet_tag_rel',
        'company_id', 'tag_id', string='Fleet Tags')

    # -- Recruitment ------------------------------------------------------
    documents_recruitment_settings = fields.Boolean(
        string='Centralize Recruitment Documents', default=True)
    documents_recruitment_folder_id = fields.Many2one(
        'documents.folder', string='Recruitment Folder',
        help='Centralize resumes and other recruitment documents. The '
             '"Create an Applicant" action is only available on files '
             'stored in this workspace (or one of its sub-folders). '
             'Leave empty to allow it on any file.')
    documents_recruitment_tag_ids = fields.Many2many(
        'documents.tag', 'documents_company_recruitment_tag_rel',
        'company_id', 'tag_id', string='Recruitment Tags')

    @api.depends()
    def _compute_document_company_folder_id(self):
        Folder = self.env['documents.folder']
        for company in self:
            company.document_company_folder_id = Folder._get_or_create_company_drive(company)
