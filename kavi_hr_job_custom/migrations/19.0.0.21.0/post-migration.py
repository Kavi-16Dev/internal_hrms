# -*- coding: utf-8 -*-
"""
post-migration script for 19.0.0.21.0.

FEATURE: hr.recruitment.vendor's "Contact Person" and "Vendor Contact
(Portal Partner)" are now real res.partner links instead of a plain Char
field, so changes on either side are automatically reflected in
Contacts (see models/vendor.py / models/res_partner.py for the full
two-way sync).

This migration performs the one-time data move for records that already
exist:

  1) `contact_person` (the OLD plain Char field, removed from the model
     in this version - its column is dropped at the end of this script)
     is copied onto a brand-new CHILD res.partner record, linked under
     that Vendor's `partner_id` company (creating `partner_id` itself
     first, from the Vendor's own Name/Email/Phone, exactly like
     HrRecruitmentVendor._sync_partner_from_vendor() does for a normal
     save - if the Vendor didn't already have one), and that new
     Contact's id is written into the new `contact_person_id` field.

  2) Any Vendor that has NO `partner_id` at all yet (most existing
     records, since this is a brand-new required relationship) gets one
     auto-created from its own Name/Email/Phone, same as (1).

Both steps reuse the model's own create()/write() (via the ORM, not raw
SQL) so the full sync/is_vendor/portal-access logic in
HrRecruitmentVendor and ResPartner already runs exactly as it would for
a normal user-triggered save - this script only decides WHICH records
need that save and what one-time value (the old contact_person text) to
seed into the new structure.
"""
import logging

from odoo import api, SUPERUSER_ID

_logger = logging.getLogger(__name__)


def migrate(cr, version):
    env = api.Environment(cr, SUPERUSER_ID, {})
    _migrate_vendor_contacts(env, cr)


def _migrate_vendor_contacts(env, cr):
    Vendor = env['hr.recruitment.vendor']

    # The `contact_person` column still exists physically at this point
    # (its Python field was only just removed from the model in this
    # version, Odoo doesn't drop the column on its own) - read it with
    # raw SQL since the ORM no longer knows this field.
    cr.execute("""
        SELECT id, contact_person
        FROM hr_recruitment_vendor
        WHERE contact_person IS NOT NULL AND contact_person != ''
    """)
    old_contact_person_by_vendor_id = dict(cr.fetchall())

    vendors = Vendor.sudo().search([])
    for vendor in vendors:
        # Step (1)/(2) combined: _sync_partner_from_vendor() auto-creates
        # partner_id (the Company) from the Vendor's own Name/Email/Phone
        # if none is set yet - a no-op if partner_id already exists.
        vendor._sync_partner_from_vendor()

        old_name = old_contact_person_by_vendor_id.get(vendor.id)
        if old_name and not vendor.contact_person_id:
            contact = env['res.partner'].with_context(kavi_skip_vendor_sync=True).create({
                'name': old_name,
                'parent_id': vendor.partner_id.id,
                'company_type': 'person',
                'type': 'contact',
            })
            vendor.write({'contact_person_id': contact.id})
            _logger.info(
                "kavi_hr_job_custom: migrated Vendor id=%s old contact_person "
                "text %r to new Contact Person res.partner id=%s under "
                "Company res.partner id=%s.",
                vendor.id, old_name, contact.id, vendor.partner_id.id,
            )

    if old_contact_person_by_vendor_id:
        _logger.info(
            "kavi_hr_job_custom: migrated %d existing contact_person value(s).",
            len(old_contact_person_by_vendor_id),
        )
    # Always attempt this, regardless of whether any row actually had a
    # value - the column is no longer part of the model either way, and
    # DROP COLUMN IF EXISTS is a safe no-op if it's already gone.
    cr.execute("ALTER TABLE hr_recruitment_vendor DROP COLUMN IF EXISTS contact_person")
