# -*- coding: utf-8 -*-
from odoo.tests.common import TransactionCase


class TestSharedDocumentLink(TransactionCase):
    def setUp(self):
        super().setUp()
        self.Folder = self.env["documents.folder"]
        self.Document = self.env["documents.document"]
        self.Share = self.env["documents.share"]
        self.folder = self.Folder.create({
            "name": "Link Test",
            "owner_id": self.env.user.id,
            "folder_type": "private",
        })
        self.document = self.Document.create({
            "name": "Shared PDF",
            "folder_id": self.folder.id,
            "owner_id": self.env.user.id,
        })

    def test_copy_link_is_tokenized_and_points_to_document(self):
        url = self.document.action_copy_link()
        self.assertIn("/document/share/", url)
        self.assertNotIn("/odoo/documents/", url)
        share = self.Share.search([
            ("state", "=", "active"),
            ("share_type", "=", "ids"),
            ("document_ids", "=", self.document.id),
            ("access_mode", "=", "view"),
        ], limit=1)
        self.assertTrue(share)
        self.assertIn(share.access_token, url)

    def test_copy_link_reuses_active_single_document_view_share(self):
        first = self.document.action_copy_link()
        second = self.document.action_copy_link()
        self.assertEqual(first, second)
        self.assertEqual(
            self.Share.search_count([
                ("state", "=", "active"),
                ("share_type", "=", "ids"),
                ("document_ids", "=", self.document.id),
                ("access_mode", "=", "view"),
            ]),
            1,
        )
