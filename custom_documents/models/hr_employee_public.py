# -*- coding: utf-8 -*-
from odoo import fields, models


class HrEmployeePublic(models.Model):
    """Employees without HR rights (Employees: No) see the *public* employee
    form, a different model from hr.employee.  The Documents smart button
    has to exist there too, otherwise those employees can never reach their
    own documents."""
    _inherit = 'hr.employee.public'

    document_count = fields.Integer(
        string='Document Count', compute='_compute_document_count')

    def _compute_document_count(self):
        Employee = self.env['hr.employee'].sudo()
        for public in self:
            # hr.employee.public rows share their id with hr.employee.
            employee = Employee.browse(public.id)
            public.document_count = employee.with_env(self.env)\
                ._get_own_document_count() if employee.exists() else 0

    def action_view_documents(self):
        self.ensure_one()
        return self.env['hr.employee'].sudo().browse(self.id)\
            .with_env(self.env).action_view_documents()
