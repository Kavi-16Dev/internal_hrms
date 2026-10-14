# -*- coding: utf-8 -*-
from datetime import timedelta

from dateutil.relativedelta import relativedelta

from odoo import api, fields, models, _, Command
from odoo.exceptions import UserError


class DocumentsRequestWizard(models.TransientModel):
    _name = 'documents.request.wizard'
    _description = 'Request a Document'

    name = fields.Char(string='Document Name', required=True)

    # Native Documents behavior: Request To is a partner/contact, not a
    # res.users record. This makes the selector search the complete contact
    # list (including companies and external contacts) and gives the standard
    # partner search dialog shown in the reference video.
    request_to_id = fields.Many2one(
        'res.partner', string='Request To',
        help='Person or company who must provide the requested document.')

    # Legacy fields are intentionally retained so existing callers and
    # previously created request records continue to work.
    request_user_id = fields.Many2one(
        'res.users', string='Request To (User)',
        help='Internal user selected from the Request To contact.')
    request_partner_id = fields.Many2one(
        'res.partner', string='Request To (Contact)',
        help='External contact selected from the Request To contact.')
    request_type = fields.Selection([
        ('user', 'Internal User'),
        ('partner', 'Contact / Portal User'),
    ], default='user', required=True)

    # This is the contact attached to the requested document. It is separate
    # from the recipient, matching the standard Documents request dialog.
    partner_id = fields.Many2one(
        'res.partner', string='Contact',
        compute='_compute_partner_id', inverse='_inverse_partner_id',
        readonly=True,
        help='Contact related to this document request.')

    folder_id = fields.Many2one(
        'documents.folder', string='Folder', required=True)
    tag_ids = fields.Many2many('documents.tag', string='Tags')

    request_deadline_in = fields.Integer(
        string='Due Date In', default=30, required=True)
    request_deadline_unit = fields.Selection([
        ('days', 'Days'),
        ('weeks', 'Weeks'),
        ('months', 'Months'),
    ], string='Deadline Unit', default='days', required=True)
    request_deadline = fields.Date(
        string='Requested Deadline', readonly=True)

    activity_type = fields.Selection([
        ('document', 'Document'),
    ], string='Activity type', default='document', required=True)

    resource_model = fields.Char(
        string='Resource Model', readonly=True)
    resource_id = fields.Integer(
        string='Resource ID', readonly=True, default=0)
    request_note = fields.Html(
        string='Message',
        sanitize=True,
        strip_style=False,
        help='Optional message sent with the document request.')

    @api.depends('request_to_id', 'request_user_id', 'request_partner_id')
    def _compute_partner_id(self):
        """Always show the selected Request To contact.

        The reference Documents flow keeps Request To and Contact
        synchronized.  Computing the field (in addition to the onchange
        handlers below) makes the synchronization reliable for both the
        interactive form and programmatic callers.
        """
        for wizard in self:
            wizard.partner_id = (
                wizard.request_to_id
                or wizard.request_partner_id
                or (wizard.request_user_id.partner_id if wizard.request_user_id else False)
            )

    def _inverse_partner_id(self):
        """Keep legacy callers that assign Contact working."""
        for wizard in self:
            if wizard.partner_id:
                wizard.request_to_id = wizard.partner_id

    @api.model
    def default_get(self, fields_list):
        vals = super().default_get(fields_list)
        ctx = self.env.context

        # When the user explicitly opened Request from a folder, keep that
        # folder. Otherwise reproduce the Documents application's default
        # Request dialog: the request is created in the company's Inbox.
        if 'folder_id' in fields_list and not vals.get('folder_id'):
            folder_id = ctx.get('default_folder_id')
            if folder_id:
                vals['folder_id'] = folder_id
            elif ctx.get('default_folder_is_company_drive'):
                vals['folder_id'] = self.env['documents.folder']._get_or_create_company_drive(
                    self.env.company).id
            else:
                vals['folder_id'] = self.env['documents.folder']._get_or_create_company_inbox(
                    self.env.company).id

        if 'resource_model' in fields_list:
            vals['resource_model'] = ctx.get('default_resource_model') or ctx.get('active_model') or False
        if 'resource_id' in fields_list:
            vals['resource_id'] = ctx.get('default_resource_id') or ctx.get('active_id') or 0
        if 'partner_id' in fields_list and not vals.get('partner_id'):
            vals['partner_id'] = ctx.get('default_partner_id') or False
        if 'request_to_id' in fields_list and ctx.get('default_request_to_id'):
            partner = self.env['res.partner'].browse(ctx['default_request_to_id']).exists()
            if partner:
                vals['request_to_id'] = partner.id
                if 'partner_id' in fields_list and not vals.get('partner_id'):
                    vals['partner_id'] = partner.id

        # Backward-compatible context values from the previous custom flow.
        if ctx.get('default_request_user_id'):
            user = self.env['res.users'].browse(ctx['default_request_user_id']).exists()
            if user:
                vals['request_user_id'] = user.id
                vals['request_to_id'] = user.partner_id.id
                if 'partner_id' in fields_list and not vals.get('partner_id'):
                    vals['partner_id'] = user.partner_id.id
        if ctx.get('default_request_partner_id'):
            partner = self.env['res.partner'].browse(ctx['default_request_partner_id']).exists()
            if partner:
                vals['request_partner_id'] = partner.id
                vals['request_to_id'] = partner.id
                if 'partner_id' in fields_list and not vals.get('partner_id'):
                    vals['partner_id'] = partner.id
        return vals

    @api.onchange('request_type')
    def _onchange_request_type(self):
        # Keep legacy request_type callers functional. The visible UI uses
        # request_to_id for both internal users and external contacts.
        for wizard in self:
            if wizard.request_type == 'user':
                wizard.request_partner_id = False
                if wizard.request_user_id:
                    wizard.request_to_id = wizard.request_user_id.partner_id
                    wizard.partner_id = wizard.request_user_id.partner_id
            else:
                wizard.request_user_id = False
                if wizard.request_partner_id:
                    wizard.request_to_id = wizard.request_partner_id
                    wizard.partner_id = wizard.request_partner_id

    @api.onchange('request_to_id')
    def _onchange_request_to_id(self):
        """Keep Contact synchronized with the selected Request To partner."""
        for wizard in self:
            partner = wizard.request_to_id
            wizard.partner_id = partner or False
            wizard.request_user_id = False
            wizard.request_partner_id = False

            if not partner:
                continue

            # If this contact belongs to an internal user, keep that user in
            # the existing request_user_id field for security/Requests logic.
            internal_user = partner.user_ids.filtered(lambda u: not u.share)[:1]
            if internal_user:
                wizard.request_type = 'user'
                wizard.request_user_id = internal_user
            else:
                wizard.request_type = 'partner'
                wizard.request_partner_id = partner

    @api.onchange('request_user_id')
    def _onchange_request_user_id(self):
        """Legacy compatibility: selecting a user selects its partner too."""
        for wizard in self:
            if wizard.request_user_id:
                wizard.request_type = 'user'
                wizard.request_to_id = wizard.request_user_id.partner_id
                wizard.partner_id = wizard.request_user_id.partner_id
            elif not wizard.request_to_id:
                wizard.partner_id = False

    @api.onchange('request_partner_id')
    def _onchange_request_partner_id(self):
        """Legacy compatibility for external-contact callers."""
        for wizard in self:
            if wizard.request_partner_id:
                wizard.request_type = 'partner'
                wizard.request_to_id = wizard.request_partner_id
                wizard.partner_id = wizard.request_partner_id
            elif not wizard.request_to_id:
                wizard.partner_id = False

    @api.constrains('request_type', 'request_to_id', 'request_user_id', 'request_partner_id')
    def _check_recipient(self):
        for wizard in self:
            if not wizard.request_to_id and not wizard.request_user_id and not wizard.request_partner_id:
                raise UserError(_('Please select who you are requesting the document from.'))

    def _compute_request_deadline(self):
        self.ensure_one()
        value = max(self.request_deadline_in or 0, 0)
        today = fields.Date.context_today(self)
        if self.request_deadline_unit == 'weeks':
            return today + timedelta(weeks=value) if value else False
        if self.request_deadline_unit == 'months':
            return today + relativedelta(months=value) if value else False
        return today + timedelta(days=value) if value else False

    def request_document(self):
        self.ensure_one()
        if self.request_deadline_in < 0:
            raise UserError(_('Due Date In cannot be negative.'))
        if not self.folder_id:
            raise UserError(_('Please select a folder.'))

        recipient = self.request_to_id or self.request_partner_id
        if not recipient and self.request_user_id:
            recipient = self.request_user_id.partner_id
        if not recipient:
            raise UserError(_('Please select who you are requesting the document from.'))

        # Prefer the explicitly selected internal user; otherwise detect an
        # internal user linked to the selected partner. This keeps all of the
        # existing security, Requests, Inbox and email behavior intact.
        request_user = self.request_user_id
        if not request_user:
            request_user = recipient.user_ids.filtered(lambda u: not u.share)[:1]

        deadline = self._compute_request_deadline()
        # Keep the recipient partner as the canonical contact on the
        # document, even when the selected partner is linked to an internal
        # user.  This is important for the email recipient and for the
        # Request/Contact fields to remain consistent.
        vals = {
            'name': self.name,
            'folder_id': self.folder_id.id,
            'tag_ids': [(6, 0, self.tag_ids.ids)],
            'partner_id': recipient.id,
            'request_partner_id': recipient.id,
            'request_deadline': deadline,
            'request_note': self.request_note,
            'requested_by_id': self.env.user.id,
            'state': 'requested',
            'res_model': self.resource_model or False,
            'res_id': self.resource_id or False,
        }
        if request_user:
            vals['request_user_id'] = request_user.id

            # Preserve the existing automatic Documents Basic access grant.
            basic_group = self.env.ref(
                'custom_documents.group_documents_basic',
                raise_if_not_found=False,
            )
            if basic_group:
                request_user.sudo().write({
                    'group_ids': [Command.link(basic_group.id)],
                })

        document = self.env['documents.document'].create(vals)
        document.message_post(
            body=_('Document requested from %(recipient)s.', recipient=(
                request_user.name if request_user else recipient.name
            )))
        return {'type': 'ir.actions.act_window_close'}


    def action_send_request(self):
        """Backward-compatible alias for existing callers."""
        return self.request_document()
