# -*- coding: utf-8 -*-

import logging

from odoo import api, fields, models, Command

_logger = logging.getLogger(__name__)


class ResPartner(models.Model):
    _inherit = "res.partner"

    is_vendor = fields.Boolean(
        string="Is Vendor",
        help="Enable this to identify this contact as a Vendor and grant Vendor Portal access."
    )

    vendor_ids = fields.One2many(
        'hr.recruitment.vendor', 'partner_id',
        string='Recruitment Vendors',
        help='Recruitment Vendor record(s) that use this Contact as their '
             '"Vendor Contact (Portal Partner)". Name/Email/Phone edited '
             'here are automatically pushed to the matching field(s) on '
             'those Vendor record(s) too.'
    )

    contact_vendor_ids = fields.One2many(
        'hr.recruitment.vendor', 'contact_person_id',
        string='Recruitment Vendors (as Contact Person)',
        help='Recruitment Vendor record(s) whose "Contact Person" Name is '
             'backed by this Contact. Editing this Contact\'s Name here is '
             'automatically pushed back onto the "Contact Person" field on '
             'those Vendor record(s) too.'
    )

    @api.model_create_multi
    def create(self, vals_list):
        partners = super().create(vals_list)
        if not self.env.context.get('kavi_defer_vendor_portal_access'):
            partners.filtered("is_vendor")._grant_vendor_portal_access()
        return partners

    def write(self, vals):
        res = super().write(vals)

        if not self.env.context.get('kavi_defer_vendor_portal_access'):
            if vals.get("is_vendor") or vals.get("active") is True:
                vendor_partners = self.filtered(lambda p: p.is_vendor and p.active)
                if vendor_partners:
                    # Grant the Contact Person first.  This is important when
                    # Vendor and Contact Person share the same email address:
                    # Odoo requires unique portal logins, so one shared email
                    # must resolve to one portal user rather than creating a
                    # duplicate login.
                    for vendor in vendor_partners.sudo().mapped('vendor_ids').filtered('active'):
                        vendor._ensure_contact_person_portal_access()

                    # If the Vendor has its own distinct email, this creates
                    # its own portal user and sends the same standard Odoo
                    # invitation email.
                    vendor_partners._grant_vendor_portal_access()

        # Keep Vendor Portal access synchronized with the standard Active
        # boolean.  Deactivating a Vendor/Contact revokes portal access and
        # clears is_vendor; reactivating a vendor restores the vendor flag and
        # portal membership for any linked user.
        if 'active' in vals:
            inactive_partners = self.filtered(lambda p: not p.active)
            if inactive_partners:
                inactive_partners._revoke_vendor_portal_access()
                inactive_partners.with_context(kavi_portal_active_sync=True).write({
                    'is_vendor': False,
                })
            if vals.get('active') is True:
                reactivated = self.filtered(lambda p: p.active)
                if reactivated and not self.env.context.get('kavi_defer_vendor_portal_access'):
                    reactivated.with_context(kavi_portal_active_sync=True)._grant_vendor_portal_access()
                    for vendor in reactivated.sudo().mapped('vendor_ids').filtered('active'):
                        vendor._ensure_contact_person_portal_access()

        # NOTE: this write() override runs for EVERY res.partner write in the
        # whole database whenever name/email/phone changes - not just for
        # Vendor contacts. `vendor_ids` / `contact_vendor_ids` have no
        # `groups=` restriction of their own, so a plain (non-sudo) read of
        # them forces Odoo to check model-level access on
        # hr.recruitment.vendor for whichever user triggered THIS write.
        # ir.model.access.csv only grants that model to Recruitment
        # User/Manager and Portal - so any other internal user (e.g. a
        # Purchase user editing/syncing an unrelated contact's email) would
        # hit "You are not allowed to access 'Recruitment Vendor' records"
        # here. sudo() is safe: it's only used to look up which Vendor
        # record(s) to sync, mirroring the pattern already used in
        # _grant_vendor_portal_access() below and in
        # HrJob._kavi_portal_get_vendor_jobs().
        sync_fields = {'name', 'email', 'phone'} & set(vals)
        if sync_fields and not self.env.context.get('kavi_skip_vendor_sync'):
            for partner in self:
                vendors = partner.sudo().vendor_ids
                if not vendors:
                    continue
                vendor_vals = {f: partner[f] for f in sync_fields}
                vendors.with_context(kavi_skip_vendor_sync=True).write(vendor_vals)

        if 'name' in vals and not self.env.context.get('kavi_skip_vendor_sync'):
            for partner in self:
                for vendor in partner.sudo().contact_vendor_ids:
                    if vendor.contact_person != partner.name:
                        vendor.with_context(kavi_skip_vendor_sync=True).write({
                            'contact_person': partner.name,
                        })
                for vendor in partner.sudo().vendor_ids:
                    contact = vendor.contact_person_id
                    if contact and contact.company_name != partner.name:
                        contact.with_context(kavi_skip_vendor_sync=True).write({
                            'company_name': partner.name,
                        })

        return res

    def _grant_vendor_portal_access(self):
        """Grant standard Odoo Portal access to these Vendor partners.

        This deliberately uses Odoo's native ``portal.wizard`` instead of a
        custom mail template.  The wizard creates/reuses the portal user,
        prepares the signup token, and sends the same invitation email shown
        by Contacts > Grant Portal Access (including the Activate Account
        button).
        """
        if "portal.wizard" not in self.env:
            _logger.warning(
                "Kavi HR Job Custom: the 'portal' app is not installed; "
                "Portal Access could not be granted to %s.",
                self.mapped("display_name"),
            )
            return

        portal_group = self.env.ref("base.group_portal", raise_if_not_found=False)
        if not portal_group:
            return

        for partner in self.filtered(lambda p: p.active and p.is_vendor and p.email):
            user = partner.with_context(active_test=False).user_ids[:1]
            already_portal = bool(user and user.active and portal_group in user.group_ids)
            if already_portal:
                continue

            # Odoo requires a unique login for every res.users record.  If a
            # Vendor company and its Contact Person intentionally share one
            # email address, the Contact Person may already own the portal
            # user.  Do not try to create a second user with the same login;
            # the standard invitation has already been sent to that address.
            conflicting_user = self.env['res.users'].with_context(active_test=False).sudo().search([
                ('login', '=', partner.email),
                ('partner_id', '!=', partner.id),
            ], limit=1)
            if conflicting_user:
                partner.message_post(
                    body='Portal access granted',
                    subtype_xmlid='mail.mt_note',
                )
                continue

            try:
                self._grant_portal_access_with_standard_wizard(partner)
            except Exception:
                _logger.exception(
                    "Kavi HR Job Custom: failed to grant standard Portal Access "
                    "to Vendor %s.",
                    partner.display_name,
                )

    def _grant_portal_access_with_standard_wizard(self, partner):
        """Grant Portal access and send Odoo's native invitation email."""
        portal_wizard_model = self.env['portal.wizard']
        wizard = portal_wizard_model.sudo().with_context(
            active_model='res.partner',
            active_ids=partner.ids,
            default_partner_ids=partner.ids,
            kavi_skip_portal_access_notifications=True,
        ).create({
            'partner_ids': [Command.set(partner.ids)],
        })

        wizard_user = wizard.user_ids.filtered(lambda u: u.partner_id == partner)[:1]
        if not wizard_user:
            return False

        # Use the standard wizard action.  In Odoo 19 this both grants the
        # Portal group and sends auth_signup.portal_set_password_email, which
        # is the exact "Your account at ... / Activate Account" email shown
        # in the supplied screenshot.
        wizard_user.action_grant_access()

        partner.message_post(
            body='Portal access granted',
            subtype_xmlid='mail.mt_note',
        )
        return True

    def _send_portal_access_email(self):
        """Backward-compatible helper using Odoo's standard Portal wizard."""
        for partner in self.filtered(lambda p: p.active and p.email):
            self._grant_portal_access_with_standard_wizard(partner)

    def _revoke_vendor_portal_access(self):
        """Remove portal access from users linked to inactive Vendor contacts."""
        portal_group = self.env.ref("base.group_portal", raise_if_not_found=False)
        if not portal_group:
            return
        for partner in self:
            for user in partner.user_ids:
                if portal_group in user.group_ids:
                    user.with_context(kavi_skip_portal_access_notifications=True).write({
                        "group_ids": [Command.unlink(portal_group.id)]
                    })
