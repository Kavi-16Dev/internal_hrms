from odoo import models, fields, api
from odoo.exceptions import ValidationError


class ApprovalLevel(models.Model):
    _name = 'ml.approval.level'
    _description = 'Approval Level'
    _order = 'sequence, id'

    name = fields.Char(string='Level Name', required=True)
    sequence = fields.Integer(string='Sequence', required=True, default=10)
    group_id = fields.Many2one(
        'ml.approval.group',
        string='Approval Group',
        required=True,
        ondelete='cascade'
    )
    min_amount = fields.Float(
        string='Minimum Amount',
        required=True,
        default=0.0,
        help='Minimum amount threshold for this approval level'
    )
    max_amount = fields.Float(
        string='Maximum Amount',
        required=True,
        help='Maximum amount threshold for this approval level'
    )
    is_recommendation = fields.Boolean(
        string='Recommendation',
        default=True,
        help='If checked, this level is for recommendation'
    )
    is_approval = fields.Boolean(
        string='Approval',
        default=True,
        help='If checked, this level is for approval'
    )

    user_ids = fields.Many2many(
        'res.users',
        'ml_approval_level_user_rel',
        'level_id', 'user_id',
        string='Approvers/Recommenders'
    )
    active = fields.Boolean(string='Active', default=True)

    @api.constrains('min_amount', 'max_amount')
    def _check_amounts(self):
        for level in self:
            if level.min_amount >= level.max_amount:
                raise ValidationError(
                    'Minimum amount must be less than maximum amount!'
                )

    @api.constrains('sequence', 'group_id')
    def _check_sequence_uniqueness(self):
        for level in self:
            if self.search_count([
                ('group_id', '=', level.group_id.id),
                ('sequence', '=', level.sequence),
                ('id', '!=', level.id)
            ]) > 0:
                raise ValidationError(
                    'Sequence must be unique within the same approval group!'
                )