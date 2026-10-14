# -*- coding: utf-8 -*-
"""Align HR employee folders with the first-35-seconds reference flow.

Older releases keyed employee folders only by the employee's linked user.
The reference creates one folder per employee, even when no linked user
exists, and shows a Contracts child folder.
"""
import logging

from odoo import SUPERUSER_ID, api, _

_logger = logging.getLogger(__name__)


def migrate(cr, version):
    if not version:
        return

    env = api.Environment(cr, SUPERUSER_ID, {})
    Employee = env["hr.employee"].sudo()
    Folder = env["documents.folder"].sudo()
    created = 0
    linked = 0
    members = 0
    contracts = 0

    for employee in Employee.search([]):
        company = employee.company_id or env.company
        parent = company.documents_hr_folder_id
        if not company.documents_hr_settings or not parent or not company.documents_hr_subfolders:
            continue

        folder = Folder.search([
            ("employee_id", "=", employee.id),
            ("company_id", "=", company.id),
        ], limit=1)

        if not folder and employee.user_id:
            folder = Folder.search([
                ("parent_folder_id", "=", parent.id),
                ("folder_type", "=", "custom"),
                ("user_id", "=", employee.user_id.id),
                ("company_id", "=", company.id),
            ], limit=1)
            if folder:
                folder.write({"employee_id": employee.id})
                linked += 1

        if not folder:
            folder = Folder.create({
                "name": employee.name,
                "folder_type": "custom",
                "parent_folder_id": parent.id,
                "user_id": employee.user_id.id if employee.user_id else False,
                "employee_id": employee.id,
                "company_id": company.id,
                "member_ids": [(4, employee.user_id.id)] if employee.user_id else [],
            })
            created += 1

        if employee.user_id and employee.user_id not in folder.member_ids:
            folder.write({"member_ids": [(4, employee.user_id.id)]})
            members += 1

        child = Folder.search([
            ("parent_folder_id", "=", folder.id),
            ("company_id", "=", company.id),
            ("name", "=", _("Contracts")),
            ("active", "=", True),
        ], limit=1)
        if not child:
            Folder.create({
                "name": _("Contracts"),
                "folder_type": "custom",
                "parent_folder_id": folder.id,
                "company_id": company.id,
            })
            contracts += 1

    _logger.info(
        "custom_documents 19.0.0.2.11: employee folders created=%s linked=%s members=%s contracts=%s",
        created, linked, members, contracts,
    )
