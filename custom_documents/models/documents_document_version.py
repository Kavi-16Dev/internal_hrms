# -*- coding: utf-8 -*-
from odoo import api, fields, models, _
from odoo.exceptions import UserError


class DocumentsDocumentVersion(models.Model):
    _name = 'documents.document.version'
    _description = 'Document Version'
    _order = 'create_date desc, id desc'
    _rec_name = 'name'

    document_id = fields.Many2one(
        'documents.document', string='Document', required=True,
        ondelete='cascade', index=True)
    attachment_id = fields.Many2one(
        'ir.attachment', string='File Snapshot', required=True,
        ondelete='cascade')
    name = fields.Char(related='attachment_id.name', string='File Name')
    file_size = fields.Integer(related='attachment_id.file_size', string='Size')

    def action_restore(self):
        """'Restore' button of the Manage Versions dialog: put this
        snapshot's content back on the parent document, after first
        snapshotting whatever is on the document right now (so restoring
        is itself reversible, and no version is ever lost)."""
        self.ensure_one()
        document = self.document_id
        if document.attachment_id:
            document._snapshot_version()
            document.attachment_id.write({
                'datas': self.attachment_id.datas,
                'name': self.attachment_id.name,
            })
        else:
            raise UserError(_('This document no longer has a file to restore onto.'))
        return True
