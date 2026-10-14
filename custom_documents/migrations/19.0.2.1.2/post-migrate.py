# -*- coding: utf-8 -*-
"""
Post-migration script: 19.0.2.1.2

`documents_menus.xml` no longer defines the `menu_documents_request`
("Request Document") and `menu_documents_shares` ("Share Links") entries
under the Documents app menu - both are now only reachable from the
"New" button (Request) and from a document's "Share" button, matching
the reference UI, instead of being their own sidebar sections.

A normal `-u custom_documents` upgrade already removes menu items whose
xml_id disappears from a module's data files, but we delete them here
too as a safety net in case an old database is upgraded in a way that
skips that automatic orphan cleanup (e.g. the xml_id was hand-edited or
the module's ir.model.data got out of sync).
"""
import logging

_logger = logging.getLogger(__name__)

REMOVED_MENU_XML_IDS = [
    'custom_documents.menu_documents_request',
    'custom_documents.menu_documents_shares',
]


def migrate(cr, version):
    if not version:
        # Fresh install picks up the (already correct) XML directly.
        return

    env = _get_env(cr)

    removed = 0
    for xml_id in REMOVED_MENU_XML_IDS:
        menu = env.ref(xml_id, raise_if_not_found=False)
        if menu:
            _logger.info("Removing obsolete Documents menu item: %s", xml_id)
            menu.unlink()
            removed += 1

    if removed:
        _logger.info("custom_documents post-migrate: removed %d obsolete menu(s).", removed)
    else:
        _logger.info("custom_documents post-migrate: no obsolete menus found.")


def _get_env(cr):
    """Return an environment, compatible with the Odoo version running
    this migration (env(cr) helper differs slightly across versions)."""
    from odoo import api, SUPERUSER_ID
    return api.Environment(cr, SUPERUSER_ID, {})
