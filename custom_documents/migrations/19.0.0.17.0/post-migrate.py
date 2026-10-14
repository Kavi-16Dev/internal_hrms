# -*- coding: utf-8 -*-
"""Backfill the Inbox flag for existing company Inbox folders.

Odoo 19 stores translated Char values as JSONB.  Never call lower() on the
JSONB column itself; extract a text value first.
"""
import logging

_logger = logging.getLogger(__name__)


def migrate(cr, version):
    if not version:
        return

    cr.execute("""
        UPDATE documents_folder AS inbox
           SET is_inbox = TRUE
          FROM documents_folder AS company_drive
         WHERE inbox.parent_folder_id = company_drive.id
           AND company_drive.folder_type = 'company'
           AND lower(COALESCE(inbox.name ->> 'en_US', '')) = 'inbox'
           AND inbox.is_inbox IS DISTINCT FROM TRUE
    """)

    _logger.info(
        "custom_documents 19.0.0.17.0: marked %s existing company Inbox folder(s).",
        cr.rowcount,
    )
