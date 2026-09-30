# -*- coding: utf-8 -*-
"""
post-migration script for 19.0.3.12.0.

FIX: hr.job._create_vendor_tracker_links() used to auto-create TWO
hr.job.vendor.tracker.link rows per (Job, Vendor) pair whenever the Job
Position had an Email Alias configured - one link_type='job_page' row
and one link_type='email' row - so the Vendors tab list showed two
rows per Vendor differing only in "Link Type". As of this version, the
Email Tracker link is a plain computed field (`email_url`) on the
SAME row as the 'job_page' link instead - see
hr.job.vendor.tracker.link._compute_email_url() - so only one
auto-generated row per Vendor remains, and manually-added rows ("Add a
line") are the only way a second "Link Type" row can appear.

`email_url` is a stored computed field, so simply upgrading the module
recomputes it correctly for every existing 'job_page' row (it depends
on job_id.alias_name/alias_full_name and vendor_id.source_id, both
already set). What recomputing alone can't do is preserve
`email_sent`/whether the vendor was actually emailed, since that lived
on the now-redundant 'email' row. This migration:

  1. For every (job_id, vendor_id) pair that has BOTH a 'job_page' and
     an 'email' row, copies `email_sent` from the 'email' row onto the
     'job_page' row (so "was this vendor emailed" isn't lost).
  2. Deletes the now-redundant 'email' rows.

Vendors that only ever had a single row (e.g. no Email Alias was ever
configured, or the extra row was removed already) are untouched.
"""
import logging

from odoo import api, SUPERUSER_ID

_logger = logging.getLogger(__name__)


def migrate(cr, version):
    env = api.Environment(cr, SUPERUSER_ID, {})
    _collapse_duplicate_email_rows(env)


def _collapse_duplicate_email_rows(env):
    Link = env['hr.job.vendor.tracker.link'].sudo()

    email_rows = Link.search([('link_type', '=', 'email')])
    collapsed = 0
    for email_row in email_rows:
        job_page_row = Link.search([
            ('job_id', '=', email_row.job_id.id),
            ('vendor_id', '=', email_row.vendor_id.id),
            ('link_type', '=', 'job_page'),
        ], limit=1)
        if not job_page_row:
            # No matching 'job_page' row (e.g. it was manually deleted) -
            # leave this row as-is rather than guess; it will keep
            # showing under Link Type as a manually-managed row.
            continue

        if email_row.email_sent and not job_page_row.email_sent:
            job_page_row.write({'email_sent': True})
        email_row.unlink()
        collapsed += 1

    if collapsed:
        _logger.info(
            "kavi_hr_job_custom: collapsed %d duplicate auto-generated "
            "'email' Tracker Link row(s) into their matching 'job_page' "
            "row's Email Tracker column.",
            collapsed,
        )
