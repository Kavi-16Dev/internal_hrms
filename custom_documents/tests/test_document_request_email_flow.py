# -*- coding: utf-8 -*-
from odoo.tests.common import TransactionCase


class TestDocumentRequestEmailFlow(TransactionCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.admin = cls.env.ref('base.user_admin')
        cls.recipient = cls.env['res.users'].create({
            'name': 'Abigail Peterson',
            'login': 'abigail.peterson.request',
            'email': 'abigail.peterson@example.com',
        })
        cls.folder = cls.env['documents.folder']._get_or_create_company_inbox(
            cls.env.company)

    def _request(self, name='Aadhar Card'):
        wizard = self.env['documents.request.wizard'].with_user(self.admin).create({
            'name': name,
            'request_type': 'user',
            'request_user_id': self.recipient.id,
            'folder_id': self.folder.id,
            'request_deadline_in': 30,
            'request_deadline_unit': 'days',
            'request_note': 'Please submit the Aadhar card',
        })
        wizard.action_send_request()
        return self.env['documents.document'].search([
            ('name', '=', name),
            ('request_user_id', '=', self.recipient.id),
        ], order='id desc', limit=1)


    def test_request_user_populates_contact_and_canonical_request_method(self):
        wizard = self.env['documents.request.wizard'].with_user(self.admin).create({
            'name': 'Contact Auto Fill.pdf',
            'request_type': 'user',
            'request_user_id': self.recipient.id,
            'folder_id': self.folder.id,
            'request_deadline_in': 30,
            'request_deadline_unit': 'days',
        })
        wizard._onchange_request_user_id()
        self.assertEqual(wizard.partner_id, self.recipient.partner_id)
        self.assertTrue(wizard.partner_id)

        wizard.request_document()
        document = self.env['documents.document'].search([
            ('name', '=', 'Contact Auto Fill.pdf'),
            ('request_user_id', '=', self.recipient.id),
        ], order='id desc', limit=1)
        self.assertTrue(document)
        self.assertEqual(document.partner_id, self.recipient.partner_id)
        self.assertEqual(document.request_partner_id, self.recipient.partner_id)

    def test_request_contact_is_computed_without_manual_onchange(self):
        wizard = self.env['documents.request.wizard'].with_user(self.admin).create({
            'name': 'Computed Contact.pdf',
            'request_to_id': self.recipient.partner_id.id,
            'folder_id': self.folder.id,
            'request_deadline_in': 30,
            'request_deadline_unit': 'days',
        })
        self.assertEqual(wizard.partner_id, self.recipient.partner_id)

    def test_request_preserves_rich_text_message(self):
        wizard = self.env['documents.request.wizard'].with_user(self.admin).create({
            'name': 'Rich Message.pdf',
            'request_to_id': self.recipient.partner_id.id,
            'folder_id': self.folder.id,
            'request_deadline_in': 30,
            'request_deadline_unit': 'days',
            'request_note': '<p><strong>Please submit</strong> this document.</p>',
        })
        document_action = wizard.request_document()
        self.assertEqual(document_action['type'], 'ir.actions.act_window_close')
        document = self.env['documents.document'].search([
            ('name', '=', 'Rich Message.pdf'),
            ('request_partner_id', '=', self.recipient.partner_id.id),
        ], order='id desc', limit=1)
        self.assertTrue(document)
        self.assertIn('Please submit', document.request_note)
        self.assertTrue(document.request_share_id)


    def test_request_to_partner_selector_and_contact_autofill(self):
        wizard = self.env['documents.request.wizard'].with_user(self.admin).create({
            'name': 'Partner Selector.pdf',
            'request_type': 'user',
            'request_user_id': self.recipient.id,
            'folder_id': self.folder.id,
            'request_deadline_in': 30,
            'request_deadline_unit': 'days',
        })
        wizard._onchange_request_user_id()
        self.assertEqual(wizard.request_to_id, self.recipient.partner_id)
        self.assertEqual(wizard.partner_id, self.recipient.partner_id)

        wizard.request_to_id = self.recipient.partner_id
        wizard._onchange_request_to_id()
        self.assertEqual(wizard.partner_id, self.recipient.partner_id)

        wizard.request_document()
        document = self.env['documents.document'].search([
            ('name', '=', 'Partner Selector.pdf'),
            ('request_user_id', '=', self.recipient.id),
        ], order='id desc', limit=1)
        self.assertTrue(document)
        self.assertEqual(document.partner_id, self.recipient.partner_id)

    def test_request_to_external_partner_keeps_legacy_partner_flow(self):
        partner = self.env['res.partner'].create({
            'name': 'External Request Contact',
            'email': 'external.request@example.com',
        })
        wizard = self.env['documents.request.wizard'].with_user(self.admin).create({
            'name': 'External Partner.pdf',
            'request_type': 'partner',
            'request_partner_id': partner.id,
            'folder_id': self.folder.id,
            'request_deadline_in': 30,
            'request_deadline_unit': 'days',
        })
        wizard.request_to_id = partner
        wizard._onchange_request_to_id()
        self.assertFalse(wizard.request_user_id)
        self.assertEqual(wizard.request_partner_id, partner)
        self.assertEqual(wizard.partner_id, partner)

        wizard.request_document()
        document = self.env['documents.document'].search([
            ('name', '=', 'External Partner.pdf'),
            ('request_partner_id', '=', partner.id),
        ], order='id desc', limit=1)
        self.assertTrue(document)
        self.assertEqual(document.partner_id, partner)

    def test_request_creates_secure_upload_share(self):
        document = self._request()
        self.assertTrue(document.request_share_id)
        self.assertEqual(document.request_share_id.access_mode, 'upload')
        self.assertEqual(document.request_share_id.share_type, 'ids')
        self.assertIn(document, document.request_share_id.document_ids)
        self.assertIn('/document/share/', document.request_share_url)
        self.assertIn(document.request_share_id.access_token, document.request_share_url)

    def test_request_email_contains_reference_flow_content(self):
        document = self._request()
        template = self.env.ref('custom_documents.mail_template_document_request')
        values = template.generate_email(document.id)
        body = values['body_html']

        self.assertFalse(values['email_to'])
        self.assertEqual(values['partner_to'], str(self.recipient.partner_id.id))
        self.assertIn('Hello Abigail Peterson,', body)
        self.assertIn('Abigail Peterson', body)
        self.assertIn('asks you to provide the following document:', body)
        self.assertIn('Aadhar Card', body)
        self.assertIn('Please submit the Aadhar card', body)
        self.assertIn('Upload the requested document', body)
        self.assertIn(document.request_share_id.access_token, body)
        self.assertIn(str(document.request_deadline), body)
        self.assertIn(self.admin.name, body)
        self.assertIn('Powered by Odoo Documents', body)
        self.assertEqual(values['subject'], 'Document Request : Aadhar Card')

    def test_request_email_uses_partner_email_for_internal_user(self):
        self.recipient.email = False
        self.recipient.partner_id.email = 'abigail.partner@example.com'
        document = self._request('Partner Email Fallback.pdf')
        template = self.env.ref('custom_documents.mail_template_document_request')
        values = template.generate_email(document.id)
        self.assertFalse(values['email_to'])
        self.assertEqual(values['partner_to'], str(self.recipient.partner_id.id))

    def test_request_reuses_active_upload_share(self):
        document = self._request('Reusable Request.pdf')
        first_share = document.request_share_id
        document._send_request_notification()
        document.invalidate_recordset(['request_share_id'])
        self.assertEqual(document.request_share_id, first_share)
        self.assertEqual(
            self.env['documents.share'].search_count([
                ('document_ids', '=', document.id),
                ('access_mode', '=', 'upload'),
                ('state', '=', 'active'),
            ]),
            1,
        )


    def test_request_email_matches_reference_video_flow(self):
        document = self._request('PAN Card')
        template = self.env.ref('custom_documents.mail_template_document_request')
        values = template.generate_email(document.id)
        body = values['body_html']
        self.assertEqual(values['subject'], 'Document Request : PAN Card')
        self.assertIn('asks you to provide the following document:', body)
        self.assertIn('PAN Card', body)
        self.assertIn('Upload the requested document', body)
        self.assertIn('Please provide us with the missing document before', body)
        self.assertIn('--', body)
        self.assertIn('Powered by Odoo Documents', body)
        self.assertIn(document.request_share_id.access_token, body)
