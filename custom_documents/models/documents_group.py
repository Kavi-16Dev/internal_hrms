# -*- coding: utf-8 -*-
from odoo import fields, models


class DocumentsGroup(models.Model):
    """Documents > Configuration > Groups: a named set of users managed by
    one or more responsibles (e.g. "HR Group", "Finance Managers")."""
    _name = 'documents.group'
    _description = 'Documents Group'
    _order = 'name, id'

    name = fields.Char(
        string='Group Name', required=True, translate=True,
        help='Name of the group, e.g. "HR Group".')
    responsible_ids = fields.Many2many(
        'res.users', 'documents_group_responsible_rel', 'group_id', 'user_id',
        string='Group Responsibles',
        default=lambda self: self.env.user,
        domain=[('share', '=', False)],
        help='Users in charge of this group: they manage its members.')
    user_ids = fields.Many2many(
        'res.users', 'documents_group_user_rel', 'group_id', 'user_id',
        string='Users',
        domain=[('share', '=', False)],
        help='Members of the group.')
