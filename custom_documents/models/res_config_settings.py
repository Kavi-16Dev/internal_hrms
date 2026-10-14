# -*- coding: utf-8 -*-
from odoo import api, fields, models


class ResConfigSettings(models.TransientModel):
    _inherit = 'res.config.settings'

    # ------------------------------------------------------------------
    # Existing settings
    # ------------------------------------------------------------------
    documents_share_default_validity = fields.Integer(
        string='Default Share Link Validity (days)',
        config_parameter='custom_documents.share_default_validity',
        default=7,
        help='Number of days a new share link stays active by default. '
             'Set to 0 for links that never expire by default.')

    documents_request_default_deadline = fields.Integer(
        string='Default Request Deadline (days)',
        config_parameter='custom_documents.request_default_deadline',
        default=15,
        help='Default number of days given to a colleague or contact to '
             'fulfil a document request.')

    documents_spreadsheet_folder_id = fields.Many2one(
        'documents.folder', string='Spreadsheet Templates Workspace',
        config_parameter='custom_documents.spreadsheet_folder_id',
        help='Workspace browsed by default from '
             'Configuration > Spreadsheet Templates.')

    # ------------------------------------------------------------------
    # Trash Management
    # ------------------------------------------------------------------
    documents_deletion_delay = fields.Integer(
        related='company_id.documents_deletion_delay', readonly=False,
        string='Deletion Delay (days)')

    # ------------------------------------------------------------------
    # Files Centralization
    # ------------------------------------------------------------------
    documents_project_folder_id = fields.Many2one(
        related='company_id.documents_project_folder_id', readonly=False,
        string='Default Project Folder')

    documents_hr_settings = fields.Boolean(
        related='company_id.documents_hr_settings', readonly=False)
    documents_hr_folder_id = fields.Many2one(
        related='company_id.documents_hr_folder_id', readonly=False,
        string='Employees Folder')
    documents_hr_subfolders = fields.Boolean(
        related='company_id.documents_hr_subfolders', readonly=False,
        string='Employees Subfolders')
    documents_hr_contract_tag_ids = fields.Many2many(
        related='company_id.documents_hr_contract_tag_ids', readonly=False,
        string='Contracts')
    documents_hr_payslip_tag_ids = fields.Many2many(
        related='company_id.documents_hr_payslip_tag_ids', readonly=False,
        string='Payslip')

    documents_product_settings = fields.Boolean(
        related='company_id.documents_product_settings', readonly=False)
    documents_product_folder_id = fields.Many2one(
        related='company_id.documents_product_folder_id', readonly=False,
        string='Product Folder')

    documents_account_settings = fields.Boolean(
        related='company_id.documents_account_settings', readonly=False)
    documents_account_folder_id = fields.Many2one(
        related='company_id.documents_account_folder_id', readonly=False,
        string='Finance Folder')

    documents_approval_settings = fields.Boolean(
        related='company_id.documents_approval_settings', readonly=False)
    documents_approval_folder_id = fields.Many2one(
        related='company_id.documents_approval_folder_id', readonly=False,
        string='Approvals Folder')
    documents_approval_tag_ids = fields.Many2many(
        related='company_id.documents_approval_tag_ids', readonly=False,
        string='Approvals Tags')

    documents_fleet_settings = fields.Boolean(
        related='company_id.documents_fleet_settings', readonly=False)
    documents_fleet_folder_id = fields.Many2one(
        related='company_id.documents_fleet_folder_id', readonly=False,
        string='Fleet Folder')
    documents_fleet_tag_ids = fields.Many2many(
        related='company_id.documents_fleet_tag_ids', readonly=False,
        string='Fleet Tags')

    documents_recruitment_settings = fields.Boolean(
        related='company_id.documents_recruitment_settings', readonly=False)
    documents_recruitment_folder_id = fields.Many2one(
        related='company_id.documents_recruitment_folder_id', readonly=False,
        string='Recruitment Folder')
    documents_recruitment_tag_ids = fields.Many2many(
        related='company_id.documents_recruitment_tag_ids', readonly=False,
        string='Recruitment Tags')

    # ------------------------------------------------------------------
    # Flags used purely to show/hide a Files Centralization block
    # depending on which apps are actually installed on this database.
    # Kept soft (no manifest 'depends') so the module stays installable
    # on a bare Community setup with only base/mail/portal/hr.
    # ------------------------------------------------------------------
    documents_project_installed = fields.Boolean(
        compute='_compute_documents_installed_apps')
    documents_product_installed = fields.Boolean(
        compute='_compute_documents_installed_apps')
    documents_account_installed = fields.Boolean(
        compute='_compute_documents_installed_apps')
    documents_approval_installed = fields.Boolean(
        compute='_compute_documents_installed_apps')
    documents_fleet_installed = fields.Boolean(
        compute='_compute_documents_installed_apps')
    documents_sign_installed = fields.Boolean(
        compute='_compute_documents_installed_apps')
    documents_recruitment_installed = fields.Boolean(
        compute='_compute_documents_installed_apps')

    def _compute_documents_installed_apps(self):
        installed = set(self.env['ir.module.module'].sudo().search([
            ('name', 'in', ['project', 'product', 'account', 'approvals',
                             'fleet', 'sign', 'custom_sign', 'hr_recruitment']),
            ('state', '=', 'installed'),
        ]).mapped('name'))
        for record in self:
            record.documents_project_installed = 'project' in installed
            record.documents_product_installed = 'product' in installed
            record.documents_account_installed = 'account' in installed
            record.documents_approval_installed = 'approvals' in installed
            record.documents_fleet_installed = 'fleet' in installed
            record.documents_sign_installed = bool(
                {'sign', 'custom_sign'} & installed)
            record.documents_recruitment_installed = 'hr_recruitment' in installed

    def action_open_sign_templates(self):
        """Best-effort shortcut to the Sign templates list, whichever Sign
        implementation (Enterprise 'sign' or the custom 'custom_sign'
        module) happens to be installed."""
        self.ensure_one()
        for xml_id in ('custom_sign.action_csign_template',
                        'sign.sign_template_action'):
            action = self.env.ref(xml_id, raise_if_not_found=False)
            if action:
                return action.sudo().read()[0]
        return {'type': 'ir.actions.act_window_close'}
