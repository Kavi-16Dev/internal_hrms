# -*- coding: utf-8 -*-

"""Backfill the denormalized Shared with me recipient index.

Version 19.0.0.12.0 introduces documents.document.shared_user_ids.  Existing
share rows must be copied into the new relation table during upgrade, otherwise
old shares would not appear in Shared with me until they are edited again.
"""
import logging

_logger = logging.getLogger(__name__)


def migrate(cr, version):
    if not version:
        return

    # Rebuild the index from the share tables.  The relation is intentionally
    # restricted to explicit document shares; folder-wide shares are not used
    # by the custom Share dialog and therefore do not belong in this index.
    cr.execute("DELETE FROM documents_document_shared_user_rel")
    cr.execute("""
        INSERT INTO documents_document_shared_user_rel (document_id, user_id)
        SELECT DISTINCT rel.document_id, user_rel.user_id
          FROM documents_share_document_rel rel
          JOIN documents_share share
            ON share.id = rel.share_id
          JOIN documents_share_user_rel user_rel
            ON user_rel.share_id = share.id
         WHERE share.state = 'active'
           AND share.share_type = 'ids'
        ON CONFLICT DO NOTHING
    """)
    _logger.info(
        "custom_documents 19.0.0.12.0: rebuilt Shared with me recipient index (%s rows)",
        cr.rowcount,
    )
