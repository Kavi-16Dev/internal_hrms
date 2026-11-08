# -*- coding: utf-8 -*-
from odoo import api, fields, models, _, SUPERUSER_ID
from odoo.exceptions import AccessError, UserError

ACCESS_LEVELS = [
    ('none', 'None'),
    ('viewer', 'Viewer'),
    ('editor', 'Editor'),
]
ACCESS_RANK = {'none': 0, 'viewer': 1, 'editor': 2}


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

    # -- Sharing ----------------------------------------------------------
    # Folder sharing is inherited: whatever is granted on a folder also
    # applies to every sub-folder and document below it.
    #
    # * General access (Share dialog > "General Access") is stored on the
    #   folder itself; the ``effective_*`` fields add what the ancestors
    #   grant, so record rules never have to walk the tree.
    # * Per-person access lives on ``documents.share`` records
    #   (share_type = 'folder').  ``shared_user_ids`` / ``shared_editor_ids``
    #   are a denormalized index of those shares, already expanded to the
    #   descendants of the shared folder.  It is rebuilt with SQL by
    #   ``documents.share._sync_folder_shared_index`` (see that method).
    access_internal = fields.Selection(
        ACCESS_LEVELS, string='Internal Users Access', default='none',
        required=True, copy=False,
        help='Access granted to every internal user on this folder, its '
             'sub-folders and its documents.')
    access_via_link = fields.Selection(
        ACCESS_LEVELS, string='Access Through Link', default='none',
        required=True, copy=False,
        help='Whether anyone holding the folder link may open its files. '
             '"Editor" additionally allows downloading the files.')
    effective_access_internal = fields.Selection(
        ACCESS_LEVELS, string='Effective Internal Access',
        compute='_compute_effective_access', store=True, recursive=True,
        index=True,
        help='Highest internal access granted on this folder or any of its '
             'ancestors.')
    effective_access_via_link = fields.Selection(
        ACCESS_LEVELS, string='Effective Link Access',
        compute='_compute_effective_access', store=True, recursive=True,
        index=True,
        help='Highest link access granted on this folder or any of its '
             'ancestors.')
    shared_user_ids = fields.Many2many(
        'res.users', 'documents_folder_shared_user_rel', 'folder_id', 'user_id',
        string='Shared With', copy=False, readonly=True,
        help='Internal users who can read this folder, through a share on it '
             'or on one of its ancestors.')
    shared_editor_ids = fields.Many2many(
        'res.users', 'documents_folder_shared_editor_rel', 'folder_id', 'user_id',
        string='Shared With (Editors)', copy=False, readonly=True,
        help='Subset of "Shared With" holding the Editor role.')

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

    @api.depends('access_internal', 'access_via_link',
                 'parent_folder_id.effective_access_internal',
                 'parent_folder_id.effective_access_via_link')
    def _compute_effective_access(self):
        """A folder is at least as open as its parent: general access set on
        a folder is inherited by everything below it."""
        for folder in self:
            parent = folder.parent_folder_id
            folder.effective_access_internal = max(
                folder.access_internal or 'none',
                parent.effective_access_internal or 'none',
                key=ACCESS_RANK.get)
            folder.effective_access_via_link = max(
                folder.access_via_link or 'none',
                parent.effective_access_via_link or 'none',
                key=ACCESS_RANK.get)

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
        folders = super().create(vals_list)
        # A new sub-folder inherits the people its parent is shared with.
        if any(vals.get('parent_folder_id') for vals in vals_list):
            folders._sync_folder_shared_index_if_needed()
        return folders

    def write(self, vals):
        if ('access_internal' in vals or 'access_via_link' in vals) \
                and self.env.uid != SUPERUSER_ID:
            # General access is only changed through the Share dialog, which
            # checks this too; this stops other write paths (e.g. the backend
            # form) from bypassing the owner restriction.
            for folder in self:
                if not folder._can_manage_access():
                    raise AccessError(_(
                        'Only the owner of a folder or a Documents '
                        'Administrator can change its general access.'))
        res = super().write(vals)
        if 'parent_folder_id' in vals:
            for folder in self:
                if folder.parent_folder_id and folder.parent_folder_id.employee_id:
                    folder.sudo().write({
                        'employee_id': folder.parent_folder_id.employee_id.id,
                    })
            # Moving a folder changes which shares it inherits.
            self._sync_folder_shared_index_if_needed()
        return res

    def _sync_folder_shared_index_if_needed(self):
        """Rebuild the folder sharing index, but only when some folder is
        shared at all (otherwise the index is empty and stays empty)."""
        has_folder_share = self.env['documents.share'].sudo().search_count([
            ('share_type', '=', 'folder'),
            ('state', '=', 'active'),
        ], limit=1)
        if has_folder_share:
            self.env['documents.share']._sync_folder_shared_index()

    # ------------------------------------------------------------------
    # Sharing helpers
    # ------------------------------------------------------------------
    def _can_manage_access(self):
        """Whether the current user may share this folder and change its
        general access: Documents Administrators, or the owner of an
        ordinary workspace / personal drive.

        The Company Drive, the Inbox and employee (HR) folders are
        restricted to Administrators so that private HR files cannot be
        opened up by whoever happened to create the record."""
        self.ensure_one()
        user = self.env.user
        if user.has_group('custom_documents.group_documents_manager'):
            return True
        folder = self.sudo()
        if folder.folder_type == 'company' or folder.is_inbox or folder.employee_id:
            return False
        owner = folder.user_id or folder.create_uid
        return owner == user

    def _get_ancestor_folders(self):
        """Ancestors of this folder, nearest first, without sudo checks
        (callers decide what to expose)."""
        self.ensure_one()
        ancestors = self.env['documents.folder'].sudo()
        parent = self.sudo().parent_folder_id
        while parent:
            ancestors |= parent
            parent = parent.parent_folder_id
        return ancestors

    @api.model
    def get_folder_share_state(self, folder_id):
        """Small payload used by the kanban header to decide whether to show
        its Share button for the folder currently open."""
        folder = self.browse(folder_id).exists()
        if not folder:
            return False
        folder.check_access('read')
        return {
            'id': folder.id,
            'name': folder.name,
            'can_share': folder._can_manage_access(),
        }

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
            # The Inbox is created lazily; make sure it exists so it is
            # always listed inside the Company Drive.
            self._get_or_create_company_inbox(self.env.company)
            folders = Folder.search([
                ("parent_folder_id", "=", company_drive.id),
                ("active", "=", True),
            ], order="sequence, name, id")
        elif category == "all":
            # The All browser shows custom workspaces across the company tree
            # but does not show the invisible/root drive records themselves.
            self._get_or_create_company_inbox(self.env.company)
            # Folders shared with the user (for example somebody's employee
            # folder) are listed too, even though they are not "custom".
            folders = Folder.search([
                ("active", "=", True),
                "|",
                ("folder_type", "=", "custom"),
                "&",
                ("folder_type", "!=", "company"),
                "|",
                ("shared_user_ids", "in", [self.env.uid]),
                ("effective_access_internal", "in", ["viewer", "editor"]),
            ], order="sequence, name, id")
        elif category == "shared_with_me":
            # Folders somebody else shared with the current user, either
            # with them personally or with all internal users.  Only the
            # top-most shared folder of a tree is listed: its sub-folders are
            # reached by opening it.
            uid = self.env.uid
            shared = Folder.search([
                ("active", "=", True),
                ("folder_type", "!=", "company"),
                "|",
                ("shared_user_ids", "in", [uid]),
                ("effective_access_internal", "in", ["viewer", "editor"]),
            ], order="sequence, name, id")
            shared = shared.filtered(
                lambda f: (f.sudo().user_id or f.sudo().create_uid).id != uid)
            folders = shared.filtered(lambda f: f.parent_folder_id not in shared)
        else:
            return []

        result = []
        for folder in folders:
            # A shared folder's parent is usually NOT readable by the person
            # it was shared with.  Reading ``parent.name`` would then raise
            # an AccessError and the whole browser would fail to load, so
            # only expose the parent when the user may read it.
            parent = folder.parent_folder_id
            if parent and not parent.has_access("read"):
                parent = Folder
            result.append(self._folder_card_values(folder, parent))
        return result

    @api.model
    def get_sidebar_folder_tree(self):
        """Folder trees shown under the menus of the Documents sidebar.

        Returns ``{category: [node, ...]}`` for ``all`` (workspaces that are
        not under the Company Drive nor a My Drive), ``company`` (inside the
        Company Drive), ``my_drive`` (inside the user's own drive) and
        ``shared_with_me``.  A node is ``{id, name, children: [node, ...]}``.
        Everything goes through the normal access rules (no sudo), so a user
        only ever gets the folders they may open.
        """
        Folder = self.env['documents.folder']
        order = 'sequence, name, id'

        def build(roots):
            if not roots:
                return []
            tree = Folder.search([
                ('id', 'child_of', roots.ids),
                ('active', '=', True),
                ('folder_type', '!=', 'employee'),
            ], order=order)
            by_parent = {}
            for folder in tree:
                by_parent.setdefault(folder.parent_folder_id.id, []).append(folder)

            def node(folder, seen):
                if folder.id in seen:  # safety net against corrupted data
                    return None
                seen = seen | {folder.id}
                children = [node(child, seen) for child in by_parent.get(folder.id, [])]
                return {
                    'id': folder.id,
                    'name': folder.name,
                    'children': [child for child in children if child],
                }

            return [n for n in (node(root, frozenset()) for root in roots) if n]

        company_drive = self._get_or_create_company_drive(self.env.company)
        my_drive = self._get_or_create_employee_drive(self.env.user)
        self._get_or_create_company_inbox(self.env.company)

        company_roots = Folder.search([
            ('parent_folder_id', '=', company_drive.id),
            ('active', '=', True),
            ('folder_type', '!=', 'employee'),
        ], order=order)
        my_roots = Folder.search([
            ('parent_folder_id', '=', my_drive.id),
            ('active', '=', True),
        ], order=order)
        all_roots = Folder.search([
            ('parent_folder_id', '=', False),
            ('folder_type', '=', 'custom'),
            ('active', '=', True),
        ], order=order)
        shared_ids = [
            card['id'] for card in self.get_documents_view_folders('shared_with_me')]

        return {
            'all': build(all_roots),
            'company': build(company_roots),
            'my_drive': build(my_roots),
            'shared_with_me': build(Folder.browse(shared_ids)),
        }

    def _folder_card_values(self, folder, parent):
        return {
            "id": folder.id,
            "name": folder.name,
            "parent_id": parent.id or False,
            "parent_name": parent.name or False,
            "folder_type": folder.folder_type,
            "document_count": folder.document_count,
            "color": folder.color,
            "can_share": folder._can_manage_access(),
        }

    def action_open_documents(self):
        self.ensure_one()
        category = 'all'
        # Walk up with sudo: the ancestors of a shared folder are often not
        # readable by the person it was shared with.
        root = self.sudo()
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
        """Return the private My Drive of `user`, creating it if needed.

        A My Drive is a ROOT workspace: it must never sit under the Company
        Drive.  Being a child of the Company Drive made everything a user
        uploaded to My Drive show up in Company (the Company view lists the
        content of the Company Drive tree) and made the drive inherit the
        Company Drive's general access.
        """
        folder = self.sudo().search([
            ('folder_type', '=', 'employee'),
            ('user_id', '=', user.id),
            ('company_id', '=', user.company_id.id),
        ], limit=1)
        if not folder:
            folder = self.sudo().create({
                'name': _('%s\'s Drive', user.name),
                'folder_type': 'employee',
                'user_id': user.id,
                'company_id': user.company_id.id,
            })
        elif folder.parent_folder_id:
            # Self-heal drives created by older versions under Company Drive.
            folder.write({'parent_folder_id': False})
        return folder

    @api.model
    def _detach_employee_drives_from_company(self):
        """Move every existing My Drive out of the Company Drive tree
        (used by the upgrade script)."""
        drives = self.sudo().with_context(active_test=False).search([
            ('folder_type', '=', 'employee'),
            ('parent_folder_id', '!=', False),
        ])
        drives.write({'parent_folder_id': False})
        return len(drives)

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

    # ------------------------------------------------------------------
    # Actions-menu entries (Rename / Move / Copy Links) for workspaces
    # ------------------------------------------------------------------
    def action_rename(self, new_name):
        """'Rename' Actions-menu entry for a workspace."""
        self.ensure_one()
        new_name = (new_name or '').strip()
        if not new_name:
            raise UserError(_('Please enter a name.'))
        self.name = new_name

    def action_move(self, folder_id):
        """'Move' Actions-menu entry: put the workspace under another one."""
        self.ensure_one()
        if self.folder_type in ('company', 'employee') or self.is_inbox:
            raise UserError(_(
                'The default Company, Inbox and Employee drives cannot be moved.'))
        target = self.browse(folder_id).exists()
        if not target:
            raise UserError(_('Please select a destination workspace.'))
        if target == self or target.id in self.search(
                [('id', 'child_of', self.id)]).ids:
            raise UserError(_(
                'A workspace cannot be moved into itself or into one of its '
                'sub-workspaces.'))
        # The workspace takes the access settings of its new parent.
        self.write({
            'parent_folder_id': target.id,
            'access_internal': 'none',
            'access_via_link': 'none',
        })

    def action_create_shortcut(self, destination_folder_id):
        """'Create Shortcut' Actions-menu entry for a workspace: adds an entry
        in the destination workspace that opens this workspace."""
        self.ensure_one()
        destination = self.browse(destination_folder_id).exists()
        if not destination:
            raise UserError(_('Please select a destination workspace.'))
        if destination == self:
            raise UserError(_('A workspace cannot contain a shortcut to itself.'))
        return self.env['documents.document'].create({
            'name': self.name,
            'type': 'folder',
            'folder_id': destination.id,
            'shortcut_folder_id': self.id,
        })

    @api.model
    def get_shortcut_destination_tree(self):
        """Destinations offered by the 'Create Shortcut' dialog: My Drive and
        Company first, then the other workspaces, each with its sub-folders.
        Nodes are ``{id, name, children}``."""
        tree = self.get_sidebar_folder_tree()
        my_drive = self._get_or_create_employee_drive(self.env.user)
        company_drive = self._get_or_create_company_drive(self.env.company)
        return [
            {'id': my_drive.id, 'name': _('My Drive'), 'children': tree['my_drive']},
            {'id': company_drive.id, 'name': _('Company'), 'children': tree['company']},
        ] + tree['all']

    def action_copy_link(self):
        """'Copy Links' Actions-menu entry: tokenized share URL of the
        workspace (same mechanism as for documents)."""
        self.ensure_one()
        share = self.env['documents.share']._get_or_create_folder_link_share(self)
        base_url = self.env['ir.config_parameter'].sudo().get_param('web.base.url')
        return f'{base_url.rstrip("/")}/document/share/{share.access_token}'

    def unlink(self):
        for folder in self:
            if folder.folder_type in ('company', 'employee'):
                raise UserError(_(
                    'The default Company Drive and Employee Drives cannot '
                    'be deleted.'))
        return super().unlink()
