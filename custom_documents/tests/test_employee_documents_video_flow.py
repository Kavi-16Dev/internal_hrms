from odoo.tests.common import TransactionCase


class TestEmployeeDocumentsVideoFlow(TransactionCase):
    """Regression coverage for the employee Documents flow shown in the
    first 35 seconds of the reference video.
    """

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.company = cls.env.company
        cls.folder_model = cls.env["documents.folder"].sudo()
        cls.document_model = cls.env["documents.document"].sudo()
        cls.user = cls.env["res.users"].sudo().create({
            "name": "Employee Documents Video User",
            "login": "employee-documents-video-%s" % cls.env.cr.dbname,
            "email": "employee.documents.video@example.com",
            "company_id": cls.company.id,
            "group_ids": [(6, 0, [cls.env.ref("custom_documents.group_documents_basic").id])],
        })
        cls.employee = cls.env["hr.employee"].sudo().create({
            "name": "Employee Documents Video Employee",
            "user_id": cls.user.id,
            "company_id": cls.company.id,
        })

    def _enable_hr_centralization(self):
        parent = self.folder_model.search([
            ("company_id", "=", self.company.id),
            ("name", "=", "Employees - Video Test"),
            ("folder_type", "=", "custom"),
        ], limit=1)
        if not parent:
            parent = self.folder_model.create({
                "name": "Employees - Video Test",
                "folder_type": "custom",
                "company_id": self.company.id,
            })
        self.company.write({
            "documents_hr_settings": True,
            "documents_hr_folder_id": parent.id,
            "documents_hr_subfolders": True,
        })
        return parent

    def test_employee_documents_folder_is_shared_with_linked_user(self):
        self._enable_hr_centralization()
        folder = self.employee._get_documents_hr_folder(create=True)
        self.assertEqual(folder.user_id, self.user)
        self.assertIn(self.user, folder.member_ids)
        contracts = self.folder_model.search([
            ('parent_folder_id', '=', folder.id),
            ('name', '=', 'Contracts'),
        ], limit=1)
        self.assertTrue(contracts)


    def test_employee_without_linked_user_still_gets_documents_folder(self):
        self._enable_hr_centralization()
        employee = self.env["hr.employee"].sudo().create({
            "name": "Employee Without User",
            "company_id": self.company.id,
        })
        folder = employee._get_documents_hr_folder(create=True)
        self.assertTrue(folder)
        self.assertEqual(folder.employee_id, employee)
        self.assertEqual(folder.name, employee.name)
        contracts = self.folder_model.search([
            ("parent_folder_id", "=", folder.id),
            ("name", "=", "Contracts"),
        ], limit=1)
        self.assertTrue(contracts)

    def test_uploaded_employee_document_appears_in_shared_with_me_domain(self):
        self._enable_hr_centralization()
        folder = self.employee._get_documents_hr_folder(create=True)
        document = self.document_model.create({
            "name": "Attendance (8).xlsx",
            "folder_id": folder.id,
            "owner_id": self.env.user.id,
            "type": "binary",
        })

        domain = self.document_model.with_user(self.user)._get_shared_with_me_domain()
        visible = self.document_model.with_user(self.user).search(
            domain + [("id", "=", document.id)]
        )
        self.assertIn(document, visible)

    def test_employee_document_count_updates_after_upload(self):
        self._enable_hr_centralization()
        folder = self.employee._get_documents_hr_folder(create=True)
        self.assertEqual(self.employee.with_user(self.user).document_count, 0)

        self.document_model.with_user(self.user).create({
            "name": "Employee File.pdf",
            "folder_id": folder.id,
            "owner_id": self.user.id,
            "type": "binary",
        })

        self.assertEqual(self.employee.with_user(self.user).document_count, 1)

        self.document_model.with_user(self.user).create({
            "name": "Second Employee File.pdf",
            "folder_id": folder.id,
            "owner_id": self.user.id,
            "type": "binary",
        })
        self.assertEqual(self.employee.with_user(self.user).document_count, 2)

    def test_employee_document_count_ignores_empty_requested_document_until_file_upload(self):
        self._enable_hr_centralization()
        folder = self.employee._get_documents_hr_folder(create=True)
        document = self.document_model.with_user(self.user).create({
            'name': 'Requested Contract.pdf',
            'folder_id': folder.id,
            'owner_id': self.user.id,
            'type': 'binary',
            'state': 'requested',
        })
        self.assertEqual(self.employee.with_user(self.user).document_count, 0)

        document.with_user(self.user).write({'datas': 'JVBERi0xLjQK'})
        self.assertEqual(self.employee.with_user(self.user).document_count, 1)

        document.with_user(self.user).unlink()
        self.assertEqual(self.employee.with_user(self.user).document_count, 0)

    def test_employee_document_count_includes_contracts_subfolder(self):
        self._enable_hr_centralization()
        folder = self.employee._get_documents_hr_folder(create=True)
        contracts = self.folder_model.search([
            ("parent_folder_id", "=", folder.id),
            ("name", "=", "Contracts"),
        ], limit=1)
        self.assertTrue(contracts)
        self.document_model.sudo().create({
            "name": "Contract.pdf",
            "folder_id": contracts.id,
            "owner_id": self.user.id,
            "type": "binary",
        })
        self.assertEqual(self.employee.with_user(self.user).document_count, 1)

    def test_employee_documents_are_private_to_the_linked_user(self):
        self._enable_hr_centralization()
        other_user = self.env["res.users"].sudo().create({
            "name": "Other Documents User",
            "login": "other-documents-%s" % self.env.cr.dbname,
            "email": "other.documents@example.com",
            "company_id": self.company.id,
            "group_ids": [(6, 0, [self.env.ref("custom_documents.group_documents_basic").id])],
        })
        other_employee = self.env["hr.employee"].sudo().create({
            "name": "Other Employee",
            "user_id": other_user.id,
            "company_id": self.company.id,
        })

        my_folder = self.employee._get_documents_hr_folder(create=True)
        other_folder = other_employee._get_documents_hr_folder(create=True)
        my_document = self.document_model.sudo().create({
            "name": "My Private File.pdf",
            "folder_id": my_folder.id,
            "owner_id": self.user.id,
            "type": "binary",
        })
        other_document = self.document_model.sudo().create({
            "name": "Other Private File.pdf",
            "folder_id": other_folder.id,
            "owner_id": other_user.id,
            "type": "binary",
        })

        user_docs = self.document_model.with_user(self.user).search([])
        self.assertIn(my_document, user_docs)
        self.assertNotIn(other_document, user_docs)

        user_folders = self.folder_model.with_user(self.user).search([])
        self.assertIn(my_folder, user_folders)
        self.assertNotIn(other_folder, user_folders)
        self.assertEqual(self.employee.with_user(self.user).document_count, 1)
        self.assertEqual(other_employee.with_user(self.user).document_count, 0)

    def test_documents_administrator_can_see_all_employee_documents(self):
        self._enable_hr_centralization()
        other_user = self.env["res.users"].sudo().create({
            "name": "Administrator Test Employee User",
            "login": "admin-employee-%s" % self.env.cr.dbname,
            "email": "admin.employee@example.com",
            "company_id": self.company.id,
            "group_ids": [(6, 0, [self.env.ref("custom_documents.group_documents_basic").id])],
        })
        other_employee = self.env["hr.employee"].sudo().create({
            "name": "Administrator Test Employee",
            "user_id": other_user.id,
            "company_id": self.company.id,
        })
        other_folder = other_employee._get_documents_hr_folder(create=True)
        other_document = self.document_model.sudo().create({
            "name": "Administrator Visible File.pdf",
            "folder_id": other_folder.id,
            "owner_id": other_user.id,
            "type": "binary",
        })

        admin = self.env.ref("base.user_admin")
        admin_docs = self.document_model.with_user(admin).search([])
        self.assertIn(other_document, admin_docs)
        self.assertEqual(
            other_employee.with_user(admin).document_count, 1,
        )

    def test_employee_documents_action_keeps_upload_in_current_employee_folder(self):
        """The Documents smart button must pass the employee folder as the
        current workspace so New -> Upload stores the file there."""
        self._enable_hr_centralization()
        folder = self.employee._get_documents_hr_folder(create=True)
        action = self.employee.action_view_documents()

        self.assertEqual(action['res_model'], 'documents.document')
        self.assertEqual(action['context']['default_folder_id'], folder.id)
        self.assertEqual(action['context']['documents_folder_id'], folder.id)
        self.assertEqual(action['domain'], [('folder_id', 'child_of', folder.id)])

        document = self.document_model.create({
            'name': 'Offer Letter - Video Flow.pdf',
            'datas': 'JVBERi0xLjQK',
            'type': 'binary',
            'folder_id': action['context']['documents_folder_id'],
        })
        self.assertEqual(document.folder_id, folder)
        self.assertTrue(document.attachment_id)
