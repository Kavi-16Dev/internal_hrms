from odoo import models, fields, api


class ApprovalGroup(models.Model):
    _name = 'ml.approval.group'
    _description = 'Approval Group'
    _order = 'sequence, id'

    name = fields.Char(string='Group Name', required=True)
    sequence = fields.Integer(string='Sequence', default=10)
    active = fields.Boolean(string='Active', default=True)
    level_ids = fields.One2many(
        'ml.approval.level',
        'group_id',
        string='Approval Levels'
    )
    description = fields.Text(string='Description')

    _sql_constraints = [
        ('name_unique', 'UNIQUE(name)', 'Group name must be unique!'),
    ]