# -*- coding: utf-8 -*-
from odoo import Command
from odoo.tests.common import TransactionCase


class TestDocumentSections(TransactionCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.admin = cls.env.ref('base.user_admin')
        cls.basic_group = cls.env.ref('custom_documents.group_documents_basic')
        cls.user = cls.env['res.users'].create({
            'name': 'Section Test User',
            'login': 'section_test_user',
            'email': 'section.test@example.com',
            'group_ids': [Command.link(cls.basic_group.id)],
        })
        cls.folder = cls.env['documents.folder'].create({
            'name': 'Section Test Folder',
            'folder_type': 'custom',
            'company_id': cls.env.company.id,
        })
        cls.inbox = cls.env['documents.folder']._get_or_create_company_inbox(cls.env.company)

    def _doc(self, name, **vals):
        values = {
            'name': name,
            'folder_id': self.folder.id,
            'type': 'binary',
            'state': 'uploaded',
        }
        values.update(vals)
        return self.env['documents.document'].create(values)

    def test_shared_document_is_only_in_shared_with_me(self):
        doc = self._doc('Shared Section.pdf')
        self.env['documents.share'].with_user(self.admin).action_share_internal(
            doc.id, [self.user.id], 'viewer', False, False, 'none')

        docs = self.env['documents.document'].with_user(self.user)
        shared = docs.search(docs._get_shared_with_me_domain())
        requests = docs.search(docs._get_requests_domain())
        inbox = docs.search(docs._get_inbox_domain())

        self.assertIn(doc, shared)
        self.assertNotIn(doc, requests)
        self.assertNotIn(doc, inbox)

    def test_request_appears_in_requests_until_fulfilled(self):
        doc = self.env['documents.document'].with_user(self.admin).create({
            'name': 'Requested Section.pdf',
            'folder_id': self.inbox.id,
            'type': 'binary',
            'state': 'requested',
            'request_user_id': self.user.id,
            'requested_by_id': self.admin.id,
        })

        docs = self.env['documents.document'].with_user(self.user)
        requests = docs.search(docs._get_requests_domain())
        inbox = docs.search(docs._get_inbox_domain())
        shared = docs.search(docs._get_shared_with_me_domain())

        self.assertIn(doc, requests)
        self.assertNotIn(doc, inbox)
        self.assertNotIn(doc, shared)

        # Once fulfilled, it is no longer a request. Because it is in Inbox,
        # it becomes an Inbox item instead.
        doc.sudo().write({'state': 'uploaded'})
        requests = docs.search(docs._get_requests_domain())
        inbox = docs.search(docs._get_inbox_domain())
        self.assertNotIn(doc, requests)
        self.assertIn(doc, inbox)

    def test_incoming_requested_document_appears_in_inbox_like_reference_flow(self):
        doc = self.env['documents.document'].with_user(self.admin).create({
            'name': 'PAN Card',
            'folder_id': self.inbox.id,
            'type': 'binary',
            'state': 'requested',
            'request_user_id': self.user.id,
            'requested_by_id': self.admin.id,
        })
        recipient_docs = self.env['documents.document'].with_user(self.user)
        inbox = recipient_docs.search(recipient_docs._get_inbox_domain())
        self.assertIn(doc, inbox)
        self.assertIn(doc, recipient_docs.search(recipient_docs._get_requests_domain()))

    def test_normal_inbox_document_appears_in_inbox(self):
        doc = self._doc('Inbox Section.pdf', folder_id=self.inbox.id)
        docs = self.env['documents.document'].with_user(self.user)
        inbox = docs.search(docs._get_inbox_domain())
        self.assertIn(doc, inbox)
        self.assertNotIn(doc, docs.search(docs._get_requests_domain()))

    def test_request_recipient_gets_documents_basic_access(self):
        # Start from a user without the Documents privilege.
        no_documents_user = self.env['res.users'].create({
            'name': 'Request Access User',
            'login': 'request_access_user',
            'email': 'request.access@example.com',
        })
        self.assertFalse(no_documents_user.has_group('custom_documents.group_documents_basic'))

        wizard = self.env['documents.request.wizard'].with_user(self.admin).create({
            'name': 'Access Request.pdf',
            'request_type': 'user',
            'request_user_id': no_documents_user.id,
            'folder_id': self.inbox.id,
        })
        wizard.action_send_request()
        self.assertTrue(no_documents_user.has_group('custom_documents.group_documents_basic'))

        doc = self.env['documents.document'].search([
            ('name', '=', 'Access Request.pdf'),
            ('request_user_id', '=', no_documents_user.id),
        ], limit=1)
        self.assertTrue(doc)
        visible = self.env['documents.document'].with_user(no_documents_user).search(
            self.env['documents.document'].with_user(no_documents_user)._get_requests_domain()
        )
        self.assertIn(doc, visible)
