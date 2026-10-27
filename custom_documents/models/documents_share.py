# -*- coding: utf-8 -*-
import uuid
from datetime import timedelta

from odoo import api, fields, models, _, Command
from odoo.exceptions import AccessError, UserError


class DocumentsShare(models.Model):
    _name = 'documents.share'
    _description = 'Document Share Link'
    _inherit = ['mail.thread']
    _order = 'create_date desc'
    _rec_name = 'name'

    name = fields.Char(compute='_compute_name', store=True)
    access_token = fields.Char(
        default=lambda s: str(uuid.uuid4()), copy=False, readonly=True,
        index=True)

    share_type = fields.Selection([
        ('ids', 'Selected Documents'),
        ('folder', 'Whole Workspace'),
    ], default='ids', required=True)

    folder_id = fields.Many2one('documents.folder', string='Workspace')
    document_ids = fields.Many2many(
        'documents.document', 'documents_share_document_rel',
        'share_id', 'document_id', string='Documents')

    # Internal users explicitly granted access by the Share dialog.
    recipient_user_ids = fields.Many2many(
        'res.users', 'documents_share_user_rel',
        'share_id', 'user_id', string='People with access')

    access_mode = fields.Selection([
        ('view', 'Viewer'),
        ('download', 'Viewer + Download'),
        ('upload', 'Can Upload (Request)'),
    ], default='view', required=True, tracking=True)

    # Values used by the Share dialog shown in the reference video.
    role = fields.Selection([
        ('viewer', 'Viewer'),
        ('editor', 'Editor'),
    ], default='viewer', required=True, tracking=True)
    notify = fields.Boolean(string='Notify', default=True)
    message = fields.Text(string='Message')
    internal_access = fields.Selection([
        ('none', 'None'),
        ('viewer', 'Internal Users — Viewer'),
        ('editor', 'Internal Users — Editor'),
    ], default='none', required=True)

    is_document_link = fields.Boolean(
        string='Document Link', default=False, copy=False,
        help='The "Copy Link" share of a document. It only opens the file '
             'while the document\'s "Access through link" is not None.')

    partner_id = fields.Many2one('res.partner', string='Shared With')
    email = fields.Char(string="Recipient's Email")
    date_deadline = fields.Date(
        string='Expiration Date', default=lambda s: s._default_date_deadline())
    state = fields.Selection([
        ('active', 'Active'),
        ('expired', 'Expired'),
        ('revoked', 'Revoked'),
    ], default='active', required=True, tracking=True)

    owner_id = fields.Many2one(
        'res.users', string='Shared By', default=lambda s: s.env.user)
    company_id = fields.Many2one(
        'res.company', default=lambda s: s.env.company)
    full_url = fields.Char(compute='_compute_full_url', string='Share Link')

    @api.model
    def _default_date_deadline(self):
        days = int(self.env['ir.config_parameter'].sudo().get_param(
            'custom_documents.share_default_validity', default='7') or 0)
        if days > 0:
            return fields.Date.context_today(self) + timedelta(days=days)
        return False

    @api.depends('share_type', 'folder_id', 'document_ids')
    def _compute_name(self):
        for share in self:
            if share.share_type == 'folder' and share.folder_id:
                share.name = _('Share: %s', share.folder_id.name)
            elif share.document_ids:
                share.name = _('Share: %s', ', '.join(share.document_ids.mapped('name')[:3]))
            else:
                share.name = _('Share Link')

    def _compute_full_url(self):
        base_url = self.env['ir.config_parameter'].sudo().get_param('web.base.url')
        for share in self:
            share.full_url = f'{base_url}/document/share/{share.access_token}' if base_url else False

    def action_revoke(self):
        self.write({'state': 'revoked'})

    def _check_valid(self):
        self.ensure_one()
        if self.state != 'active':
            return False
        if self.date_deadline and self.date_deadline < fields.Date.today():
            if self.state == 'active':
                self.state = 'expired'
            return False
        return True

    def _get_shared_documents(self):
        self.ensure_one()
        if self.share_type == 'folder' and self.folder_id:
            if self.is_document_link and \
                    self.folder_id.sudo().effective_access_via_link not in ('viewer', 'editor'):
                # Same rule as for a document: closing "Access through link"
                # on the folder (and on all its ancestors) closes the link
                # even though the token itself is still active.
                return self.env['documents.document'].sudo()
            return self.env['documents.document'].sudo().search(
                [('folder_id', 'child_of', self.folder_id.id)])
        documents = self.document_ids
        if self.is_document_link:
            # General access: closing "Access through link" must close the
            # link even though the token itself is still active.
            documents = documents.sudo().filtered(
                lambda doc: doc.access_via_link in ('viewer', 'editor'))
        return documents

    @api.model
    def _sync_shared_user_index(self, documents):
        """Rebuild the explicit-recipient index for the given documents.

        ``documents.document.shared_user_ids`` is a denormalized index used
        by both the Shared with me action and the document record rule.  The
        previous implementation rebuilt the M2M through an ORM ``write``.
        That can be unreliable when the share operation is performed through
        a different user/context because the document's record rules may
        affect the intermediate recordset.

        Here the share records remain the single source of truth and the
        relation table is rebuilt with SQL under the current transaction.
        This is deterministic and does not depend on the recipient having
        access to the original workspace.
        """
        documents = documents.sudo().exists()
        if not documents:
            return

        document_ids = tuple(documents.ids)
        if not document_ids:
            return

        # Make pending ORM M2M commands visible to the SQL rebuild.
        self.env.flush_all()

        self.env.cr.execute(
            """
            DELETE FROM documents_document_shared_user_rel
             WHERE document_id IN %s
            """,
            [document_ids],
        )

        # Rebuild from documents.share, the authoritative sharing records.
        # The SQL intentionally bypasses recipient document/folder record
        # rules: the recipient may have no access to the original workspace.
        self.env.cr.execute(
            """
            INSERT INTO documents_document_shared_user_rel (document_id, user_id)
            SELECT DISTINCT rel.document_id, user_rel.user_id
              FROM documents_share_document_rel rel
              JOIN documents_share share
                ON share.id = rel.share_id
              JOIN documents_share_user_rel user_rel
                ON user_rel.share_id = share.id
             WHERE rel.document_id IN %s
               AND share.state = 'active'
               AND share.share_type = 'ids'
               AND user_rel.user_id IS NOT NULL
            ON CONFLICT DO NOTHING
            """,
            [document_ids],
        )

        documents.invalidate_recordset(['shared_user_ids'])

    @api.model
    def rebuild_shared_user_index(self):
        """Rebuild the complete explicit-share recipient index.

        This is intentionally callable by administrators/cron and is also
        useful after importing old share records or restoring a database.
        It makes Shared with me self-healing instead of depending solely on
        the original share transaction.
        """
        self.env.flush_all()
        self.env.cr.execute(
            "DELETE FROM documents_document_shared_user_rel"
        )
        self.env.cr.execute(
            """
            INSERT INTO documents_document_shared_user_rel (document_id, user_id)
            SELECT DISTINCT rel.document_id, user_rel.user_id
              FROM documents_share_document_rel rel
              JOIN documents_share share ON share.id = rel.share_id
              JOIN documents_share_user_rel user_rel ON user_rel.share_id = share.id
             WHERE share.state = 'active'
               AND share.share_type = 'ids'
               AND user_rel.user_id IS NOT NULL
            ON CONFLICT DO NOTHING
            """
        )
        self.env['documents.document'].invalidate_model(['shared_user_ids'])
        self._sync_folder_shared_index()
        return True

    @api.model
    def _sync_folder_shared_index(self):
        """Rebuild the folder sharing index from the active folder shares.

        ``documents.folder.shared_user_ids`` / ``shared_editor_ids`` list who
        may read / edit each folder.  A share on folder F applies to F and to
        every folder below it, so the index is expanded to the descendants
        here (``parent_path`` of a descendant starts with the parent_path of
        F) and record rules only ever look at one hop:
        ``folder_id.shared_user_ids``.

        As for documents, the share records stay the single source of truth
        and the relation tables are rebuilt with SQL, which is deterministic
        and independent of the recipients' own record rules.  Shares past
        their expiration date are ignored, so the daily rebuild also
        enforces expiry.
        """
        self.env.flush_all()
        cr = self.env.cr
        cr.execute("DELETE FROM documents_folder_shared_user_rel")
        cr.execute("DELETE FROM documents_folder_shared_editor_rel")
        base_from = """
              FROM documents_share share
              JOIN documents_share_user_rel user_rel
                ON user_rel.share_id = share.id
              JOIN documents_folder root
                ON root.id = share.folder_id
              JOIN documents_folder child
                ON starts_with(child.parent_path, root.parent_path)
             WHERE share.state = 'active'
               AND share.share_type = 'folder'
               AND user_rel.user_id IS NOT NULL
               AND root.parent_path IS NOT NULL
               AND (share.date_deadline IS NULL
                    OR share.date_deadline >= CURRENT_DATE)
        """
        cr.execute(
            "INSERT INTO documents_folder_shared_user_rel (folder_id, user_id) "
            "SELECT DISTINCT child.id, user_rel.user_id " + base_from +
            " ON CONFLICT DO NOTHING")
        cr.execute(
            "INSERT INTO documents_folder_shared_editor_rel (folder_id, user_id) "
            "SELECT DISTINCT child.id, user_rel.user_id " + base_from +
            " AND share.role = 'editor' ON CONFLICT DO NOTHING")
        self.env['documents.folder'].invalidate_model(
            ['shared_user_ids', 'shared_editor_ids'])

    def _documents_affected_by_share(self):
        """Return documents whose shared-user index may need rebuilding.

        Only shares on selected documents feed that index.  Folder shares are
        indexed on the folders themselves (``_sync_folder_shared_index``), so
        they never need a per-document rebuild.
        """
        documents = self.env['documents.document']
        for share in self.sudo():
            if share.share_type != 'folder':
                documents |= share.document_ids
        return documents

    def _affects_folder_index(self):
        """Whether any of these shares grants people access to a folder."""
        return any(
            share.share_type == 'folder' and share.recipient_user_ids
            for share in self.sudo())

    @api.model_create_multi
    def create(self, vals_list):
        shares = super().create(vals_list)
        self._sync_shared_user_index(shares._documents_affected_by_share())
        if shares._affects_folder_index():
            self._sync_folder_shared_index()
        return shares

    def write(self, vals):
        tracked_fields = {
            'state', 'share_type', 'folder_id', 'document_ids',
            'recipient_user_ids', 'role', 'date_deadline',
        }
        tracking = bool(tracked_fields.intersection(vals))
        before = self._documents_affected_by_share() if tracking else self.env['documents.document']
        folder_before = self._affects_folder_index() if tracking else False
        result = super().write(vals)
        if tracking:
            after = self._documents_affected_by_share()
            self._sync_shared_user_index(before | after)
            if folder_before or self._affects_folder_index():
                self._sync_folder_shared_index()
        return result

    def unlink(self):
        affected = self._documents_affected_by_share()
        folder_affected = self._affects_folder_index()
        result = super().unlink()
        self._sync_shared_user_index(affected)
        if folder_affected:
            self._sync_folder_shared_index()
        return result

    @api.model
    def get_share_dialog_data(self, document_id):
        """Return the complete state required by the Documents Share dialog.

        The reference flow has two states: the invite screen and, after a
        successful share, the "People with access" screen.  The owner is
        always shown separately from explicitly shared recipients.
        """
        document = self.env['documents.document'].browse(document_id).exists()
        if not document:
            raise UserError(_('The document no longer exists.'))
        document.check_access_rights('read')
        document.check_access_rule('read')

        shares = self.search([
            ('state', '=', 'active'),
            ('document_ids', 'in', document.id),
        ])
        users = shares.mapped('recipient_user_ids')
        users = users.sorted(key=lambda user: (user.name or '').lower())
        owner = document.owner_id or document.create_uid or self.env.user
        return {
            'document': {
                'id': document.id,
                'name': document.name,
            },
            'owner': {
                'id': owner.id,
                'name': owner.name,
                'email': owner.email or owner.login or '',
                'is_current_user': owner.id == self.env.user.id,
                'role': 'owner',
            },
            'users': [{
                'id': user.id,
                'name': user.name,
                'email': user.email or user.login or '',
                'role': (shares.filtered(
                    lambda share: user in share.recipient_user_ids)[:1].role or 'viewer'),
            } for user in users],
            'general_access': {
                'internal': document.access_internal,
                'link': document.access_via_link,
            },
            'can_manage_access': self._can_manage_general_access(document),
            'share_url': document.action_copy_link(),
        }

    @api.model
    def search_share_users(self, search=''):
        """Search internal users for the Share dialog's people picker."""
        domain = [('active', '=', True), ('share', '=', False)]
        if search:
            domain += ['|', ('name', 'ilike', search), ('login', 'ilike', search)]
        users = self.env['res.users'].search(domain, limit=12, order='name')
        return [{
            'id': user.id,
            'name': user.name,
            'email': user.email or user.login or '',
        } for user in users]

    @api.model
    def search_share_groups(self, search=''):
        """Search user groups for the Share dialog's "Add Groups" picker."""
        domain = []
        if search:
            domain.append(('name', 'ilike', search))
        groups = self.env['res.groups'].sudo().search(domain, limit=12, order='name')
        Users = self.env['res.users'].sudo()
        result = []
        for group in groups:
            count = Users.search_count([
                ('share', '=', False), ('active', '=', True),
                ('group_ids', 'in', group.ids),
            ])
            if count:
                result.append({
                    'id': group.id,
                    'name': group.display_name,
                    'user_count': count,
                })
        return result

    @api.model
    def _can_manage_general_access(self, document):
        return bool(
            document.owner_id == self.env.user
            or self.env.user.has_group('custom_documents.group_documents_manager'))

    @api.model
    def set_general_access(self, document_id, internal=None, link=None):
        """Persist the Share dialog's "General Access" dropdowns."""
        document = self.env['documents.document'].browse(document_id).exists()
        if not document:
            raise UserError(_('The document no longer exists.'))
        document.check_access_rights('read')
        document.check_access_rule('read')
        if not self._can_manage_general_access(document):
            raise AccessError(_(
                'Only the owner of a document can change its general access.'))

        allowed = ('none', 'viewer', 'editor')
        vals = {}
        if internal is not None:
            if internal not in allowed:
                raise UserError(_('Invalid access level.'))
            vals['access_internal'] = internal
        if link is not None:
            if link not in allowed:
                raise UserError(_('Invalid access level.'))
            vals['access_via_link'] = link
        if vals:
            document.sudo().write(vals)
            if 'access_via_link' in vals:
                link_share = document._get_or_create_link_share()
                link_share.write({
                    'access_mode': 'download' if vals['access_via_link'] == 'editor' else 'view',
                })
        return self.get_share_dialog_data(document.id)

    @api.model
    def action_share_internal(self, document_id, user_ids=None, role='viewer',
                              notify=True, message=False, internal_access='none',
                              group_ids=None):
        """Grant internal access without overwriting existing recipients.

        Each recipient gets its own active share record.  This mirrors the
        Documents sharing behavior where every person can have an independent
        role.  Existing multi-recipient records created by older versions are
        left intact, while new recipients are added without changing the role
        of people who were already shared.
        """
        document = self.env['documents.document'].browse(document_id).exists()
        if not document:
            raise UserError(_('The document no longer exists.'))
        document.check_access_rights('read')
        document.check_access_rule('read')

        user_ids = [int(uid) for uid in (user_ids or []) if uid]
        users = self.env['res.users'].browse(user_ids).exists()
        group_ids = [int(gid) for gid in (group_ids or []) if gid]
        if group_ids:
            # Groups are expanded to their current internal members: every
            # member gets an individual share, like a manually added person.
            users |= self.env['res.users'].sudo().search([
                ('share', '=', False), ('active', '=', True),
                ('group_ids', 'in', group_ids),
            ])
            users -= self.env.user
        if not users:
            raise UserError(_('Please select at least one person.'))
        if any(user.share for user in users):
            raise UserError(_('Only internal users can be added to this share.'))

        role = role if role in ('viewer', 'editor') else 'viewer'
        internal_access = (
            internal_access if internal_access in ('none', 'viewer', 'editor')
            else 'none'
        )
        access_mode = 'view' if role == 'viewer' else 'upload'

        # Odoo 19 renamed res.users' explicit group field from groups_id
        # to group_ids. Using groups_id raises ValueError: Invalid field
        # 'groups_id' in 'res.users' during the Share operation.
        # A share must be usable even when the recipient was previously an
        # ordinary internal user without the Documents application group.
        # Viewer recipients receive the read-only Documents Basic role;
        # Editor recipients receive Documents User (which implies Basic).
        # This is what makes the Shared with me menu/action and the document
        # ACL available immediately after sharing.
        basic_group = self.env.ref(
            'custom_documents.group_documents_basic', raise_if_not_found=False)
        user_group = self.env.ref(
            'custom_documents.group_documents_user', raise_if_not_found=False)
        if role == 'editor' and user_group:
            users.sudo().write({
                'group_ids': [Command.link(user_group.id)],
            })
        elif basic_group:
            users.sudo().write({
                'group_ids': [Command.link(basic_group.id)],
            })

        created_or_updated = self.env['documents.share']

        for user in users:
            # Reuse an existing share for this exact recipient whenever one
            # exists.  Do not alter other recipients' roles.
            share = self.search([
                ('state', '=', 'active'),
                ('share_type', '=', 'ids'),
                ('document_ids', '=', document.id),
                ('recipient_user_ids', '=', user.id),
            ], limit=1)

            vals = {
                'document_ids': [Command.set([document.id])],
                'recipient_user_ids': [Command.set([user.id])],
                'access_mode': access_mode,
                'role': role,
                'notify': bool(notify),
                'message': message or False,
                'internal_access': internal_access,
                'partner_id': False,
                'email': user.email or user.login or False,
                'owner_id': self.env.user.id,
                'company_id': document.company_id.id or self.env.company.id,
                'state': 'active',
            }
            if share:
                share.write(vals)
            else:
                share = self.create(vals)
            created_or_updated |= share

            if notify and user.partner_id:
                body = message or _('%(user)s shared "%(document)s" with you.',
                                    user=self.env.user.name, document=document.name)
                document.message_post(
                    body=body,
                    partner_ids=user.partner_id.ids,
                    subtype_xmlid='mail.mt_comment',
                )

        # Do one final deterministic rebuild after all recipients have been
        # processed. This is intentionally explicit so the Share dialog can
        # never report success while the Shared with me index is stale.
        self._sync_shared_user_index(document)
        document.invalidate_recordset(['shared_user_ids'])

        return self.get_share_dialog_data(document.id) | {
            'share_id': created_or_updated[:1].id,
            'document_id': document.id,
        }

    # ------------------------------------------------------------------
    # Folder sharing (Share dialog opened on a folder)
    #
    # Same dialog and same ``documents.share`` records as for documents, but
    # with share_type = 'folder'.  Whatever is granted on a folder is
    # inherited by its sub-folders and documents: per-person roles through the
    # folder index, general access through the folder's ``effective_*``
    # fields.
    # ------------------------------------------------------------------
    @api.model
    def _get_folder_for_share(self, folder_id):
        folder = self.env['documents.folder'].browse(folder_id).exists()
        if not folder:
            raise UserError(_('The folder no longer exists.'))
        folder.check_access('read')
        return folder

    @api.model
    def _folder_share_people(self, shares, exclude_user_ids=()):
        """Flatten shares to one entry per user, keeping the highest role."""
        people = {}
        for share in shares.sorted('id'):
            for user in share.recipient_user_ids:
                if user.id in exclude_user_ids:
                    continue
                entry = people.get(user.id)
                if entry and not (share.role == 'editor' and entry['role'] != 'editor'):
                    continue
                people[user.id] = {
                    'id': user.id,
                    'name': user.name,
                    'email': user.email or user.login or '',
                    'role': share.role or 'viewer',
                    'inherited_from': (
                        share.folder_id.name if share.folder_id else False),
                }
        return sorted(people.values(), key=lambda p: (p['name'] or '').lower())

    @api.model
    def _get_or_create_folder_link_share(self, folder):
        """Return the tokenized share behind a folder's "Copy Link".

        As for documents the token is stable and whether it opens anything is
        decided by the folder's effective "Access through link"
        (see ``_get_shared_documents``)."""
        folder = folder.sudo()
        Share = self.sudo()
        share = Share.search([
            ('state', '=', 'active'),
            ('share_type', '=', 'folder'),
            ('folder_id', '=', folder.id),
            ('is_document_link', '=', True),
        ], order='create_date desc, id desc', limit=1)
        if not share:
            share = Share.create({
                'name': _('Share: %s', folder.name),
                'share_type': 'folder',
                'folder_id': folder.id,
                'recipient_user_ids': [Command.clear()],
                'access_mode': 'download' if folder.effective_access_via_link == 'editor' else 'view',
                'role': 'viewer',
                'internal_access': 'none',
                'is_document_link': True,
                'date_deadline': False,
                'owner_id': self.env.user.id,
                'company_id': folder.company_id.id or self.env.company.id,
                'state': 'active',
            })
        return share

    @api.model
    def get_folder_share_dialog_data(self, folder_id):
        """State of the Share dialog for a folder.

        Same shape as ``get_share_dialog_data`` so the dialog can render both,
        plus ``inherited_users`` (people who have access through a share on an
        ancestor folder) and the access inherited from the ancestors."""
        folder = self._get_folder_for_share(folder_id)
        can_manage = folder._can_manage_access()
        owner = folder.sudo().user_id or folder.sudo().create_uid or self.env.user

        # Managers and the owner see every recipient, not just the shares
        # they happened to create themselves.
        Share = self.sudo() if can_manage else self
        direct_shares = Share.search([
            ('state', '=', 'active'),
            ('share_type', '=', 'folder'),
            ('folder_id', '=', folder.id),
        ])
        users = self._folder_share_people(direct_shares, exclude_user_ids=(owner.id,))

        inherited_users = []
        parent = folder.sudo().parent_folder_id
        if can_manage and parent:
            ancestors = folder._get_ancestor_folders()
            inherited_shares = self.sudo().search([
                ('state', '=', 'active'),
                ('share_type', '=', 'folder'),
                ('folder_id', 'in', ancestors.ids),
            ])
            direct_ids = {user['id'] for user in users}
            inherited_users = [
                user for user in self._folder_share_people(
                    inherited_shares, exclude_user_ids=(owner.id,))
                if user['id'] not in direct_ids
            ]

        sudo_folder = folder.sudo()
        link_share = self._get_or_create_folder_link_share(folder)
        return {
            'folder': {
                'id': folder.id,
                'name': folder.name,
            },
            'is_folder': True,
            'owner': {
                'id': owner.id,
                'name': owner.name,
                'email': owner.email or owner.login or '',
                'is_current_user': owner.id == self.env.user.id,
                'role': 'owner',
            },
            'users': users,
            'inherited_users': inherited_users,
            'general_access': {
                'internal': sudo_folder.access_internal,
                'link': sudo_folder.access_via_link,
            },
            'inherited_access': {
                'internal': parent.effective_access_internal if parent else 'none',
                'link': parent.effective_access_via_link if parent else 'none',
                'from': parent.name if parent else False,
            },
            'can_manage_access': can_manage,
            'share_url': link_share.full_url,
        }

    @api.model
    def set_folder_general_access(self, folder_id, internal=None, link=None):
        """Persist the Share dialog's "General Access" dropdowns for a folder."""
        folder = self._get_folder_for_share(folder_id)
        if not folder._can_manage_access():
            raise AccessError(_(
                'Only the owner of a folder or a Documents Administrator can '
                'change its general access.'))

        allowed = ('none', 'viewer', 'editor')
        vals = {}
        if internal is not None:
            if internal not in allowed:
                raise UserError(_('Invalid access level.'))
            vals['access_internal'] = internal
        if link is not None:
            if link not in allowed:
                raise UserError(_('Invalid access level.'))
            vals['access_via_link'] = link
        if vals:
            folder.sudo().write(vals)
            if 'access_via_link' in vals:
                link_share = self._get_or_create_folder_link_share(folder)
                link_share.write({
                    'access_mode': (
                        'download'
                        if folder.sudo().effective_access_via_link == 'editor'
                        else 'view'),
                })
        return self.get_folder_share_dialog_data(folder.id)

    @api.model
    def action_share_folder_internal(self, folder_id, user_ids=None, role='viewer',
                                     notify=True, message=False, group_ids=None):
        """Grant internal users (or all members of groups) access to a folder.

        Like ``action_share_internal`` each recipient gets an independent
        share, so roles never overwrite each other.  The access is inherited by
        every sub-folder and document in the folder.

        Viewers need nothing more than the basic internal-user access every
        employee already has.  Editors are given the Documents Basic role,
        the lowest level whose access rights allow editing documents."""
        folder = self._get_folder_for_share(folder_id)
        if not folder._can_manage_access():
            raise AccessError(_(
                'Only the owner of a folder or a Documents Administrator can '
                'share it.'))

        users = self.env['res.users'].browse(
            [int(uid) for uid in (user_ids or []) if uid]).exists()
        group_ids = [int(gid) for gid in (group_ids or []) if gid]
        if group_ids:
            users |= self.env['res.users'].sudo().search([
                ('share', '=', False), ('active', '=', True),
                ('group_ids', 'in', group_ids),
            ])
        owner = folder.sudo().user_id or folder.sudo().create_uid
        users -= self.env.user
        users -= owner
        if not users:
            raise UserError(_('Please select at least one person.'))
        if any(user.share for user in users):
            raise UserError(_('Only internal users can be added to this share.'))

        role = role if role in ('viewer', 'editor') else 'viewer'
        if role == 'editor':
            basic_group = self.env.ref(
                'custom_documents.group_documents_basic', raise_if_not_found=False)
            if basic_group:
                users.sudo().write({'group_ids': [Command.link(basic_group.id)]})

        shares = self.env['documents.share']
        for user in users:
            share = self.sudo().search([
                ('state', '=', 'active'),
                ('share_type', '=', 'folder'),
                ('folder_id', '=', folder.id),
                ('recipient_user_ids', '=', user.id),
                ('is_document_link', '=', False),
            ], limit=1)
            vals = {
                'share_type': 'folder',
                'folder_id': folder.id,
                'document_ids': [Command.clear()],
                'recipient_user_ids': [Command.set([user.id])],
                'access_mode': 'view' if role == 'viewer' else 'upload',
                'role': role,
                'notify': bool(notify),
                'message': message or False,
                'internal_access': 'none',
                'partner_id': False,
                'email': user.email or user.login or False,
                'owner_id': self.env.user.id,
                'company_id': folder.company_id.id or self.env.company.id,
                # People granted access do not expire like a public link.
                'date_deadline': False,
                'state': 'active',
            }
            if share:
                share.write(vals)
            else:
                share = self.sudo().create(vals)
            shares |= share

            if notify and user.partner_id:
                body = message or _(
                    '%(user)s shared the folder "%(folder)s" with you.',
                    user=self.env.user.name, folder=folder.name)
                self.env['res.partner'].message_notify(
                    partner_ids=user.partner_id.ids,
                    author_id=self.env.user.partner_id.id,
                    subject=_('Folder shared with you: %s', folder.name),
                    body=body,
                    email_layout_xmlid='mail.mail_notification_light',
                )

        self._sync_folder_shared_index()
        return self.get_folder_share_dialog_data(folder.id) | {
            'share_id': shares[:1].id,
            'folder_id': folder.id,
        }

    @api.model
    def action_remove_folder_access(self, folder_id, user_id):
        """Revoke one person's direct access to a folder.

        Access that comes from a share on an ancestor folder (or from general
        access) is not affected: it has to be removed where it was granted."""
        folder = self._get_folder_for_share(folder_id)
        if not folder._can_manage_access():
            raise AccessError(_(
                'Only the owner of a folder or a Documents Administrator can '
                'change who has access to it.'))
        shares = self.sudo().search([
            ('state', '=', 'active'),
            ('share_type', '=', 'folder'),
            ('folder_id', '=', folder.id),
            ('recipient_user_ids', '=', int(user_id)),
            ('is_document_link', '=', False),
        ])
        for share in shares:
            if share.recipient_user_ids - self.env['res.users'].browse(int(user_id)):
                share.write({'recipient_user_ids': [Command.unlink(int(user_id))]})
            else:
                share.write({'state': 'revoked'})
        return self.get_folder_share_dialog_data(folder.id)
