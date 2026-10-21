# -*- coding: utf-8 -*-
import io
import re
from datetime import timedelta

from odoo import api, fields, models, _
from odoo.exceptions import UserError


class DocumentsDocument(models.Model):
    _name = 'documents.document'
    _description = 'Document'
    _inherit = ['mail.thread', 'mail.activity.mixin']
    _order = 'create_date desc, id desc'
    _rec_name = 'name'

    name = fields.Char(required=True, tracking=True)
    active = fields.Boolean(default=True)
    deletion_date = fields.Date(
        string='Deletion Date', copy=False,
        help='Date on which this document will be permanently deleted from '
             'the Trash. Left empty for documents that are not in the Trash.')

    # -- File storage -------------------------------------------------
    # The actual bytes always live on an ir.attachment record so we get
    # de-duplication, access tokens and standard Odoo file handling for
    # free; documents.document is the "business" wrapper around it.
    attachment_id = fields.Many2one(
        'ir.attachment', string='Attachment', ondelete='cascade', copy=False)
    datas = fields.Binary(
        string='File Content', related='attachment_id.datas', readonly=False)
    mimetype = fields.Char(related='attachment_id.mimetype', readonly=True)
    file_size = fields.Integer(related='attachment_id.file_size', readonly=True)
    checksum = fields.Char(related='attachment_id.checksum', readonly=True)
    url = fields.Char(string='External Link', tracking=True)
    type = fields.Selection([
        ('binary', 'File'),
        ('url', 'Link'),
    ], default='binary', required=True)

    # -- Classification -------------------------------------------------
    folder_id = fields.Many2one(
        'documents.folder', string='Workspace', required=True, tracking=True,
        index=True)
    employee_id = fields.Many2one(
        'hr.employee', string='Employee', related='folder_id.employee_id',
        store=True, index=True, readonly=True,
        help='Employee whose centralized Documents folder contains this document.')
    tag_ids = fields.Many2many('documents.tag', string='Tags')
    owner_id = fields.Many2one(
        'res.users', string='Owner', default=lambda s: s.env.user,
        tracking=True)
    partner_id = fields.Many2one('res.partner', string='Related Contact')
    company_id = fields.Many2one(
        'res.company', default=lambda s: s.env.company)

    # -- Generic link to any business record -----------------------------
    res_model = fields.Char(string='Related Document Model', index=True)
    res_id = fields.Many2oneReference(
        string='Related Document ID', model_field='res_model', index=True)
    res_name = fields.Char(compute='_compute_res_name', string='Related Record')

    # -- Request workflow -------------------------------------------------
    state = fields.Selection([
        ('uploaded', 'Uploaded'),
        ('requested', 'Requested'),
    ], default='uploaded', required=True, tracking=True,
        help='"Requested" documents are placeholders waiting for someone '
             'to upload the file that was asked of them.')
    request_partner_id = fields.Many2one(
        'res.partner', string='Requested From',
        help='Person the document was requested from, if external.')
    request_user_id = fields.Many2one(
        'res.users', string='Requested From (User)',
        help='Person the document was requested from, if an internal user.')
    requested_by_id = fields.Many2one(
        'res.users', string='Requested By', default=lambda s: s.env.user)
    request_deadline = fields.Date(string='Requested Deadline')
    request_note = fields.Html(
        string='Request Message', sanitize=True, strip_style=False)

    request_share_id = fields.Many2one(
        'documents.share', string='Request Upload Share', copy=False,
        readonly=True, index=True,
        help='Private tokenized share used by the recipient to upload the requested file.')
    request_share_url = fields.Char(
        string='Request Upload URL', compute='_compute_request_share_url',
        help='Secure upload URL included in the document-request email.')

    # -- Sharing -------------------------------------------------
    share_ids = fields.Many2many(
        'documents.share', 'documents_share_document_rel',
        'document_id', 'share_id', string='Shares')
    # Denormalized recipient index used by the Shared with me screen and
    # the document record rule.  Keeping the recipient users directly on the
    # document avoids relying on a cross-model record-rule/domain traversal
    # through documents.share, which can make a document disappear from the
    # recipient's search even though the share itself exists.  It is
    # synchronized by documents.share.create/write/unlink and backfilled by
    # the migration shipped with this version.
    shared_user_ids = fields.Many2many(
        'res.users', 'documents_document_shared_user_rel',
        'document_id', 'user_id', string='Shared With', copy=False,
        help='Internal users who have explicit access to this document.')

    # General access (Share dialog > "General Access").  Both default to
    # "none": a document is only reachable by its owner, explicit recipients
    # and whoever the workspace rules already allow.
    access_internal = fields.Selection([
        ('none', 'None'),
        ('viewer', 'Viewer'),
        ('editor', 'Editor'),
    ], string='Internal Users Access', default='none', required=True,
        copy=False, tracking=True,
        help='Access granted to every internal user, without an explicit share.')
    access_via_link = fields.Selection([
        ('none', 'None'),
        ('viewer', 'Viewer'),
        ('editor', 'Editor'),
    ], string='Access Through Link', default='none', required=True,
        copy=False, tracking=True,
        help='Whether anyone holding the document link may open it. '
             '"Editor" additionally allows downloading the file.')

    # -- Lock -------------------------------------------------
    # Mirrors Enterprise's "Lock" action: while locked, only the person who
    # locked it (or a Documents Manager) may unlock it. We don't use this
    # to hard-block writes everywhere (that would need touching every write
    # path), just to gate the toggle itself and to drive the Actions menu
    # label ("Lock" / "Unlock") and a small lock badge on the card.
    lock_uid = fields.Many2one(
        'res.users', string='Locked By', copy=False, tracking=True)

    # -- Shortcuts -------------------------------------------------
    # A "shortcut" is a lightweight documents.document that points at the
    # same attachment as another document but lives in a different
    # workspace, exactly like Enterprise's "Create Shortcut" action -
    # opening it previews the same file, but deleting it never touches the
    # original.
    shortcut_document_id = fields.Many2one(
        'documents.document', string='Shortcut Of', ondelete='cascade',
        copy=False, index=True,
        help='If set, this document is a shortcut pointing at another '
             'document rather than owning its own file.')
    is_shortcut = fields.Boolean(
        string='Is a Shortcut', compute='_compute_is_shortcut', store=True)

    # -- Versions -------------------------------------------------
    version_ids = fields.One2many(
        'documents.document.version', 'document_id', string='Versions')
    version_count = fields.Integer(
        compute='_compute_version_count', string='Version Count')

    # -- Recruitment bridge -------------------------------------------------
    # Whether the "Create an Applicant" action should be offered for this
    # document: mirrors Odoo's own Documents/Recruitment bridge, gated by a
    # *soft* dependency on hr_recruitment (checked at runtime, no hard
    # 'depends' entry - see res_config_settings.py) so this module keeps
    # installing fine on a bare Community setup without Recruitment.
    show_create_applicant = fields.Boolean(
        string='Can Create Applicant', compute='_compute_show_create_applicant')

    _sql_constraints = [
        ('url_or_attachment_or_request',
         "CHECK(1=1)", 'placeholder'),
    ]

    # ------------------------------------------------------------------
    # Compute
    # ------------------------------------------------------------------
    @api.depends('request_share_id', 'request_share_id.full_url')
    def _compute_request_share_url(self):
        for document in self:
            document.request_share_url = document.request_share_id.full_url or False

    @api.depends('res_model', 'res_id')
    def _compute_res_name(self):
        for doc in self:
            name = False
            if doc.res_model and doc.res_id:
                record = self.env[doc.res_model].browse(doc.res_id).exists()
                if record:
                    name = record.display_name
            doc.res_name = name

    @api.depends('shortcut_document_id')
    def _compute_is_shortcut(self):
        for document in self:
            document.is_shortcut = bool(document.shortcut_document_id)

    @api.depends('version_ids')
    def _compute_version_count(self):
        for document in self:
            document.version_count = len(document.version_ids)

    # ------------------------------------------------------------------
    # Recruitment bridge
    # ------------------------------------------------------------------
    @api.depends('attachment_id', 'type', 'active', 'folder_id',
                 'company_id.documents_recruitment_settings',
                 'company_id.documents_recruitment_folder_id')
    def _compute_show_create_applicant(self):
        recruitment_installed = bool(self.env['ir.module.module'].sudo().search_count([
            ('name', '=', 'hr_recruitment'),
            ('state', '=', 'installed'),
        ]))
        # Cache, per company, the set of folder ids allowed to expose the
        # action (the configured Recruitment folder and all its
        # sub-folders), computed at most once per company for this batch.
        allowed_folder_ids_by_company = {}
        for document in self:
            show = False
            if recruitment_installed and document.type == 'binary' \
                    and document.attachment_id and document.active:
                company = document.company_id or self.env.company
                folder = company.documents_recruitment_folder_id
                if not company.documents_recruitment_settings or not folder:
                    # No workspace configured (or centralization disabled):
                    # allow the action on any file, so it works out of the
                    # box without requiring extra setup.
                    show = True
                else:
                    if company.id not in allowed_folder_ids_by_company:
                        allowed_folder_ids_by_company[company.id] = set(
                            self.env['documents.folder'].search(
                                [('id', 'child_of', folder.id)]).ids)
                    show = document.folder_id.id in allowed_folder_ids_by_company[company.id]
            document.show_create_applicant = show

    def action_create_applicant(self):
        """Create a new Recruitment applicant from this document, attaching
        a copy of its file so it shows up (with preview) on the applicant's
        chatter - mirrors the 'Create an Applicant' action of Odoo's own
        Documents/Recruitment bridge."""
        self.ensure_one()
        if not self.env['ir.module.module'].sudo().search_count([
            ('name', '=', 'hr_recruitment'), ('state', '=', 'installed'),
        ]):
            raise UserError(_('The Recruitment app must be installed to use this feature.'))
        if not self.attachment_id:
            raise UserError(_('This document has no file to convert into an applicant.'))

        applicant = self.env['hr.applicant'].create({
            'partner_name': _('New Applicant from Documents'),
            'company_id': (self.company_id or self.env.company).id,
        })
        self.attachment_id.copy({
            'res_model': 'hr.applicant',
            'res_id': applicant.id,
            'res_field': False,
            'name': self.attachment_id.name,
        })
        return {
            'type': 'ir.actions.act_window',
            'name': _('New Applicant from Documents'),
            'res_model': 'hr.applicant',
            'res_id': applicant.id,
            'views': [(False, 'form')],
            'target': 'current',
        }

    # ------------------------------------------------------------------
    # Defaults
    # ------------------------------------------------------------------
    @api.model
    def default_get(self, fields_list):
        """Resolve dynamic default_folder_id requests in Python instead of
        baking a hardcoded folder id into an action's context via XML
        ref() + eval. This avoids any dependency on module-upgrade timing
        (a stale/un-upgraded action would otherwise still store the raw,
        un-resolved 'ref(...)' text and crash the browser's expression
        evaluator) and is multi-company safe.

        Actions trigger this by setting a plain, static context flag such
        as {'default_folder_is_company_drive': 1} - no ref(), no eval
        attribute required."""
        res = super().default_get(fields_list)
        if 'folder_id' in fields_list and not res.get('folder_id'):
            if self.env.context.get('default_folder_is_company_drive'):
                res['folder_id'] = self.env['documents.folder']._get_or_create_company_drive(
                    self.env.company).id
        return res

    # ------------------------------------------------------------------
    # CRUD
    # ------------------------------------------------------------------
    def _recompute_employee_document_counts(self, employee_ids):
        employee_ids = list({employee_id for employee_id in employee_ids if employee_id})
        if employee_ids:
            self.env['hr.employee'].sudo().browse(employee_ids)._compute_document_count()

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            if not vals.get('folder_id'):
                vals['folder_id'] = self.env['documents.folder']._get_or_create_employee_drive(
                    self.env.user).id
            if vals.get('request_partner_id') or vals.get('request_user_id'):
                vals.setdefault('state', 'requested')

        documents = super().create(vals_list)
        for document, vals in zip(documents, vals_list):
            if vals.get('datas') and not vals.get('attachment_id'):
                document._create_attachment_from_datas(vals['datas'], document.name)
            if document.state == 'requested':
                document._send_request_notification()

        self._recompute_employee_document_counts(documents.mapped('employee_id').ids)
        return documents

    def write(self, vals):
        if 'shared_user_ids' in vals and not self.env.context.get('_documents_share_sync'):
            vals = dict(vals)
            vals.pop('shared_user_ids', None)

        old_employee_ids = self.mapped('employee_id').ids

        if vals.get('datas'):
            for document in self:
                if document.attachment_id and document.attachment_id.datas:
                    document._snapshot_version()

        res = super().write(vals)
        if vals.get('datas'):
            for document in self:
                if document.state == 'requested':
                    document.state = 'uploaded'
                    document.message_post(
                        body=_('Document fulfilled: the requested file was uploaded.'))

        self._recompute_employee_document_counts(
            old_employee_ids + self.mapped('employee_id').ids)
        return res

    def unlink(self):
        employee_ids = self.mapped('employee_id').ids
        result = super().unlink()
        self._recompute_employee_document_counts(employee_ids)
        return result

    def _snapshot_version(self):
        """Copy the current attachment content into a new
        documents.document.version record, preserving the file as it was
        right before being overwritten."""
        self.ensure_one()
        if not self.attachment_id:
            return
        self.env['documents.document.version'].sudo().create({
            'document_id': self.id,
            'attachment_id': self.attachment_id.copy({
                'res_model': False,
                'res_id': False,
                'res_field': False,
            }).id,
        })

    def _create_attachment_from_datas(self, datas, name):
        self.ensure_one()
        attachment = self.env['ir.attachment'].create({
            'name': name,
            'datas': datas,
            'res_model': self._name,
            'res_id': self.id,
        })
        self.attachment_id = attachment.id

    # ------------------------------------------------------------------
    # Actions
    # ------------------------------------------------------------------
    def action_upload_fulfill(self):
        """Used by the form-view upload button on a requested document."""
        self.ensure_one()
        if not self.datas:
            raise UserError(_('Please attach a file before submitting.'))
        self.state = 'uploaded'

    def action_upload_requested_file(self, datas, filename=False, mimetype=False):
        """Fulfil a requested document directly from the Documents card.

        The Documents kanban uses this RPC after the user chooses a file in
        the native browser file picker.  This deliberately does not open the
        document form: the requested card itself is the upload entry point,
        matching the native Documents request flow.
        """
        self.ensure_one()
        if self.state != 'requested':
            raise UserError(_('This document is no longer waiting for an upload.'))
        if not datas:
            raise UserError(_('Please select a file.'))

        attachment_vals = {
            'name': filename or self.name,
            'datas': datas,
            'res_model': self._name,
            'res_id': self.id,
        }
        if mimetype:
            attachment_vals['mimetype'] = mimetype

        attachment = self.env['ir.attachment'].create(attachment_vals)
        self.write({
            'attachment_id': attachment.id,
            'type': 'binary',
            'state': 'uploaded',
        })
        self.message_post(
            body=_('Document fulfilled: %(filename)s was uploaded.',
                   filename=filename or self.name)
        )
        return {
            'id': self.id,
            'name': self.name,
            'attachment_id': attachment.id,
            'state': self.state,
        }

    def action_share(self):
        self.ensure_one()
        return {
            'type': 'ir.actions.act_window',
            'name': _('Share'),
            'res_model': 'documents.share',
            'view_mode': 'form',
            'target': 'new',
            'context': {
                'default_document_ids': [(6, 0, self.ids)],
                'default_folder_id': self.folder_id.id,
            },
        }

    def action_open_versions(self):
        """Smart button on the form view: list every automatic version
        snapshot for this document (same data as the 'Manage Versions'
        Actions-menu entry in the preview, via the classic view)."""
        self.ensure_one()
        return {
            'type': 'ir.actions.act_window',
            'name': _('Versions'),
            'res_model': 'documents.document.version',
            'view_mode': 'list,form',
            'domain': [('document_id', '=', self.id)],
            'context': {'create': False},
        }

    def action_duplicate(self):
        """'Duplicate' Actions-menu entry: copy the document (and its own
        attachment, so editing the copy never touches the original) into
        the same workspace."""
        self.ensure_one()
        new_attachment_id = False
        if self.attachment_id:
            new_attachment_id = self.attachment_id.copy({
                'res_model': False, 'res_id': False, 'res_field': False,
            }).id
        copy = self.copy({
            'name': _('%s (copy)', self.name),
            'attachment_id': new_attachment_id,
            'lock_uid': False,
            'shortcut_document_id': False,
        })
        return copy

    def action_rename(self, new_name):
        """'Rename' Actions-menu entry."""
        self.ensure_one()
        new_name = (new_name or '').strip()
        if not new_name:
            raise UserError(_('Please enter a name.'))
        self.name = new_name

    def action_move(self, folder_id):
        """'Move' Actions-menu entry: file the document into another
        workspace."""
        self.ensure_one()
        folder = self.env['documents.folder'].browse(folder_id).exists()
        if not folder:
            raise UserError(_('Please select a destination workspace.'))
        self.folder_id = folder.id

    def action_create_shortcut(self, folder_id):
        """'Create Shortcut' Actions-menu entry: a new document that shares
        this one's attachment/file but lives in another workspace. Deleting
        the shortcut never deletes the original file."""
        self.ensure_one()
        folder = self.env['documents.folder'].browse(folder_id).exists()
        if not folder:
            raise UserError(_('Please select a destination workspace.'))
        shortcut = self.create({
            'name': self.name,
            'folder_id': folder.id,
            'attachment_id': self.attachment_id.id,
            'type': self.type,
            'url': self.url,
            'tag_ids': [(6, 0, self.tag_ids.ids)],
            'shortcut_document_id': self.id,
        })
        return shortcut

    def action_toggle_lock(self):
        """'Lock' / 'Unlock' Actions-menu entry."""
        self.ensure_one()
        is_manager = self.env.user.has_group('custom_documents.group_documents_manager')
        if self.lock_uid:
            if self.lock_uid != self.env.user and not is_manager:
                raise UserError(_(
                    'This document is locked by %s.', self.lock_uid.name))
            self.lock_uid = False
        else:
            self.lock_uid = self.env.user.id

    def action_copy_link(self):
        """Return a real, tokenized share URL for this document.

        The old implementation returned ``/odoo/documents/<id>``.  That URL
        is a backend web-client route, so opening it outside the current
        Documents action can land on the last/default application (often
        Discuss) instead of the document.  A Documents share URL is
        self-contained and can therefore be opened in a new tab, another
        browser profile, or an incognito window.
        """
        self.ensure_one()
        share = self._get_or_create_link_share()
        base_url = self.env['ir.config_parameter'].sudo().get_param('web.base.url')
        return f'{base_url.rstrip("/")}/document/share/{share.access_token}'

    def _get_or_create_link_share(self):
        """Return the tokenized share behind "Copy Link".

        The token is stable per document, but whether it actually opens the
        file is decided by ``access_via_link`` (see the portal controller),
        so switching "Access through link" back to None really closes it.
        """
        self.ensure_one()
        Share = self.env['documents.share'].sudo()
        share = Share.search([
            ('state', '=', 'active'),
            ('share_type', '=', 'ids'),
            ('document_ids', '=', self.id),
            ('is_document_link', '=', True),
        ], order='create_date desc, id desc', limit=1)
        if not share:
            share = Share.create({
                'name': _('Share: %s', self.name),
                'share_type': 'ids',
                'document_ids': [(6, 0, [self.id])],
                'recipient_user_ids': [(5, 0, 0)],
                'access_mode': 'download' if self.access_via_link == 'editor' else 'view',
                'role': 'viewer',
                'internal_access': 'none',
                'is_document_link': True,
                'date_deadline': False,
                'owner_id': self.env.user.id,
                'company_id': self.company_id.id or self.env.company.id,
                'state': 'active',
            })
        return share

    def action_split_pdf(self, page_ranges):
        """'Split PDF' Actions-menu entry: cut this PDF into several new
        documents (filed in the same workspace) according to
        `page_ranges`, a string such as "1-2,3,4-5" (1-indexed, inclusive).
        The original document/file is left untouched."""
        self.ensure_one()
        if not self.attachment_id or 'pdf' not in (self.mimetype or ''):
            raise UserError(_('Split PDF is only available for PDF files.'))
        try:
            from pypdf import PdfReader, PdfWriter
        except ImportError:
            raise UserError(_(
                'The "pypdf" Python library is required to split PDF files. '
                'Please ask your administrator to install it (pip install pypdf).'))

        ranges = self._parse_split_ranges(page_ranges)
        if not ranges:
            raise UserError(_('Please enter at least one valid page range, e.g. "1-2,3,4-5".'))

        content = self.attachment_id.raw
        reader = PdfReader(io.BytesIO(content))
        page_count = len(reader.pages)
        new_documents = self.env['documents.document']
        for index, (start, end) in enumerate(ranges, start=1):
            if start < 1 or end > page_count or start > end:
                raise UserError(_(
                    'Page range %(start)s-%(end)s is out of bounds (this PDF has '
                    '%(count)s pages).', start=start, end=end, count=page_count))
            writer = PdfWriter()
            for page_number in range(start - 1, end):
                writer.add_page(reader.pages[page_number])
            buffer = io.BytesIO()
            writer.write(buffer)
            base_name = re.sub(r'\.pdf$', '', self.name, flags=re.IGNORECASE)
            new_name = _('%(name)s (%(index)s)', name=base_name, index=index) + '.pdf'
            attachment = self.env['ir.attachment'].create({
                'name': new_name,
                'raw': buffer.getvalue(),
                'mimetype': 'application/pdf',
            })
            new_documents |= self.create({
                'name': new_name,
                'folder_id': self.folder_id.id,
                'attachment_id': attachment.id,
                'tag_ids': [(6, 0, self.tag_ids.ids)],
            })
        return new_documents

    @api.model
    def _parse_split_ranges(self, page_ranges):
        """Turn "1-2,3,4-5" into [(1, 2), (3, 3), (4, 5)]. Silently skips
        malformed chunks rather than raising, so a trailing comma/space
        doesn't block the whole action."""
        ranges = []
        for chunk in (page_ranges or '').split(','):
            chunk = chunk.strip()
            if not chunk:
                continue
            match = re.match(r'^(\d+)\s*-\s*(\d+)$', chunk)
            if match:
                ranges.append((int(match.group(1)), int(match.group(2))))
                continue
            match = re.match(r'^(\d+)$', chunk)
            if match:
                page = int(match.group(1))
                ranges.append((page, page))
        return ranges

    def action_download(self):
        self.ensure_one()
        if not self.attachment_id:
            raise UserError(_('This document has no file to download.'))
        return {
            'type': 'ir.actions.act_url',
            'url': f'/web/content/{self.attachment_id.id}?download=true',
            'target': 'self',
        }

    def _get_or_create_request_share(self):
        """Return the private upload share used by a document request.

        A request is represented by a real placeholder document.  The email
        therefore needs a tokenized Documents share that points to that exact
        placeholder; using a backend ``/odoo/...`` URL would open the web
        client and can fall back to Discuss or another application.
        """
        self.ensure_one()
        Share = self.env['documents.share'].sudo()
        share = self.request_share_id.sudo()
        if share and share.state == 'active' and share._check_valid():
            return share

        share = Share.search([
            ('state', '=', 'active'),
            ('share_type', '=', 'ids'),
            ('access_mode', '=', 'upload'),
            ('document_ids', 'in', self.id),
        ], order='create_date desc, id desc', limit=1)

        recipient_partner = (
            self.partner_id
            or self.request_partner_id
            or (self.request_user_id.partner_id if self.request_user_id else False)
        )
        vals = {
            'name': _('Document Request: %s', self.name),
            'share_type': 'ids',
            'document_ids': [(6, 0, [self.id])],
            'access_mode': 'upload',
            'role': 'viewer',
            'notify': False,
            'message': self.request_note or False,
            'internal_access': 'none',
            'partner_id': recipient_partner.id if recipient_partner else False,
            'email': (recipient_partner.email if recipient_partner else False) or
                      (self.request_user_id.email if self.request_user_id else False),
            'owner_id': self.requested_by_id.id or self.env.user.id,
            'company_id': self.company_id.id or self.env.company.id,
            'state': 'active',
        }
        if share:
            share.write(vals)
        else:
            share = Share.create(vals)
        self.sudo().write({'request_share_id': share.id})
        return share

    def _send_request_notification(self):
        self.ensure_one()
        # Always prepare the secure upload link before rendering the email.
        self._get_or_create_request_share()
        template = self.env.ref(
            'custom_documents.mail_template_document_request', raise_if_not_found=False)
        if template:
            template.send_mail(self.id, force_send=True)

    # ------------------------------------------------------------------
    # Trash Management
    # ------------------------------------------------------------------
    def action_archive(self):
        """Move document(s) to the Trash: hide them (active=False) and
        schedule their permanent deletion according to each company's
        'Deletion delay' setting (Settings > Documents > Trash Management)."""
        for document in self:
            delay = document.company_id.documents_deletion_delay or 30
            document.deletion_date = fields.Date.context_today(document) + timedelta(days=delay)
        return super().action_archive()

    def action_unarchive(self):
        """Restore document(s) from the Trash."""
        self.write({'deletion_date': False})
        return super().action_unarchive()

    def action_restore(self):
        """Button-friendly alias for action_unarchive, used on the Trash view."""
        return self.action_unarchive()

    def action_delete_permanently(self):
        """Permanently remove the document(s) and their attachment right
        away, without waiting for the Deletion Delay / cron to run."""
        for document in self:
            if document.attachment_id:
                document.attachment_id.unlink()
        return self.unlink()

    @api.model
    def _cron_purge_trash(self):
        """Scheduled action: permanently delete every document whose
        deletion_date (Trash > Deletion Delay) has passed."""
        today = fields.Date.context_today(self)
        expired = self.with_context(active_test=False).search([
            ('active', '=', False),
            ('deletion_date', '!=', False),
            ('deletion_date', '<=', today),
        ])
        expired.action_delete_permanently()

    # ------------------------------------------------------------------
    # "Shared with me" (Documents > Shared with me)
    # A document is "shared with me" when it sits in a workspace the
    # current user was explicitly added to as a member (documents.folder
    # member_ids) without being its owner - i.e. a colleague gave them
    # access to that workspace, mirroring Enterprise's "Shared with me".
    # ------------------------------------------------------------------
    @api.model
    def _get_shared_with_me_domain(self):
        """Return the domain for the dedicated *Shared with me* section.

        This section is driven by active explicit document shares and by
        documents stored in an employee workspace that explicitly includes
        the current user as a workspace member. Request placeholders are
        handled by *Requests*, while ordinary company/owned documents remain
        in their respective workspace/Inbox views.
        """
        uid = self.env.uid
        return [
            ('active', '=', True),
            ('state', '=', 'uploaded'),
            '|', '|',
                ('shared_user_ids', 'in', uid),
                ('folder_id.member_ids', 'in', uid),
                '&',
                    ('access_internal', 'in', ['viewer', 'editor']),
                    ('owner_id', '!=', uid),
        ]

    @api.model
    def _get_requests_domain(self):
        """Return the domain for the dedicated *Requests* section.

        A request remains in this section only while its placeholder is in
        ``state = requested``.  Both incoming requests (the selected user or
        partner is the current user) and requests created by the current user
        are shown, so the section is useful to both sides of the workflow.
        """
        uid = self.env.uid
        partner_id = self.env.user.partner_id.id
        return [
            ('active', '=', True),
            ('state', '=', 'requested'),
            '|', '|',
                ('request_user_id', '=', uid),
                ('request_partner_id', '=', partner_id),
                ('requested_by_id', '=', uid),
        ]

    @api.model
    def _get_inbox_domain(self):
        """Return the domain for the company *Inbox* section.

        Requested placeholders have their own Requests section.  A document
        explicitly shared with another user is also presented in Shared with
        me for that recipient, so it is excluded from the recipient's Inbox
        view to keep the three action/status sections deterministic.
        """
        uid = self.env.uid
        return [
            ('active', '=', True),
            ('folder_id.is_inbox', '=', True),
            ('folder_id.company_id', '=', self.env.user.company_id.id),
            '|',
                # Normal Inbox files owned by the current user or not
                # explicitly shared with them.
                '&',
                    ('state', '=', 'uploaded'),
                    '|',
                        ('owner_id', '=', uid),
                        ('shared_user_ids', 'not in', [uid]),
                # Incoming document requests are also shown in Inbox,
                # matching the reference Documents flow: the recipient
                # sees the requested card with the green upload affordance.
                '&',
                    ('state', '=', 'requested'),
                    '|',
                        ('request_user_id', '=', uid),
                        ('request_partner_id', '=', self.env.user.partner_id.id),
        ]
