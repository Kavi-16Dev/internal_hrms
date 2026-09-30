# -*- coding: utf-8 -*-
"""
post-migration for 19.0.3.17.0.

The Vendor Tracker Link ``email_url`` field previously stored the actual
email alias address (for example ``sales-manager+mani@example.com``).
The UI requirement is that the Vendors tab shows an ``Email Link`` next to
``Tracker Link``, using the same public Job URL and Source with
``utm_medium=email``.

Force a recompute so existing rows immediately receive the new URL after
module upgrade.
"""
import logging

from odoo import api, SUPERUSER_ID

_logger = logging.getLogger(__name__)


def migrate(cr, version):
    env = api.Environment(cr, SUPERUSER_ID, {})
    links = env['hr.job.vendor.tracker.link'].sudo().search([])
    if not links:
        return

    links._compute_email_url()
    links.flush_recordset(['email_url'])
    _logger.info(
        'kavi_hr_job_custom: recomputed %d Vendor Tracker Link email_url '
        'value(s) as Email Tracker URLs during 19.0.3.17.0 migration.',
        len(links),
    )
