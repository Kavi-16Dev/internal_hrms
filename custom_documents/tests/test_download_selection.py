from odoo.exceptions import AccessError
from odoo.tests.common import TransactionCase


class TestDownloadSelection(TransactionCase):
    """What the Download button of the selection bar puts in the download."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.admin = cls.env.ref('base.user_admin')
        internal = cls.env.ref('base.group_user')
        cls.owner = cls.env['res.users'].create({
            'name': 'Download Owner',
            'login': 'download_owner',
            'group_ids': [(6, 0, [internal.id])],
        })
        cls.viewer = cls.env['res.users'].create({
            'name': 'Download Viewer',
            'login': 'download_viewer',
            'group_ids': [(6, 0, [internal.id])],
        })

        # Personal-drive type folders are invisible to anybody not given
        # access, which the access tests below rely on.
        Folder = cls.env['documents.folder']
        cls.root = Folder.create({
            'name': 'Reports',
            'folder_type': 'employee',
            'user_id': cls.owner.id,
            'company_id': cls.env.company.id,
        })
        cls.child = Folder.create({
            'name': '2026',
            'folder_type': 'employee',
            'parent_folder_id': cls.root.id,
            'company_id': cls.env.company.id,
        })
        cls.doc_a = cls._make_document('a.txt', cls.root, b'a')
        cls.doc_b = cls._make_document('b.txt', cls.child, b'b')
        # Renamed without an extension: the file's own extension is kept.
        cls.doc_contract = cls._make_document(
            'Contract', cls.root, b'c', attachment_name='Contract.pdf')
        cls.Document = cls.env['documents.document'].with_user(cls.admin)

    @classmethod
    def _make_document(cls, name, folder, content, attachment_name=None):
        attachment = cls.env['ir.attachment'].create({
            'name': attachment_name or name,
            'raw': content,
        })
        return cls.env['documents.document'].create({
            'name': name,
            'folder_id': folder.id,
            'attachment_id': attachment.id,
            'type': 'binary',
        })

    def _paths(self, entries):
        return sorted(path for path, _document in entries)

    def test_folder_keeps_its_structure(self):
        entries = self.Document._get_download_entries([], [self.root.id])
        self.assertEqual(
            self._paths(entries),
            ['Reports/2026/b.txt', 'Reports/Contract.pdf', 'Reports/a.txt'])

    def test_selected_files_sit_at_the_root(self):
        entries = self.Document._get_download_entries(
            [self.doc_a.id, self.doc_b.id], [])
        self.assertEqual(self._paths(entries), ['a.txt', 'b.txt'])

    def test_file_and_folder_can_be_combined(self):
        entries = self.Document._get_download_entries(
            [self.doc_a.id], [self.child.id])
        self.assertEqual(self._paths(entries), ['2026/b.txt', 'a.txt'])

    def test_renamed_file_keeps_its_extension(self):
        self.assertEqual(self.doc_contract._get_download_filename(), 'Contract.pdf')

    def test_duplicate_names_get_a_suffix(self):
        twin = self._make_document('a.txt', self.child, b'twin')
        entries = self.Document._get_download_entries(
            [self.doc_a.id, twin.id], [])
        self.assertEqual(self._paths(entries), ['a (2).txt', 'a.txt'])

    def test_links_placeholders_and_empty_documents_are_skipped(self):
        Document = self.env['documents.document']
        Document.create({
            'name': 'Website', 'folder_id': self.root.id,
            'type': 'url', 'url': 'https://example.com'})
        Document.create({
            'name': 'Empty', 'folder_id': self.root.id, 'type': 'binary'})
        Document.create({
            'name': 'Requested', 'folder_id': self.root.id,
            'state': 'requested', 'request_user_id': self.viewer.id})
        entries = self.Document._get_download_entries([], [self.root.id])
        self.assertEqual(len(entries), 3)

    def test_download_info(self):
        info = self.Document.get_download_info([self.doc_a.id], [])
        self.assertEqual(info['count'], 1)
        self.assertEqual(info['attachment_id'], self.doc_a.attachment_id.id)
        # Several files, or any folder, are sent as a zip.
        self.assertFalse(
            self.Document.get_download_info([self.doc_a.id, self.doc_b.id], [])['attachment_id'])
        self.assertFalse(self.Document.get_download_info([], [self.child.id])['attachment_id'])
        self.assertEqual(self.Document.get_download_info([], [])['count'], 0)

    def test_folder_download_only_includes_what_the_user_can_read(self):
        viewer_docs = self.env['documents.document'].with_user(self.viewer)
        self.assertFalse(viewer_docs._get_download_entries([], [self.root.id]))

        self.env['documents.share'].with_user(self.admin).action_share_folder_internal(
            self.root.id, [self.viewer.id], 'viewer', False)
        self.assertEqual(
            self._paths(viewer_docs._get_download_entries([], [self.root.id])),
            ['Reports/2026/b.txt', 'Reports/Contract.pdf', 'Reports/a.txt'])

    def test_files_the_user_cannot_read_are_refused(self):
        viewer_docs = self.env['documents.document'].with_user(self.viewer)
        with self.assertRaises(AccessError):
            viewer_docs._get_download_entries([self.doc_a.id], [])
