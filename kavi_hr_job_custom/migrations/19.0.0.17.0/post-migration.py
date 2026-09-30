# -*- coding: utf-8 -*-
"""Migrate Job Position -> Vendor from Many2many to true One2many/Many2one.

Before 19.0.0.17.0:
    hr.job.vendor_ids -> Many2many -> hr_job_vendor_rel

From 19.0.0.17.0:
    hr.job.vendor_id -> Many2one
    hr.recruitment.vendor.job_ids -> One2many

A Job Position can now have only one Vendor. If legacy data contains more
than one Vendor for a Job Position, the first relation row is retained
(deterministically by vendor_id) and the extra assignments are logged.
"""
import logging

from odoo import api, SUPERUSER_ID

_logger = logging.getLogger(__name__)


def migrate(cr, version):
    env = api.Environment(cr, SUPERUSER_ID, {})

    # The old Many2many relation table is still available at this point.
    cr.execute("""
        SELECT job_id, vendor_id
          FROM hr_job_vendor_rel
         WHERE job_id IS NOT NULL
           AND vendor_id IS NOT NULL
         ORDER BY job_id, vendor_id
    """)
    rows = cr.fetchall()

    assignments = {}
    discarded = []
    for job_id, vendor_id in rows:
        if job_id not in assignments:
            assignments[job_id] = vendor_id
        else:
            discarded.append((job_id, vendor_id))

    Job = env['hr.job'].sudo()
    updated = 0
    for job_id, vendor_id in assignments.items():
        job = Job.browse(job_id)
        if not job.exists():
            continue
        if not job.vendor_id:
            job.write({'vendor_id': vendor_id})
            updated += 1

    if discarded:
        _logger.warning(
            'kavi_hr_job_custom: %d legacy Job Position/Vendor '
            'Many2many assignments could not be preserved because '
            'hr.job.vendor_id is now Many2one. Retained the lowest '
            'vendor_id for each affected Job Position. Discarded rows: %s',
            len(discarded),
            discarded,
        )

    _logger.info(
        'kavi_hr_job_custom: migrated %d Job Position Vendor assignment(s) '
        'from hr_job_vendor_rel to hr.job.vendor_id.',
        updated,
    )
