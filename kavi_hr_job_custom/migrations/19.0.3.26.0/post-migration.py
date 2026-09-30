# -*- coding: utf-8 -*-
"""
post-migration for 19.0.3.26.0.

BUG FIX (backfill): before this version, hr.job.vendor.tracker.link had
no unlink() (or vendor-changing write()) sync to remove the matching
hr.recruitment.source row (the standard "Trackers" tab) once a Vendor
Tracker Link for that (job, source) pair no longer existed. Deleting a
vendor's row from the "Vendors" tab left a stale, orphaned Trackers row
behind - a Source with no Vendor Tracker Link backing it any more.

The code fix (tracker_link.py unlink()/write()) only prevents this going
forward. Any Job Position where this already happened needs a one-time
backfill: for every hr.recruitment.source row whose (job, source) pair
has no matching hr.job.vendor.tracker.link left at all, delete it.

Scoped defensively to only ever touch (job, source) pairs where the
Source actually matches a Vendor's own source_id - i.e. rows this
module's own sync could plausibly have created - so a Tracker row a
recruiter added directly for an unrelated Source is never touched.
"""
import logging

from odoo import api, SUPERUSER_ID

_logger = logging.getLogger(__name__)


def migrate(cr, version):
    env = api.Environment(cr, SUPERUSER_ID, {})
    RecruitmentSource = env['hr.recruitment.source'].sudo()
    Link = env['hr.job.vendor.tracker.link'].sudo()

    vendor_source_ids = set(
        env['hr.recruitment.vendor'].sudo().search([
            ('source_id', '!=', False),
        ]).mapped('source_id').ids
    )
    if not vendor_source_ids:
        return

    candidates = RecruitmentSource.search([('source_id', 'in', list(vendor_source_ids))])
    orphaned = candidates.filtered(
        lambda row: not Link.search_count([
            ('job_id', '=', row.job_id.id),
            ('source_id', '=', row.source_id.id),
        ])
    )
    if not orphaned:
        return

    count = len(orphaned)
    orphaned.unlink()
    _logger.info(
        'kavi_hr_job_custom: 19.0.3.26.0 migration removed %d orphaned '
        'Trackers row(s) (hr.recruitment.source) that had no matching '
        'Vendor Tracker Link left (pre-existing data left over from the '
        'missing unlink()/write() sync).',
        count,
    )
