# -*- coding: utf-8 -*-
from odoo.tests.common import TransactionCase
from odoo import Command


class TestSharedWithMeIndex(TransactionCase):
    def test_internal_share_populates_recipient_index(self):
        Share = self.env["documents.share"].sudo()
        Document = self.env["documents.document"].sudo()
        Folder = self.env["documents.folder"].sudo()
        User = self.env["res.users"].sudo()

        owner = self.env.user
        recipient = User.create({
            "name": "Shared With Me Test User",
            "login": "shared-with-me-test-%s" % self.env.cr.dbname,
            "email": "shared-with-me-test@example.com",
            "group_ids": [Command.link(self.env.ref("custom_documents.group_documents_basic").id)],
        })
        folder = Folder.create({"name": "Private Share Test", "folder_type": "employee", "user_id": owner.id})
        doc = Document.create({"name": "Shared Test", "folder_id": folder.id})

        Share.action_share_internal(doc.id, [recipient.id], "viewer", False, False, "none")

        self.assertIn(recipient, doc.sudo().shared_user_ids)
        visible = Document.with_user(recipient).search([
            ("shared_user_ids", "in", recipient.id),
            ("id", "=", doc.id),
        ])
        self.assertIn(doc, visible)
