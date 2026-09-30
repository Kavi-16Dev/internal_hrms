# -*- coding: utf-8 -*-
"""
post-migration script for 19.0.3.11.0.

FEATURE CHANGE: hr.recruitment.vendor's "Contact Person" is a plain typed
Name (Char, `contact_person`) again instead of a Many2one picker. Behind
the scenes it is still backed by a real CHILD res.partner record (its id
kept in `contact_person_id`, not shown on the form anymore) that is
auto-created/updated from the typed Name - see
HrRecruitmentVendor._sync_contact_person() in models/vendor.py. That
linked Contact's "Company Name" (`company_name`) is kept equal to the
Vendor Contact (Portal Partner) company's own Name.

For Vendors that already had a `contact_person_id` linked from the
previous (Many2one-only) version of this feature, this migration:

  1. Backfills the new `contact_person` Char field from that linked
     Contact's Name, so existing data keeps displaying as-is on the
     simplified form.
  2. Sets `company_name` on that same linked Contact to match the
     Vendor's Company (`partner_id.name`), so it matches what
     _sync_contact_person() would have produced had the Vendor been
     saved fresh under this version.

Nothing is deleted or unlinked - `contact_person_id` keeps pointing at
the exact same res.partner record either way.
"""
import logging

from odoo import api, SUPERUSER_ID

_logger = logging.getLogger(__name__)


def migrate(cr, version):
    env = api.Environment(cr, SUPERUSER_ID, {})
    _backfill_contact_person_char(env)


def _backfill_contact_person_char(env):
    Vendor = env['hr.recruitment.vendor'].sudo()

    vendors = Vendor.search([('contact_person_id', '!=', False)])
    count = 0
    for vendor in vendors:
        contact = vendor.contact_person_id
        vendor.with_context(kavi_skip_vendor_sync=True).write({
            'contact_person': contact.name,
        })
        if vendor.partner_id and contact.company_name != vendor.partner_id.name:
            contact.with_context(kavi_skip_vendor_sync=True).write({
                'company_name': vendor.partner_id.name,
            })
        count += 1

    if count:
        _logger.info(
            "kavi_hr_job_custom: backfilled contact_person Char on %d "
            "existing Vendor(s) from their linked Contact Person record.",
            count,
        )
