from odoo.tests.common import TransactionCase
from odoo.exceptions import AccessError


class TestDocumentsSharingVideoFlow(TransactionCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.admin = cls.env.ref('base.user_admin')
        cls.user = cls.env['res.users'].create({
            'name': 'Video Share User',
            'login': 'video_share_user',
            'email': 'video.share@example.com',
            'group_ids': [(6, 0, [cls.env.ref('custom_documents.group_documents_user').id])],
        })
        cls.folder = cls.env['documents.folder'].create({
            'name': 'Private Share Test',
            'folder_type': 'custom',
            'user_id': cls.admin.id,
            'company_id': cls.env.company.id,
        })
        cls.document = cls.env['documents.document'].create({
            'name': 'Video Share Test.pdf',
            'folder_id': cls.folder.id,
            'type': 'binary',
        })

    def test_shared_document_appears_in_shared_with_me(self):
        self.env['documents.share'].with_user(self.admin).action_share_internal(
            self.document.id, [self.user.id], 'viewer', True, False, 'none')
        domain = self.env['documents.document'].with_user(self.user)._get_shared_with_me_domain()
        visible = self.env['documents.document'].with_user(self.user).search(domain)
        self.assertIn(self.document, visible)
        self.assertIn(self.user, self.document.sudo().shared_user_ids)

        # The recipient must be able to find/read the document even though
        # the containing folder itself is private to the owner.
        recipient_doc = self.env['documents.document'].with_user(self.user).browse(self.document.id).exists()
        self.assertTrue(recipient_doc)



    def test_shared_with_me_uses_direct_recipient_index(self):
        Share = self.env['documents.share'].with_user(self.admin)
        Share.action_share_internal(
            self.document.id, [self.user.id], 'viewer', True, False, 'none')

        self.env.cr.execute("""
            SELECT 1
              FROM documents_document_shared_user_rel
             WHERE document_id = %s AND user_id = %s
        """, (self.document.id, self.user.id))
        self.assertIsNotNone(
            self.env.cr.fetchone(),
            'The share operation must immediately populate the recipient index.')

        domain = self.env['documents.document'].with_user(self.user)._get_shared_with_me_domain()
        visible = self.env['documents.document'].with_user(self.user).search(domain)
        self.assertEqual(visible.filtered(lambda d: d.id == self.document.id), self.document)

    def test_direct_share_record_also_populates_shared_with_me(self):
        share = self.env['documents.share'].with_user(self.admin).create({
            'name': 'Direct share',
            'share_type': 'ids',
            'document_ids': [(6, 0, [self.document.id])],
            'recipient_user_ids': [(6, 0, [self.user.id])],
            'role': 'viewer',
            'access_mode': 'view',
            'internal_access': 'none',
            'state': 'active',
            'owner_id': self.admin.id,
            'company_id': self.env.company.id,
        })
        self.assertTrue(share)
        self.assertIn(self.user, self.document.sudo().shared_user_ids)
        visible = self.env['documents.document'].with_user(self.user).search(
            self.env['documents.document'].with_user(self.user)._get_shared_with_me_domain()
        )
        self.assertIn(self.document, visible)

        share.with_user(self.admin).write({'state': 'revoked'})
        self.assertNotIn(self.user, self.document.sudo().shared_user_ids)

    def test_share_keeps_independent_recipient_roles(self):
        Share = self.env['documents.share'].with_user(self.admin)
        Share.action_share_internal(self.document.id, [self.user.id], 'viewer', True, False, 'none')
        other = self.env['res.users'].create({
            'name': 'Video Share Editor',
            'login': 'video_share_editor',
            'email': 'video.editor@example.com',
            'group_ids': [(6, 0, [self.env.ref('custom_documents.group_documents_user').id])],
        })
        Share.action_share_internal(self.document.id, [other.id], 'editor', True, False, 'none')
        shares = self.env['documents.share'].search([('document_ids', '=', self.document.id), ('state', '=', 'active')])
        viewer_share = shares.filtered(lambda s: self.user in s.recipient_user_ids)
        editor_share = shares.filtered(lambda s: other in s.recipient_user_ids)
        self.assertTrue(viewer_share)
        self.assertTrue(editor_share)
        self.assertEqual(viewer_share[:1].role, 'viewer')
        self.assertEqual(editor_share[:1].role, 'editor')
