# -*- coding: utf-8 -*-

"""Align existing HR employee document drives with the reference sharing flow.

Employee subfolders are workspaces owned by the employee's linked user.  The
user is also an explicit workspace member so files uploaded by HR/another
Documents user appear in that employee's Shared with me section.
"""
import logging

from odoo import SUPERUSER_ID, api

_logger = logging.getLogger(__name__)


def migrate(cr, version):
    if not version:
        return

    env = api.Environment(cr, SUPERUSER_ID, {})
    Employee = env["hr.employee"].sudo()
    updated = 0
    created = 0

    for employee in Employee.search([("user_id", "!=", False)]):
        company = employee.company_id or env.company
        if not company.documents_hr_settings or not company.documents_hr_folder_id:
            continue
        if not company.documents_hr_subfolders:
            continue

        folder = env["documents.folder"].sudo().search([
            ("parent_folder_id", "=", company.documents_hr_folder_id.id),
            ("folder_type", "=", "custom"),
            ("user_id", "=", employee.user_id.id),
            ("company_id", "=", company.id),
        ], limit=1)

        if not folder:
            folder = env["documents.folder"].sudo().create({
                "name": employee.name,
                "folder_type": "custom",
                "parent_folder_id": company.documents_hr_folder_id.id,
                "user_id": employee.user_id.id,
                "member_ids": [(4, employee.user_id.id)],
                "company_id": company.id,
            })
            created += 1
        elif employee.user_id not in folder.member_ids:
            folder.write({"member_ids": [(4, employee.user_id.id)]})
            updated += 1

    _logger.info(
        "custom_documents 19.0.0.2.10: employee document drives created=%s, memberships added=%s",
        created, updated,
    )
