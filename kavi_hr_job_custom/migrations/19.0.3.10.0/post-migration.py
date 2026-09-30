# -*- coding: utf-8 -*-
"""
post-migration script for 19.0.3.10.0.

FEATURE CHANGE: hr.job.vendor.tracker.link now carries a required
`link_type` field ('job_page' / 'email') and its uniqueness constraint
moved from unique(job_id, vendor_id) to unique(job_id, vendor_id,
link_type) - see models/tracker_link.py and the updated
_create_vendor_tracker_links() in models/hr_job.py. Going forward, adding
a Vendor to a Job Position creates ONE Tracker Link per channel (Job Page
and Email) instead of a single shared one.

Every tracker link row that already exists in the database predates
`link_type` and was, in practice, always the one emailed to the vendor
(see the old _create_vendor_tracker_links(), which called
template.send_mail(link.id, ...) unconditionally on the single link it
created). This migration:

  1. Tags every existing row as link_type='email' (matching how it was
     actually used), so the new NOT NULL column has a correct value and
     the old data keeps rendering as-is under "Email" going forward.
  2. Backfills the missing 'job_page' counterpart for each (job, vendor)
     pair that already has an 'email' link, with a freshly-built URL
     (utm_medium='job_board' instead of 'email') - purely additive, no
     email is (re-)sent for it, and no existing row's URL or email_sent
     flag is touched.
"""
from odoo import api, SUPERUSER_ID


def migrate(cr, version):
    env = api.Environment(cr, SUPERUSER_ID, {})
    _backfill_link_type_and_job_page_links(env)


def _backfill_link_type_and_job_page_links(env):
    Link = env['hr.job.vendor.tracker.link'].sudo()

    # Step 1: every pre-existing row was the one actually emailed to the
    # vendor - tag it 'email' now that the column exists and is required.
    existing_links = Link.search([('link_type', '=', False)])
    for link in existing_links:
        link.write({'link_type': 'email'})

    # Step 2: create the missing 'job_page' link for each (job, vendor)
    # pair, using the same URL-building logic Job Positions use for new
    # Vendors, so old and new tracker links look identical going forward.
    email_links = Link.search([('link_type', '=', 'email')])
    for link in email_links:
        job = link.job_id
        vendor = link.vendor_id
        if not vendor.source_id:
            continue
        already_has_job_page = Link.search_count([
            ('job_id', '=', job.id),
            ('vendor_id', '=', vendor.id),
            ('link_type', '=', 'job_page'),
        ])
        if already_has_job_page:
            continue
        Link.create({
            'job_id': job.id,
            'vendor_id': vendor.id,
            'link_type': 'job_page',
            'url': job._build_tracker_url(vendor, 'job_page'),
        })
