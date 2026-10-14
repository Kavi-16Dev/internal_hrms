# -*- coding: utf-8 -*-
from odoo import api, fields, models, _


class HrEmployee(models.Model):
    _inherit = 'hr.employee'

    document_folder_id = fields.Many2one(
        'documents.folder', string='Documents Folder',
        compute='_compute_document_folder_id')
    document_count = fields.Integer(
        string='Document Count', compute='_compute_document_count')

    def _compute_document_folder_id(self):
        for employee in self:
            employee.document_folder_id = employee._get_documents_hr_folder(create=False)

    @api.depends('document_folder_id')
    def _compute_document_count(self):
        Document = self.env['documents.document'].sudo()
        is_manager = self.env.user.has_group(
            'custom_documents.group_documents_manager')
        for employee in self:
            if not is_manager and employee.user_id != self.env.user:
                employee.document_count = 0
                continue
            folder = employee.document_folder_id.sudo()
            employee.document_count = Document.search_count([
                ('folder_id', 'child_of', folder.id),
                ('active', '=', True),
                ('type', '=', 'binary'),
                ('attachment_id', '!=', False),
            ]) if folder else 0

    # def _get_documents_hr_folder(self, create=True):
    #     """Return the employee's centralized HR Documents folder.

    #     The reference flow does not depend on the employee having an Odoo
    #     user: every employee gets a folder below the configured Employees
    #     workspace.  When a linked user exists, that user is added as a folder
    #     member so the employee can see the folder and its files in
    #     ``Shared with me``.
    #     """
    #     self.ensure_one()
    #     company = self.company_id or self.env.company
    #     Folder = self.env['documents.folder'].sudo()

    #     # Employee Documents must always have a private employee folder.
    #     # Use the configured HR Employees folder when centralization is
    #     # enabled; otherwise fall back to the Company's Documents Drive so
    #     # the Employee > Documents button still works without requiring a
    #     # separate configuration switch.
    #     parent = company.documents_hr_folder_id if (
    #         company.documents_hr_settings and company.documents_hr_folder_id
    #     ) else Folder._get_or_create_company_drive(company)
    #     folder = Folder.search([
    #         ('employee_id', '=', self.id),
    #         ('company_id', '=', company.id),
    #     ], limit=1)

    #     # Backward compatibility for folders created by versions before the
    #     # explicit employee_id link existed.
    #     if not folder and self.user_id:
    #         folder = Folder.search([
    #             ('parent_folder_id', '=', parent.id),
    #             ('folder_type', '=', 'custom'),
    #             ('user_id', '=', self.user_id.id),
    #             ('company_id', '=', company.id),
    #         ], limit=1)
    #         if folder:
    #             folder.write({'employee_id': self.id})

    #     if not folder and create:
    #         folder = Folder.create({
    #             'name': self.name,
    #             'folder_type': 'custom',
    #             'parent_folder_id': parent.id,
    #             'user_id': self.user_id.id if self.user_id else False,
    #             'employee_id': self.id,
    #             'company_id': company.id,
    #             'member_ids': [(4, self.user_id.id)] if self.user_id else [],
    #         })

    #     if not folder:
    #         return folder

    #     # Keep the folder name synchronized with the employee record without
    #     # changing any manually created non-HR workspaces.
    #     if folder.parent_folder_id.id != parent.id:
    #         folder.write({'parent_folder_id': parent.id})
    #     if folder.name != self.name:
    #         folder.write({'name': self.name})

    #     if self.user_id and self.user_id not in folder.member_ids:
    #         folder.write({'member_ids': [(4, self.user_id.id)]})

    #     if create:
    #         self._ensure_documents_hr_contract_folder(folder, company)
    #     return folder

    def _get_documents_hr_folder(self, create=True):
        self.ensure_one()
        company = self.company_id or self.env.company
        Folder = self.env['documents.folder'].sudo()

        parent = company.documents_hr_folder_id if (
            company.documents_hr_settings and company.documents_hr_folder_id
        ) else Folder._get_or_create_company_drive(company)

        # Only the dedicated root folder is a candidate here - NOT any
        # employee-linked child folder such as Contracts.
        folder = Folder.search([
            ('employee_id', '=', self.id),
            ('is_employee_root', '=', True),
        ], limit=1)

        if not folder and self.user_id:
            folder = Folder.search([
                ('folder_type', '=', 'custom'),
                ('user_id', '=', self.user_id.id),
                ('employee_id', '=', False),
            ], limit=1)
            if folder:
                folder.write({'employee_id': self.id, 'is_employee_root': True})

        if not folder and create:
            folder = Folder.create({
                'name': self.name,
                'folder_type': 'custom',
                'parent_folder_id': parent.id,
                'user_id': self.user_id.id if self.user_id else False,
                'employee_id': self.id,
                'company_id': company.id,
                'is_employee_root': True,           # <-- mark it
                'member_ids': [(4, self.user_id.id)] if self.user_id else [],
            })

        if not folder:
            return folder

        update_vals = {}
        if folder.parent_folder_id.id != parent.id:
            update_vals['parent_folder_id'] = parent.id
        if folder.company_id.id != company.id:
            update_vals['company_id'] = company.id
        if folder.name != self.name:
            update_vals['name'] = self.name
        if update_vals:
            folder.write(update_vals)

        if self.user_id and self.user_id not in folder.member_ids:
            folder.write({'member_ids': [(4, self.user_id.id)]})

        if create:
            self._ensure_documents_hr_contract_folder(folder, company)
        return folder

    def _ensure_documents_hr_contract_folder(self, employee_folder, company):
        """Create the Contracts child shown inside every employee folder."""
        self.ensure_one()
        Folder = self.env['documents.folder'].sudo()
        contracts = Folder.search([
            ('parent_folder_id', '=', employee_folder.id),
            ('company_id', '=', company.id),
            ('name', '=', _('Contracts')),
            ('active', '=', True),
        ], limit=1)
        if not contracts:
            contracts = Folder.create({
                'name': _('Contracts'),
                'folder_type': 'custom',
                'parent_folder_id': employee_folder.id,
                'employee_id': self.id,
                'company_id': company.id,
            })
        elif contracts.employee_id != self:
            # Keep the standard Contracts subfolder inside the same employee
            # security boundary as its parent folder.
            contracts.write({'employee_id': self.id})
        return contracts

    @api.model_create_multi
    def create(self, vals_list):
        employees = super().create(vals_list)
        for employee in employees:
            employee._get_documents_hr_folder(create=True)
        return employees

    def write(self, vals):
        result = super().write(vals)
        if any(key in vals for key in ('name', 'user_id', 'company_id')):
            for employee in self:
                employee._get_documents_hr_folder(create=True)
        return result

    def action_view_documents(self):
        self.ensure_one()
        folder = self._get_documents_hr_folder(create=True)
        domain = [('folder_id', 'child_of', folder.id)] if folder else \
            [('res_model', '=', 'hr.employee'), ('res_id', '=', self.id)]
        return {
            'type': 'ir.actions.act_window',
            'name': _('Documents'),
            'res_model': 'documents.document',
            'view_mode': 'kanban,list,form',
            'domain': domain,
            'context': {
                'default_folder_id': folder.id,
                'documents_folder_id': folder.id,
                'documents_sidebar_category': 'company',
            } if folder else {},
            'target': 'current',
        }
