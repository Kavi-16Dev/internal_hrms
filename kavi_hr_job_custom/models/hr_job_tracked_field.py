# -*- coding: utf-8 -*-
from odoo import api, fields, models, _


class HrJobTrackedField(models.Model):
    """Configuration list of which hr.job fields get logged to
    hr.job.version.history whenever they change.

    "Field Changed" is a Selection dropdown (not free text) on purpose:
    the technical name behind each option (e.g. 'budgeting_information')
    must match a real Html field on hr.job for the write() override in
    models/hr_job.py to actually find and log data for it. Free-typing
    an arbitrary name that doesn't exist on hr.job would silently track
    nothing.

    To add a THIRD field later (beyond the 2 below):
      1. Add the new Html/Text field to hr.job in models/hr_job.py.
      2. Add one more ('technical_name', 'Display Label') tuple to
         FIELD_SELECTION below.
      3. Upgrade the module, then add a row for it here (Recruitment >
         Configuration > Tracked Fields) - no other code changes needed.
    """
    _name = 'hr.job.tracked.field'
    _description = 'Job Position - Tracked Field for Version History'
    _order = 'sequence, id'

   
    FIELD_SELECTION = [
        ('budgeting_information', 'Budgeting Information'),
        ('key_responsibilities', 'Key Roles and Responsibilities'),
    ]

    sequence = fields.Integer(default=10)

    field_key = fields.Selection(
        selection=FIELD_SELECTION,
        string='Field Changed',
        required=True,
        help='Which Job Position field this row tracks. Only Budgeting '
             'Information and Key Roles and Responsibilities are offered, '
             'since those are the two Html fields wired up for version '
             'tracking on hr.job.',
    )
   
    field_label = fields.Char(
        string='Field Changed (label)', required=True,
        help='This exact text is shown in the "Field Changed" box on '
             'Version History rows for this field.',
    )
    active = fields.Boolean(default=True)

    _sql_constraints = [
        ('field_key_unique', 'unique(field_key)',
         'This field is already configured for version tracking.'),
    ]

    @api.onchange('field_key')
    def _onchange_field_key(self):
        for rec in self:
            if rec.field_key:
                rec.field_label = dict(self.FIELD_SELECTION).get(rec.field_key)

    def name_get(self):
        result = []
        for rec in self:
            result.append((rec.id, rec.field_label or dict(self.FIELD_SELECTION).get(rec.field_key) or _('Tracked Field')))
        return result

    @api.model
    def _get_tracked_fields_map(self):
        """Returns {technical_field_name: display_label} for every active,
        configured field. Used by hr.job's write() override to decide
        which changed fields to log, and under what label."""
        records = self.sudo().search([('active', '=', True)])
        return {rec.field_key: rec.field_label for rec in records if rec.field_key}
