# -*- coding: utf-8 -*-
from odoo import fields, models


class DocumentsTagCategory(models.Model):
    _name = 'documents.tag.category'
    _description = 'Document Tag Category'
    _order = 'sequence, name'

    name = fields.Char(required=True, translate=True)
    sequence = fields.Integer(default=10)
    tag_ids = fields.One2many('documents.tag', 'category_id', string='Tags')
    folder_id = fields.Many2one(
        'documents.folder', string='Workspace',
        help='If set, this category of tags only applies to this folder '
             'and its sub-folders.')

    _sql_constraints = [
        ('name_uniq', 'unique(name, folder_id)',
         'A tag category with this name already exists in this workspace.'),
    ]
