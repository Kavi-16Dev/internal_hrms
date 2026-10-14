# -*- coding: utf-8 -*-
"""Compatibility migration for 19.0.0.16.0.

This migration intentionally performs no SQL.  The original 16.0.0
migration called lower() directly on documents.folder.name. In Odoo 19
translated Char values are JSONB, so that SQL fails during an upgrade.
The actual Inbox backfill is performed by 19.0.0.17.0 using JSONB-safe
text extraction. Keeping this script as a no-op also makes upgrades from
older installed versions safe because Odoo executes migration scripts in
version order.
"""

def migrate(cr, version):
    return
