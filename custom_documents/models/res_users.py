# -*- coding: utf-8 -*-
from odoo import api, fields, models


class ResUsers(models.Model):
    _inherit = 'res.users'

    document_folder_id = fields.Many2one(
        'documents.folder', string='My Drive', compute='_compute_document_folder_id')

    def _compute_document_folder_id(self):
        Folder = self.env['documents.folder']
        for user in self:
            user.document_folder_id = Folder._get_or_create_employee_drive(user)

    def action_open_my_drive(self):
        self.ensure_one()
        folder = self.env['documents.folder']._get_or_create_employee_drive(self)
        return folder.action_open_documents()
