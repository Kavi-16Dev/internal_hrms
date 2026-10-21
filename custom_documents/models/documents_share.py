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
        return True

    def _documents_affected_by_share(self):
        """Return documents whose shared-user index may need rebuilding."""
        documents = self.env['documents.document']
        for share in self.sudo():
            if share.share_type == 'folder' and share.folder_id:
                documents |= self.env['documents.document'].sudo().search([
                    ('folder_id', 'child_of', share.folder_id.id),
                ])
            else:
                documents |= share.document_ids
        return documents

    @api.model_create_multi
    def create(self, vals_list):
        shares = super().create(vals_list)
        self._sync_shared_user_index(shares._documents_affected_by_share())
        return shares

    def write(self, vals):
        tracked_fields = {
            'state', 'share_type', 'folder_id', 'document_ids',
            'recipient_user_ids',
        }
        before = self._documents_affected_by_share() if tracked_fields.intersection(vals) else self.env['documents.document']
        result = super().write(vals)
        if tracked_fields.intersection(vals):
            after = self._documents_affected_by_share()
            self._sync_shared_user_index(before | after)
        return result

    def unlink(self):
        affected = self._documents_affected_by_share()
        result = super().unlink()
        self._sync_shared_user_index(affected)
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
