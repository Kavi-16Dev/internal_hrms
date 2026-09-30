# -*- coding: utf-8 -*-
"""
post-migration script for 19.0.3.13.0.

FIX: `hr.job.vendor.tracker.link.email_url` used to be built by
_build_tracker_url(vendor, 'email') - a UTM-tagged tracker URL (e.g.
"http://host/jobs/odoo-consultant-1?utm_source=hari&utm_medium=email"),
just like the Tracker Link (`url`) column but tagged for the email
channel. As of this version it is built by the new
hr.job._kavi_build_tracker_email() instead, and holds the actual
"<alias>+<source>@<domain>" forwarding address (e.g.
"sales-manager+hari@kaviglobal.com") - matching the Email column on
Odoo's own core "Trackers" tab - not a URL at all.

`email_url` is a stored computed field, but Odoo only recomputes stored
computed fields automatically when one of their `@api.depends()`
fields actually changes value - upgrading the module changes the
*compute logic*, not any dependency, so every row that already had the
old URL-shaped value would otherwise keep showing it (a stale,
now-wrong value) until something unrelated happened to touch
`alias_name` or `source_id` on it. This migration forces a fresh
compute for every existing row so the column is correct immediately
after upgrading.
"""
import logging

from odoo import api, SUPERUSER_ID

_logger = logging.getLogger(__name__)


def migrate(cr, version):
    env = api.Environment(cr, SUPERUSER_ID, {})
    _recompute_email_url(env)


def _recompute_email_url(env):
    Link = env['hr.job.vendor.tracker.link'].sudo()
    links = Link.search([])
    if not links:
        return
    links._compute_email_url()
    links.flush_recordset(['email_url'])
    _logger.info(
        "kavi_hr_job_custom: recomputed email_url (now an email address, "
        "no longer a tracker URL) on %d existing Vendor Tracker Link row(s).",
        len(links),
    )
