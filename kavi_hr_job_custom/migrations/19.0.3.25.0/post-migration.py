# -*- coding: utf-8 -*-
"""
post-migration for 19.0.3.25.0.

BUG FIX (backfill): before this version, hr.job.vendor.tracker.link had
no unlink() (or vendor-changing write()) sync back onto hr.job.vendor_id.
Deleting a vendor's row from the Job Position's "Vendors" tab removed
their Tracker Link record but left them on vendor_id - which is the
ONLY field the Vendor Portal (kavi_vendor_portal._kavi_portal_get_vendor_
jobs) filters on. Result: a vendor who was removed from a Job Position
kept seeing it under "Job Positions" on their own portal indefinitely.

The code fix (tracker_link.py unlink()/write()) only prevents this going
forward. Any Job Position where this already happened needs a one-time
backfill: for every Job Position whose vendor_id currently points at a
Vendor that has NO matching tracker_link_ids row left at all, clear that
vendor_id, exactly as the new unlink()/write() logic would have done at
the time the row was actually deleted.

NOTE: as of migration 19.0.0.17.0, hr.job.vendor_ids (Many2many) was
replaced by hr.job.vendor_id (Many2one) - a Job Position can only have
one Vendor. This script must use vendor_id, not the old vendor_ids name.
"""
import logging

from odoo import api, SUPERUSER_ID

_logger = logging.getLogger(__name__)


def migrate(cr, version):
    env = api.Environment(cr, SUPERUSER_ID, {})
    Job = env['hr.job'].sudo()

    jobs = Job.search([('vendor_id', '!=', False)])
    fixed_jobs = 0

    for job in jobs:
        linked_vendor_ids = set(job.tracker_link_ids.mapped('vendor_id').ids)
        if job.vendor_id.id in linked_vendor_ids:
            continue
        job.write({'vendor_id': False})
        fixed_jobs += 1

    if fixed_jobs:
        _logger.info(
            'kavi_hr_job_custom: 19.0.3.25.0 migration cleared vendor_id '
            'on %d Job Position(s) that had no matching Vendor Tracker '
            'Link left (pre-existing data left over from the missing '
            'unlink()/write() sync).',
            fixed_jobs,
        )
