# -*- coding: utf-8 -*-
from odoo import api, fields, models, _
from odoo.exceptions import UserError


class DocumentsFolder(models.Model):
    _name = 'documents.folder'
    _description = 'Document Workspace / Folder'
    _order = 'sequence, name'
    _parent_store = True
    _parent_name = 'parent_folder_id'

    name = fields.Char(required=True, translate=True)
    sequence = fields.Integer(default=10)
    active = fields.Boolean(default=True)
    description = fields.Html()
    color = fields.Integer(string='Color Index')
    is_inbox = fields.Boolean(
        string='Inbox', default=False, index=True, copy=False,
        help='Marks the company Inbox workspace used by the Documents Inbox section.')

    parent_folder_id = fields.Many2one(
        'documents.folder', string='Parent Workspace', ondelete='cascade',
        index=True)

    is_employee_root = fields.Boolean( string='Employee Root Folder', default=False, copy=False,
            help='True only on the single top-level folder created for an '
                'employee via HR centralization. Distinguishes it from '
                'children like Contracts, which also carry employee_id.')

    parent_path = fields.Char(index=True, unaccent=False)
    children_folder_ids = fields.One2many(
        'documents.folder', 'parent_folder_id', string='Sub-Workspaces')

    folder_type = fields.Selection([
        ('company', 'Company Drive'),
        ('employee', 'Employee Drive'),
        ('custom', 'Custom Workspace'),
    ], string='Type', default='custom', required=True)

    # Owner of a personal / employee drive. Empty for shared workspaces.
    user_id = fields.Many2one(
        'res.users', string='Drive Owner',
        help='For an Employee Drive, the user this private drive belongs to.')

    # HR centralization links an employee directly to the folder shown in
    # Documents > Company > Employees.  This is intentionally separate from
    # user_id because an employee does not need a linked Odoo user for the
    # folder to exist.
    employee_id = fields.Many2one(
        'hr.employee', string='Employee', index=True, copy=False,
        ondelete='cascade',
        help='Employee whose centralized HR Documents folder this is.')

    company_id = fields.Many2one(
        'res.company', string='Company', default=lambda s: s.env.company)

    # Access: users explicitly granted access on top of the drive owner
    # and Documents Managers (who always see everything).
    member_ids = fields.Many2many(
        'res.users', 'documents_folder_member_rel', 'folder_id', 'user_id',
        string='Members',
        help='Users who can access this workspace in addition to its owner '
             'and Documents Managers.')

    document_ids = fields.One2many(
        'documents.document', 'folder_id', string='Documents')
    document_count = fields.Integer(
        compute='_compute_document_count', string='Document Count')

    tag_category_ids = fields.One2many(
        'documents.tag.category', 'folder_id', string='Tag Categories')

    # _sql_constraints = [
    #     ('employee_folder_user_uniq',
    #      'unique(user_id, folder_type, company_id)',
    #      'This user already has an Employee Drive in this company.'),
    #     ('hr_employee_folder_uniq',
    #      'unique(employee_id, company_id)',
    #      'This employee already has a centralized Documents folder in this company.'),
    # ]

    _sql_constraints = [
        ('employee_folder_user_uniq',
        'unique(user_id, folder_type, company_id)',
        'This user already has an Employee Drive in this company.'),
        ('hr_employee_folder_uniq',
        'unique(employee_id, company_id, parent_folder_id)',   # <-- add parent_folder_id
        'This employee already has a centralized Documents folder in this company.'),
    ]

    @api.depends('document_ids', 'document_ids.active', 'document_ids.attachment_id',
                 'document_ids.type')
    def _compute_document_count(self):
        for folder in self:
            # Count actual uploaded files only. Requested placeholders and
            # empty document records must not increase the Documents count.
            folder.document_count = len(folder.document_ids.filtered(
                lambda document: document.active
                and document.type == 'binary'
                and document.attachment_id
            ))

    @api.model_create_multi
    def create(self, vals_list):
        """Keep employee ownership on every subfolder.

        Employee Documents can contain folders such as Contracts.  The
        employee security boundary must follow the whole folder tree, not
        only the root folder.
        """
        for vals in vals_list:
            parent_id = vals.get('parent_folder_id')
            if parent_id and not vals.get('employee_id'):
                parent = self.sudo().browse(parent_id).exists()
                if parent and parent.employee_id:
                    vals['employee_id'] = parent.employee_id.id
        return super().create(vals_list)

    def write(self, vals):
        res = super().write(vals)
        if 'parent_folder_id' in vals:
            for folder in self:
                if folder.parent_folder_id and folder.parent_folder_id.employee_id:
                    folder.sudo().write({
                        'employee_id': folder.parent_folder_id.employee_id.id,
                    })
        return res

    def name_get(self):
        result = []
        for folder in self:
            name = folder.name
            if folder.parent_folder_id:
                name = f'{folder.parent_folder_id.name} / {name}'
            result.append((folder.id, name))
        return result

    @api.model
    def get_documents_view_folders(self, category="all", current_folder_id=False):
        """Return the real folder cards shown above Documents kanban files.

        The reference Documents browser behaves as follows:
        * All: show every accessible custom workspace in a flat browser.
        * Company: show the immediate children of Company Drive.
        * A folder: show the immediate children of that folder.
        * My Drive / Shared with me / Recent / Trash: no folder cards.

        This method intentionally uses the current user's normal ORM access
        rules. It never sudoes the result, so the folder browser cannot leak
        workspaces that the current user cannot open.
        """
        category = category or "all"
        Folder = self.env["documents.folder"]

        if current_folder_id:
            current = Folder.browse(int(current_folder_id)).exists()
            if not current:
                return []
            folders = Folder.search([
                ("parent_folder_id", "=", current.id),
                ("active", "=", True),
            ], order="sequence, name, id")
        elif category == "company":
            company_drive = self._get_or_create_company_drive(self.env.company)
            folders = Folder.search([
                ("parent_folder_id", "=", company_drive.id),
                ("active", "=", True),
            ], order="sequence, name, id")
        elif category == "all":
            # The All browser shows custom workspaces across the company tree
            # but does not show the invisible/root drive records themselves.
            folders = Folder.search([
                ("active", "=", True),
                ("folder_type", "=", "custom"),
            ], order="sequence, name, id")
        else:
            return []

        return [{
            "id": folder.id,
            "name": folder.name,
            "parent_id": folder.parent_folder_id.id or False,
            "parent_name": folder.parent_folder_id.name or False,
            "folder_type": folder.folder_type,
            "document_count": folder.document_count,
            "color": folder.color,
        } for folder in folders]

    def action_open_documents(self):
        self.ensure_one()
        category = 'all'
        root = self
        while root.parent_folder_id:
            root = root.parent_folder_id
        if root.folder_type == 'company':
            category = 'company'
        elif root.folder_type == 'employee' and root.user_id == self.env.user:
            category = 'my_drive'

        # Odoo 19's action service expects a fully normalized act_window
        # action.  In particular, the returned action must contain a `views`
        # array.  Returning only `view_mode` works in some older clients but
        # causes `_preprocessAction` to execute `.map()` on undefined in Odoo
        # 19 when the action is opened through `doAction()`.
        kanban_view = self.env.ref(
            'custom_documents.documents_document_view_kanban').id
        list_view = self.env.ref(
            'custom_documents.documents_document_view_list').id
        form_view = self.env.ref(
            'custom_documents.documents_document_view_form').id
        search_view = self.env.ref(
            'custom_documents.documents_document_view_search').id

        return {
            'type': 'ir.actions.act_window',
            'name': self.name,
            'res_model': 'documents.document',
            'views': [
                [kanban_view, 'kanban'],
                [list_view, 'list'],
                [form_view, 'form'],
            ],
            'view_mode': 'kanban,list,form',
            'view_id': kanban_view,
            'search_view_id': search_view,
            'domain': [('folder_id', 'child_of', self.id)],
            'context': {
                'default_folder_id': self.id,
                'documents_folder_id': self.id,
                'documents_sidebar_category': category,
            },
            'target': 'current',
        }

    @api.model
    def _get_or_create_company_inbox(self, company):
        """Return the default Inbox under the company drive.

        The Request dialog in Odoo Documents defaults to Inbox. Keep that
        behavior in Community while making the folder lazy and multi-company.
        Existing folders named Inbox are reused.
        """
        company = company or self.env.company
        drive = self._get_or_create_company_drive(company)
        inbox = self.sudo().search([
            ('parent_folder_id', '=', drive.id),
            ('company_id', '=', company.id),
            ('name', '=', _('Inbox')),
            ('active', '=', True),
        ], limit=1)
        if not inbox:
            inbox = self.sudo().create({
                'name': _('Inbox'),
                'folder_type': 'custom',
                'parent_folder_id': drive.id,
                'company_id': company.id,
                'is_inbox': True,
            })
        elif not inbox.is_inbox:
            inbox.sudo().write({'is_inbox': True})
        return inbox

    # @api.model
    # def _get_or_create_employee_drive(self, user):
    #     """Return the private Employee Drive of `user`, creating it on the fly
    #     the first time it is needed (lazy provisioning, mirrors Enterprise's
    #     automatic 'My Drive' folder)."""
    #     folder = self.sudo().search([
    #         ('folder_type', '=', 'employee'),
    #         ('user_id', '=', user.id),
    #         ('company_id', '=', user.company_id.id),
    #     ], limit=1)
    #     if not folder:
    #         folder = self.sudo().create({
    #             'name': _('%s\'s Drive', user.name),
    #             'folder_type': 'employee',
    #             'user_id': user.id,
    #             'company_id': user.company_id.id,
    #         })
    #     return folder

    @api.model
    def _get_or_create_employee_drive(self, user):
        folder = self.sudo().search([
            ('folder_type', '=', 'employee'),
            ('user_id', '=', user.id),
            ('company_id', '=', user.company_id.id),
        ], limit=1)
        if not folder:
            company_drive = self._get_or_create_company_drive(user.company_id)
            folder = self.sudo().create({
                'name': _('%s\'s Drive', user.name),
                'folder_type': 'employee',
                'user_id': user.id,
                'company_id': user.company_id.id,
                'parent_folder_id': company_drive.id,   # <-- was missing
            })
        return folder

    @api.model
    def _get_or_create_company_drive(self, company):
        folder = self.sudo().search([
            ('folder_type', '=', 'company'),
            ('company_id', '=', company.id),
        ], limit=1)
        if not folder:
            folder = self.sudo().create({
                'name': _('Company Drive'),
                'folder_type': 'company',
                'company_id': company.id,
            })
        return folder

    @api.model
    def get_company_drive_id(self):
        """Public, RPC-callable wrapper around ``_get_or_create_company_drive``
        for the current user's company. Used by the web client's 'New' menu
        to know where to file documents/folders created from a screen that
        has no specific workspace selected (e.g. the Company Drive root)."""
        return self._get_or_create_company_drive(self.env.company).id

    @api.model
    def get_my_drive_id(self):
        """Public, RPC-callable wrapper around ``_get_or_create_employee_drive``
        for the current user. Used by the web client's 'New' menu as the
        fallback destination when uploading/creating from a context-less
        screen (All, Recent, Shared with me, Trash)."""
        return self._get_or_create_employee_drive(self.env.user).id

    def unlink(self):
        for folder in self:
            if folder.folder_type in ('company', 'employee'):
                raise UserError(_(
                    'The default Company Drive and Employee Drives cannot '
                    'be deleted.'))
        return super().unlink()
