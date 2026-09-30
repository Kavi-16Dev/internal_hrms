# -*- coding: utf-8 -*-
from odoo import api, fields, models


class HrJobBoard(models.Model):
    """Custom model to maintain a master list of Job Boards
    (e.g. LinkedIn, Naukri, Indeed, Monster ...) that can be linked
    to a Job Position (hr.job)."""
    _name = 'hr.job.board'
    _description = 'Job Board'
    _order = 'name'

    name = fields.Char(string='Job Board Name', required=True)
    website = fields.Char(string='Website URL')
    active = fields.Boolean(default=True)
    notes = fields.Text(string='Notes')

  
    account_ids = fields.One2many(
        'hr.job.board.account', 'job_board_id', string='Accounts')
    account_count = fields.Integer(
        string='Accounts', compute='_compute_account_count')

    _sql_constraints = [
        ('name_uniq', 'unique(name)', 'A Job Board with this name already exists.'),
    ]

    @api.depends('account_ids')
    def _compute_account_count(self):
        for board in self:
            board.account_count = len(board.account_ids)

    def _get_or_create_utm_source(self):
        """Return the `utm.source` record whose name matches this Job
        Board's name, creating it (once) if it doesn't exist yet.

        Matching is done by name only (utm.source has no other natural
        key), which also means renaming a Job Board later will create a
        *new* utm.source under the new name rather than renaming the old
        one - existing Applicants already linked to the old Source keep
        pointing at it, which is the safer behaviour for reporting.
        """
        self.ensure_one()
        UtmSource = self.env['utm.source'].sudo()
        source = UtmSource.search([('name', '=', self.name)], limit=1)
        if not source:
            source = UtmSource.create({'name': self.name})
        return source
