# -*- coding: utf-8 -*-
from odoo import fields, models


class DocumentsTag(models.Model):
    _name = 'documents.tag'
    _description = 'Document Tag'
    _order = 'sequence, name'

    name = fields.Char(required=True, translate=True)
    sequence = fields.Integer(default=10)
    color = fields.Integer(string='Color Index')
    category_id = fields.Many2one(
        'documents.tag.category', string='Category', ondelete='cascade')
    document_ids = fields.Many2many('documents.document', string='Documents')

    _sql_constraints = [
        ('name_category_uniq', 'unique(name, category_id)',
         'This tag already exists in this category.'),
    ]
