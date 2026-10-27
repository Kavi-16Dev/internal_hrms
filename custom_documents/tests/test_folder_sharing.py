from datetime import timedelta

from odoo import fields
from odoo.exceptions import AccessError
from odoo.tests.common import TransactionCase


class TestFolderSharing(TransactionCase):
    """Share dialog on a folder: access is inherited by sub-folders and
    documents, through per-person shares and through general access."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.admin = cls.env.ref('base.user_admin')
        internal = cls.env.ref('base.group_user')

        def make_user(name, login):
            return cls.env['res.users'].create({
                'name': name,
                'login': login,
                'email': f'{login}@example.com',
                'group_ids': [(6, 0, [internal.id])],
            })

        cls.owner = make_user('Folder Owner', 'folder_owner')
        cls.viewer = make_user('Folder Viewer', 'folder_viewer')
        cls.editor = make_user('Folder Editor', 'folder_editor')
        cls.other = make_user('Folder Other', 'folder_other')

        # Plain custom workspaces are readable by every internal user, so the
        # fixtures use the personal-drive type: they are invisible to anyone
        # who was not given access, which is what these tests need to prove.
        Folder = cls.env['documents.folder']
        cls.folder = Folder.create({
            'name': 'Shared Parent',
            'folder_type': 'employee',
            'user_id': cls.owner.id,
            'company_id': cls.env.company.id,
        })
        cls.subfolder = Folder.create({
            'name': 'Shared Child',
            'folder_type': 'employee',
            'parent_folder_id': cls.folder.id,
            'company_id': cls.env.company.id,
        })
        Document = cls.env['documents.document']
        cls.document = Document.create({
            'name': 'Parent File.pdf',
            'folder_id': cls.folder.id,
            'type': 'binary',
        })
        cls.sub_document = Document.create({
            'name': 'Child File.pdf',
            'folder_id': cls.subfolder.id,
            'type': 'binary',
        })
        cls.Share = cls.env['documents.share']

    def _share(self, user, role='viewer', folder=None):
        return self.Share.with_user(self.admin).action_share_folder_internal(
            (folder or self.folder).id, [user.id], role, False)

    def _visible_documents(self, user, folder=None):
        folder = folder or self.folder
        return self.env['documents.document'].with_user(user).search(
            [('folder_id', 'child_of', folder.id)])

    # ------------------------------------------------------------------
    def test_nothing_is_visible_before_sharing(self):
        self.assertFalse(self._visible_documents(self.viewer))
        folders = self.env['documents.folder'].with_user(self.viewer).search(
            [('id', 'in', (self.folder | self.subfolder).ids)])
        self.assertFalse(folders)

    def test_viewer_inherits_read_access_on_subfolders_and_documents(self):
        self._share(self.viewer, 'viewer')
        self.assertEqual(
            self._visible_documents(self.viewer), self.document | self.sub_document)
        folders = self.env['documents.folder'].with_user(self.viewer).search(
            [('id', 'in', (self.folder | self.subfolder).ids)])
        self.assertEqual(folders, self.folder | self.subfolder)
        # Still nothing for people who were not shared with.
        self.assertFalse(self._visible_documents(self.other))

    def test_viewer_cannot_edit(self):
        self._share(self.viewer, 'viewer')
        with self.assertRaises(AccessError):
            self.document.with_user(self.viewer).write({'name': 'Renamed'})

    def test_editor_can_edit_documents_in_subfolders(self):
        self._share(self.editor, 'editor')
        self.sub_document.with_user(self.editor).write({'name': 'Edited by editor'})
        self.assertEqual(self.sub_document.name, 'Edited by editor')
        # Editing is granted, deleting is not.
        with self.assertRaises(AccessError):
            self.sub_document.with_user(self.editor).unlink()

    def test_new_subfolder_inherits_the_share(self):
        self._share(self.viewer, 'viewer')
        grandchild = self.env['documents.folder'].create({
            'name': 'Created After Sharing',
            'folder_type': 'employee',
            'parent_folder_id': self.subfolder.id,
            'company_id': self.env.company.id,
        })
        found = self.env['documents.folder'].with_user(self.viewer).search(
            [('id', '=', grandchild.id)])
        self.assertEqual(found, grandchild)

    def test_moving_a_folder_out_removes_inherited_access(self):
        self._share(self.viewer, 'viewer')
        self.subfolder.parent_folder_id = False
        found = self.env['documents.folder'].with_user(self.viewer).search(
            [('id', '=', self.subfolder.id)])
        self.assertFalse(found)
        self.assertFalse(
            self.env['documents.document'].with_user(self.viewer).search(
                [('id', '=', self.sub_document.id)]))

    def test_remove_access_revokes_it(self):
        self._share(self.viewer, 'viewer')
        self.assertTrue(self._visible_documents(self.viewer))
        self.Share.with_user(self.admin).action_remove_folder_access(
            self.folder.id, self.viewer.id)
        self.assertFalse(self._visible_documents(self.viewer))

    def test_roles_are_independent_per_person(self):
        self._share(self.viewer, 'viewer')
        self._share(self.editor, 'editor')
        data = self.Share.with_user(self.admin).get_folder_share_dialog_data(
            self.folder.id)
        roles = {user['id']: user['role'] for user in data['users']}
        self.assertEqual(roles[self.viewer.id], 'viewer')
        self.assertEqual(roles[self.editor.id], 'editor')
        self.assertIn(self.editor, self.folder.shared_editor_ids)
        self.assertNotIn(self.viewer, self.folder.shared_editor_ids)

    def test_owner_can_share_their_own_folder(self):
        self.Share.with_user(self.owner).action_share_folder_internal(
            self.folder.id, [self.viewer.id], 'viewer', False)
        self.assertTrue(self._visible_documents(self.viewer))

    def test_only_owner_or_administrator_can_share(self):
        self._share(self.viewer, 'viewer')
        with self.assertRaises(AccessError):
            self.Share.with_user(self.viewer).action_share_folder_internal(
                self.folder.id, [self.other.id], 'viewer', False)
        with self.assertRaises(AccessError):
            self.Share.with_user(self.viewer).set_folder_general_access(
                self.folder.id, internal='editor')

    def test_dialog_lists_people_inherited_from_the_parent(self):
        self._share(self.viewer, 'viewer')
        data = self.Share.with_user(self.admin).get_folder_share_dialog_data(
            self.subfolder.id)
        self.assertFalse(data['users'])
        self.assertEqual([u['id'] for u in data['inherited_users']], [self.viewer.id])
        self.assertEqual(data['inherited_users'][0]['inherited_from'], self.folder.name)
        self.assertTrue(data['is_folder'])

    def test_general_access_is_inherited_by_subfolders(self):
        self.Share.with_user(self.admin).set_folder_general_access(
            self.folder.id, internal='viewer')
        self.assertEqual(self.subfolder.effective_access_internal, 'viewer')
        self.assertEqual(
            self._visible_documents(self.other), self.document | self.sub_document)
        with self.assertRaises(AccessError):
            self.document.with_user(self.other).write({'name': 'Nope'})

        self.Share.with_user(self.admin).set_folder_general_access(
            self.folder.id, internal='none')
        self.assertEqual(self.subfolder.effective_access_internal, 'none')
        self.assertFalse(self._visible_documents(self.other))

    def test_general_access_editor_allows_editing(self):
        self.Share.with_user(self.admin).set_folder_general_access(
            self.folder.id, internal='editor')
        self.env.ref('custom_documents.group_documents_basic').write(
            {'user_ids': [(4, self.other.id)]})
        self.sub_document.with_user(self.other).write({'name': 'Edited via general access'})
        self.assertEqual(self.sub_document.name, 'Edited via general access')

    def test_folder_link_follows_access_through_link(self):
        link_share = self.Share.with_user(self.admin)._get_or_create_folder_link_share(
            self.folder)
        self.assertEqual(link_share.share_type, 'folder')
        self.assertFalse(link_share._get_shared_documents())

        self.Share.with_user(self.admin).set_folder_general_access(
            self.folder.id, link='viewer')
        self.assertEqual(
            link_share._get_shared_documents(), self.document | self.sub_document)
        self.assertEqual(link_share.access_mode, 'view')

        self.Share.with_user(self.admin).set_folder_general_access(
            self.folder.id, link='editor')
        self.assertEqual(link_share.access_mode, 'download')

        self.Share.with_user(self.admin).set_folder_general_access(
            self.folder.id, link='none')
        self.assertFalse(link_share._get_shared_documents())

    def test_expired_share_no_longer_grants_access(self):
        self._share(self.viewer, 'viewer')
        self.assertTrue(self._visible_documents(self.viewer))
        share = self.Share.sudo().search([
            ('share_type', '=', 'folder'),
            ('folder_id', '=', self.folder.id),
            ('recipient_user_ids', 'in', self.viewer.id),
        ])
        share.write({'date_deadline': fields.Date.today() - timedelta(days=1)})
        self.assertFalse(self._visible_documents(self.viewer))

    def test_shared_with_me_lists_only_the_top_shared_folder(self):
        self._share(self.viewer, 'viewer')
        cards = self.env['documents.folder'].with_user(self.viewer).get_documents_view_folders(
            'shared_with_me')
        self.assertEqual([card['id'] for card in cards], [self.folder.id])
        self.assertFalse(cards[0]['can_share'])
        # The owner does not see their own folder as shared with them.
        own = self.env['documents.folder'].with_user(self.owner).get_documents_view_folders(
            'shared_with_me')
        self.assertNotIn(self.folder.id, [card['id'] for card in own])

    def test_company_drive_inbox_and_hr_folders_are_admin_only(self):
        drive = self.env['documents.folder']._get_or_create_company_drive(self.env.company)
        self.assertFalse(drive.with_user(self.viewer)._can_manage_access())
        self.assertTrue(drive.with_user(self.admin)._can_manage_access())
        self.folder.is_inbox = True
        self.assertFalse(self.folder.with_user(self.viewer)._can_manage_access())
