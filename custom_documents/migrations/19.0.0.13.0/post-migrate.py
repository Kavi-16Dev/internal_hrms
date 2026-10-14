# -*- coding: utf-8 -*-

"""Rebuild the Shared with me recipient index for existing shares."""
import logging

_logger = logging.getLogger(__name__)


def migrate(cr, version):
    if not version:
        return

    # Only explicit document shares belong in Shared with me.
    cr.execute("DELETE FROM documents_document_shared_user_rel")
    cr.execute("""
        INSERT INTO documents_document_shared_user_rel (document_id, user_id)
        SELECT DISTINCT rel.document_id, user_rel.user_id
          FROM documents_share_document_rel rel
          JOIN documents_share share ON share.id = rel.share_id
          JOIN documents_share_user_rel user_rel ON user_rel.share_id = share.id
         WHERE share.state = 'active'
           AND share.share_type = 'ids'
        ON CONFLICT DO NOTHING
    """)
    _logger.info(
        "custom_documents 19.0.0.13.0: rebuilt Shared with me index (%s rows)",
        cr.rowcount,
    )
