# -*- coding: utf-8 -*-
from odoo import fields, models, api, _, Command
from odoo.exceptions import ValidationError


class HrRecruitmentVendor(models.Model):
    """Custom model to maintain Recruitment Vendors / Staffing Agencies.
    Every vendor MUST be mapped to a Source (utm.source) so that a
    Tracker Link can be generated automatically for that vendor whenever
    it is attached to a Job Position.
    """
    _name = 'hr.recruitment.vendor'
    _description = 'Recruitment Vendor'
    _inherit = ['mail.thread']
    _order = 'name'

  
    _KAVI_PARTNER_RELATED_FIELDS = (
        'street', 'street2', 'city', 'state_id', 'zip', 'country_id',
    )
    
    _KAVI_PARTNER_SYNC_FIELDS = ('name', 'email', 'phone')

    name = fields.Char(string='Vendor Name', required=True, tracking=True)
    email = fields.Char(string='Mail', required=True, tracking=True)
    phone = fields.Char(string='Phone', tracking=True)

    contact_person = fields.Char(
        string='Contact Person',
        compute='_compute_contact_person',
        inverse='_inverse_contact_person',
        help='Name of the individual point of contact at this Vendor. '
             'The displayed value is derived from the linked child Contact '
             '(`contact_person_id`) so this field does not require its own '
             'PostgreSQL column. Typing a name here creates or updates the '
             'matching child Contacts record under the Vendor Contact '
             '(Portal Partner) company.'
    )
    contact_person_id = fields.Many2one(
        'res.partner',
        string='Contact Person (Linked Contact)',
        copy=False,
        help='Internal link to the res.partner Contacts record '
             'auto-created/kept in sync from the Contact Person Name '
             'above. Managed automatically - not shown on the Vendor '
             'form.'
    )
    source_id = fields.Many2one(
        'utm.source',
        string='Source',
        required=True,
        ondelete='restrict',
        help='Every vendor must have a unique Source. This Source is used '
             'to build the Tracker Link when the vendor is added to a Job Position.'
    )


    tracker_link_ids = fields.One2many(
        'hr.job.vendor.tracker.link', 'vendor_id',
        string='Vendor Tracker Links',
        groups='hr_recruitment.group_hr_recruitment_user,'
            'hr_recruitment.group_hr_recruitment_manager',)
    

    # job_ids = fields.One2many(
    #     'hr.job',
    #     'vendor_id',
    #     string='Job Positions',
    #     groups='hr_recruitment.group_hr_recruitment_user,'
    #            'hr_recruitment.group_hr_recruitment_manager',
    #     help='Job Positions assigned to this Vendor. This is a true '
    #          'One2many relationship: each Vendor can have multiple Job '
    #          'Positions, while each Job Position has one Vendor through '
    #          'the hr.job.vendor_id Many2one field.')

    active = fields.Boolean(default=True)
    notes = fields.Text(string='Notes')

    job_ids = fields.One2many(
        'hr.job',
        compute='_compute_job_ids',
        search='_search_job_ids',
        string='Job Positions',
        groups='hr_recruitment.group_hr_recruitment_user,'
            'hr_recruitment.group_hr_recruitment_manager',
        help='Job Positions assigned to this Vendor, sourced from the Vendor '
            'Tracker Links (tracker_link_ids) on each Job Position - the '
            'true multi-vendor relationship. A Job Position can appear '
            'under more than one Vendor.',
    )

    @api.depends('tracker_link_ids.job_id')
    def _compute_job_ids(self):
        for vendor in self:
            vendor.job_ids = vendor.tracker_link_ids.mapped('job_id')

    def _search_job_ids(self, operator, value):
        links = self.env['hr.job.vendor.tracker.link'].search([('job_id', operator, value)])
        return [('id', 'in', links.mapped('vendor_id').ids)]
   
    @api.model
    def _default_recruiter(self):
        """Return the current user only when they have an allowed
        Recruitment access level.

        The Recruiter field is intentionally limited to users who have
        either:
          * Recruitment Officer / Manage all applicants
          * Recruitment Administrator

        Interviewer-only users and ordinary internal users must not be
        selectable or assigned as a Vendor Recruiter.
        """
        user = self.env.user
        if (
            user.has_group('hr_recruitment.group_hr_recruitment_user')
            or user.has_group('hr_recruitment.group_hr_recruitment_manager')
        ):
            return user
        return self.env['res.users']

    user_id = fields.Many2one(
        'res.users',
        string='Recruiter',
        default=_default_recruiter,
        tracking=True,
        help='The recruiter responsible for this vendor. Only this recruiter '
             'and the Vendor Contact below can see and post messages in the '
             'Chatter below - the conversation is private to the two of them.'
    )
    partner_id = fields.Many2one(
        'res.partner',
        string='Vendor Contact (Portal Partner)',
        tracking=True,
        domain="[('is_company', '=', True)]",
      
        context={'default_is_company': True, 'default_company_type': 'company', 'default_is_vendor': True},
        help='The Company-type Contacts record that represents this Vendor '
             '(its Name IS the Vendor\'s Company Name). Auto-created and '
             'kept in sync with the Vendor Name/Mail/Phone above if left '
             'empty - see the class docstring in models/vendor.py for the '
             'full two-way sync behaviour. Grant this contact Portal access '
             '(Settings > Users > Grant Portal Access) so they can log in '
             'and privately exchange messages with the Recruiter above.'
    )

    street = fields.Char(related='partner_id.street', store=True, readonly=False, string='Street')
    street2 = fields.Char(related='partner_id.street2', store=True, readonly=False, string='Street 2')
    city = fields.Char(related='partner_id.city', store=True, readonly=False, string='City')
    state_id = fields.Many2one(
        'res.country.state',
        related='partner_id.state_id',
        store=True,
        readonly=False,
        string='State',
    )
    zip = fields.Char(related='partner_id.zip', store=True, readonly=False, string='ZIP')
    country_id = fields.Many2one(
        'res.country', related='partner_id.country_id', store=True, readonly=False, string='Country')

    @api.onchange('state_id')
    def _onchange_state_id(self):
        """Set Country from the selected State, like Odoo Contacts."""
        for vendor in self:
            if vendor.state_id and vendor.state_id.country_id:
                vendor.country_id = vendor.state_id.country_id

    @api.onchange('country_id')
    def _onchange_country_id(self):
        """Clear State when a manually selected Country is incompatible."""
        for vendor in self:
            if vendor.country_id and vendor.state_id and vendor.state_id.country_id != vendor.country_id:
                vendor.state_id = False

    def _prepare_state_country_vals(self, vals):
        """When State is supplied, derive its Country automatically.

        This mirrors the form onchange for imports, RPC calls and other
        server-side writes. It is intentionally limited to the address
        fields and does not alter unrelated Vendor values.
        """
        vals = dict(vals)
        state_value = vals.get('state_id')
        if state_value:
            state_id = state_value.id if hasattr(state_value, 'id') else state_value
            state = self.env['res.country.state'].browse(state_id).exists()
            if state and state.country_id:
                vals['country_id'] = state.country_id.id
        return vals

    _name_uniq = models.Constraint(
        'UNIQUE(name)',
        'A Vendor with this name already exists.',
    )
    _source_uniq = models.Constraint(
        'UNIQUE(source_id)',
        'This Source is already mapped to another Vendor. Each Vendor needs its own Source.',
    )

    @api.onchange('source_id')
    def _onchange_source_id(self):
        """Give the user a normal form warning instead of an uncaught
        client promise when a Source is already assigned to another Vendor.

        The database constraint below is intentionally kept as the final
        server-side protection.  The onchange only improves the UI/UX: Odoo
        can otherwise surface the SQL constraint failure as an
        ``UncaughtPromiseError`` with an unhelpful ``undefined`` message in
        the web client.
        """
        for vendor in self:
            if not vendor.source_id:
                continue
            duplicate = self.env['hr.recruitment.vendor'].search([
                ('source_id', '=', vendor.source_id.id),
                ('id', '!=', vendor._origin.id if vendor._origin else 0),
            ], limit=1)
            if duplicate:
                duplicate_name = duplicate.name
                source_name = vendor.source_id.name
                vendor.source_id = False
                return {
                    'warning': {
                        'title': _('Source Already Assigned'),
                        'message': _(
                            'The Source "%s" is already assigned to Vendor "%s". '
                            'Each Vendor must have a different Source. Please select '
                            'another Source.'
                        ) % (source_name, duplicate_name),
                    }
                }

    @api.constrains('user_id')
    def _check_recruiter_access(self):
        """Prevent assigning an Interviewer/ordinary user as Recruiter.

        The XML domain provides the dropdown filtering in the web client,
        while this constraint protects the rule for imports, RPC calls and
        other server-side writes.
        """
        for vendor in self:
            recruiter = vendor.user_id
            if not recruiter:
                continue
            if not (
                recruiter.has_group('hr_recruitment.group_hr_recruitment_user')
                or recruiter.has_group('hr_recruitment.group_hr_recruitment_manager')
            ):
                raise ValidationError(_(
                    'The Recruiter must be a Recruitment Officer (Manage all applicants) '
                    'or a Recruitment Administrator.'
                ))

    @api.constrains('email')
    def _check_email(self):
        for rec in self:
            if rec.email and '@' not in rec.email:
                raise ValidationError(_('Please enter a valid email address for vendor "%s".') % rec.name)

     
    def _sync_partner_from_vendor(self):
        """Keep the linked company Contact synchronized with the Vendor.

        The Vendor ``active`` switch is the source of truth for the vendor
        flag on ``res.partner``.  This is important when an inactive Vendor
        is edited: changing its name/email must never accidentally restore
        vendor status or portal access.
        """
        Partner = self.env['res.partner']
        for rec in self:
            vals = {f: rec[f] for f in rec._KAVI_PARTNER_SYNC_FIELDS}
            vals.update({
                'company_type': 'company',
                'is_vendor': bool(rec.active),
                'active': bool(rec.active),
            })
            if not rec.partner_id:
                partner = Partner.with_context(kavi_skip_vendor_sync=True, kavi_defer_vendor_portal_access=True).create(vals)
                super(HrRecruitmentVendor, rec).write({'partner_id': partner.id})
            else:
                partner = rec.partner_id
                changed = {f: v for f, v in vals.items() if partner[f] != v}
                if changed:
                    partner.with_context(kavi_skip_vendor_sync=True, kavi_defer_vendor_portal_access=True).write(changed)

    @api.depends('contact_person_id.name')
    def _compute_contact_person(self):
        """Display the linked child Contact's name.

        `contact_person` used to be a stored Char column. The database in
        some existing installations no longer has that column because the
        feature was migrated through a Many2one-backed implementation.
        Keeping this field non-stored makes the model compatible with both
        schemas while preserving the same UI behaviour.
        """
        for rec in self:
            rec.contact_person = rec.contact_person_id.name or False

    def _inverse_contact_person(self):
        """Persist edits through the linked res.partner Contact.

        The actual source of truth is `contact_person_id.name`; no
        `hr_recruitment_vendor.contact_person` database column is needed.
        """
        self._sync_contact_person()

    def _sync_contact_person(self, contact_names=None):
        """Create/update the real Contact Person partner.

        The ``contact_person`` field is a non-stored computed field backed by
        ``contact_person_id.name``.  During ``create()`` Odoo can execute the
        computed-field inverse before ``partner_id`` exists, so reading
        ``rec.contact_person`` after ``super().create()`` can lose the name
        entered by the user.  ``contact_names`` therefore carries the exact
        value supplied in the original create payload until the linked
        partner has been created.
        """
        Partner = self.env['res.partner']
        contact_names = contact_names or {}

        for rec in self:
            if not rec.partner_id:
                continue

            if rec.id in contact_names:
                name = (contact_names.get(rec.id) or '').strip()
            else:
                name = (rec.contact_person or '').strip()

            if not name:
                continue

            vals = {
                'name': name,
                'parent_id': rec.partner_id.id,
                'company_name': rec.partner_id.name,
                'type': 'contact',
                'company_type': 'person',
            }
            if rec.contact_person_id:
                partner = rec.contact_person_id
                changed = {f: v for f, v in vals.items() if partner[f] != v}
                if changed:
                    partner.with_context(kavi_skip_vendor_sync=True).write(changed)
            else:
                partner = Partner.with_context(
                    kavi_skip_vendor_sync=True,
                    kavi_defer_vendor_portal_access=True,
                ).create(vals)
                super(HrRecruitmentVendor, rec).write({'contact_person_id': partner.id})



    def _get_vendor_portal_user(self, contact):
        """Return the first User linked to the Vendor Contact Person."""
        return contact.user_ids[:1]

    def _ensure_contact_person_portal_access(self):
        """Grant standard Portal access to the Vendor Contact Person.

        The Contact Person is a separate ``res.partner`` child record.  It
        receives the same native Odoo Portal invitation email as the Vendor
        company.  If the Contact already has its own email, it is preserved;
        otherwise the Vendor email remains the fallback for compatibility
        with the existing Vendor form.
        """
        for rec in self.filtered(lambda vendor: vendor.active):
            contact = rec.contact_person_id
            if not contact:
                continue

            vals = {'is_vendor': True, 'active': True}
            if not contact.email and rec.email:
                vals['email'] = rec.email
            contact.with_context(
                kavi_skip_vendor_sync=True,
                kavi_defer_vendor_portal_access=True,
            ).write(vals)

            if contact.email:
                contact._grant_vendor_portal_access()



    def _post_portal_access_granted_message(self, vendor, contact):
        """Post the portal-access confirmation on both Vendor partners.

        The Vendor's company partner and the Contact Person are separate
        ``res.partner`` records.  Portal access belongs to the Contact Person
        user, but the Company form must also show the same confirmation in
        its Chatter.  Posting from this single helper keeps both Chatter
        entries consistent and avoids maintaining two independent messages.
        """
        body = _('Portal access granted')
        subtype = 'mail.mt_note'

        company = vendor.partner_id
        if company:
            company.message_post(body=body, subtype_xmlid=subtype)

        if contact and contact != company:
            contact.message_post(body=body, subtype_xmlid=subtype)

    def _revoke_vendor_portal_access(self):
        """Revoke portal access from the Vendor's linked partners/users."""
        partners = self.mapped('partner_id') | self.mapped('contact_person_id')
        if not partners:
            return

        portal_group = self.env.ref('base.group_portal', raise_if_not_found=False)
        if portal_group:
            for partner in partners:
                for user in partner.user_ids:
                    if portal_group in user.group_ids:
                        user.write({'group_ids': [Command.unlink(portal_group.id)]})
                        partner.message_post(
                            body=_('Portal access revoked'),
                            subtype_xmlid='mail.mt_note',
                        )

        partners.with_context(kavi_skip_vendor_sync=True).write({
            'is_vendor': False,
        })

    def _sync_vendor_active_state(self):
        """Make Vendor ``active`` control partner status and portal access."""
        for rec in self:
            partners = rec.partner_id | rec.contact_person_id
            if not partners:
                continue

            if rec.active:
                partners.with_context(
                    kavi_skip_vendor_sync=True,
                    kavi_defer_vendor_portal_access=True,
                ).write({
                    'active': True,
                    'is_vendor': True,
                })
                if rec.partner_id:
                    rec.partner_id._grant_vendor_portal_access()
                rec._ensure_contact_person_portal_access()
            else:
                partners.with_context(
                    kavi_skip_vendor_sync=True,
                    kavi_defer_vendor_portal_access=True,
                ).write({
                    'active': False,
                    'is_vendor': False,
                })
                rec._revoke_vendor_portal_access()

    def _sync_chatter_participants(self):
        """Keep the Chatter's followers limited to exactly the assigned
        Recruiter (user_id) and the Vendor Contact (partner_id), so the
        conversation stays private between just those two parties."""
        for rec in self:
            partner_ids = set()
            if rec.user_id and rec.user_id.partner_id:
                partner_ids.add(rec.user_id.partner_id.id)
            if rec.partner_id:
                partner_ids.add(rec.partner_id.id)
            current_followers = rec.message_follower_ids.partner_id
            to_remove = [pid for pid in current_followers.ids if pid not in partner_ids]
            if to_remove:
                rec.message_unsubscribe(partner_ids=to_remove)
            if partner_ids:
                rec.message_subscribe(partner_ids=list(partner_ids))

    @api.model_create_multi
    def create(self, vals_list):
        # Preserve the Contact Person name exactly as entered.  The field is
        # computed/inverse-backed, so its value may not survive the initial
        # create cycle until contact_person_id exists.
        vals_list = [self._prepare_state_country_vals(vals) for vals in vals_list]

        contact_names_by_input = [
            (vals.get('contact_person') or '').strip()
            for vals in vals_list
        ]

        deferred_vals_list = [
            {f: vals.pop(f) for f in self._KAVI_PARTNER_RELATED_FIELDS if f in vals}
            for vals in vals_list
        ]

        records = super().create(vals_list)
        records._sync_partner_from_vendor()

        for record, deferred_vals in zip(records, deferred_vals_list):
            if deferred_vals:
                record.write(deferred_vals)

        contact_names = {
            record.id: name
            for record, name in zip(records, contact_names_by_input)
            if name
        }
        records._sync_contact_person(contact_names=contact_names)
        records.invalidate_recordset(['contact_person'])

        # Grant standard Portal access to the Contact Person when a Vendor is
        # created.  The Vendor company itself is granted automatically when
        # its ``is_vendor`` flag is enabled from Contacts; keeping the create
        # path contact-first avoids a duplicate-login conflict when the Vendor
        # and Contact Person intentionally share the same email address.
        for record in records.filtered('active'):
            record._ensure_contact_person_portal_access()
            if not record.contact_person_id or record.contact_person_id.email != record.email:
                if record.partner_id:
                    record.partner_id._grant_vendor_portal_access()

        records._sync_vendor_active_state()
        records._sync_chatter_participants()
        return records



    def write(self, vals):
        vals = self._prepare_state_country_vals(vals)
        res = super().write(vals)

        skip_sync = self.env.context.get('kavi_skip_vendor_sync')

        sync_triggers = set(self._KAVI_PARTNER_SYNC_FIELDS) | {'partner_id'}
        partner_synced = False
        if sync_triggers & set(vals) and not skip_sync:
            self._sync_partner_from_vendor()
            partner_synced = True

        if ('contact_person' in vals or partner_synced) and not skip_sync:
            self._sync_contact_person()

        if ({'contact_person', 'email', 'active'} & set(vals) or partner_synced) and not skip_sync:
            self._ensure_contact_person_portal_access()

        if ('active' in vals or partner_synced) and not skip_sync:
            active_vendors = self.filtered('active')
            for vendor in active_vendors:
                if vendor.partner_id:
                    vendor.partner_id._grant_vendor_portal_access()
        if 'user_id' in vals or 'partner_id' in vals or partner_synced:
            self._sync_chatter_participants()

        if 'active' in vals and not skip_sync:
            self._sync_vendor_active_state()

        if 'source_id' in vals:
            links = self.env['hr.job.vendor.tracker.link'].search([
                ('vendor_id', 'in', self.ids),
            ])
            links._refresh_tracker_urls()
            links._sync_recruitment_source_tracker()

        return res
