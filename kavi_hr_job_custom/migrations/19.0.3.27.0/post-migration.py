# -*- coding: utf-8 -*-
"""
post-migration for 19.0.3.27.0.

BREAKING CHANGE: the separate "Job Board" field on hr.applicant
(job_board_id) has been removed. The stock "Source" field (source_id)
is now restricted directly to the Source(s) that correspond to the
Applied Job's configured Job Boards (see job_board_source_ids /
_compute_job_board_source_ids in models/hr_applicant.py and the
domain on source_id in views/hr_applicant_views.xml).

This is a one-time data continuity backfill: any Applicant that
already had an explicit Job Board picked (job_board_id) but no Source
yet gets that Job Board's Source now, BEFORE the ORM drops the
now-undefined job_board_id column on this module's registry update -
otherwise that already-captured "which Job Board did this Applicant
actually apply through" information would be silently lost.
"""
import logging

from odoo import SUPERUSER_ID, api

_logger = logging.getLogger(__name__)


def migrate(cr, version):
    cr.execute("""
        SELECT column_name FROM information_schema.columns
        WHERE table_name = 'hr_applicant' AND column_name = 'job_board_id'
    """)
    if not cr.fetchone():
        # Fresh install, or this migration already ran - nothing to do.
        return

    cr.execute("""
        SELECT id, job_board_id FROM hr_applicant
        WHERE job_board_id IS NOT NULL AND source_id IS NULL
    """)
    rows = cr.fetchall()
    if not rows:
        return

    env = api.Environment(cr, SUPERUSER_ID, {})
    JobBoard = env['hr.job.board'].sudo()
    Applicant = env['hr.applicant'].sudo()

    for applicant_id, job_board_id in rows:
        board = JobBoard.browse(job_board_id)
        if not board.exists():
            continue
        try:
            with cr.savepoint():
                source = board._get_or_create_utm_source()
                Applicant.browse(applicant_id).write({'source_id': source.id})
        except Exception:
            # The savepoint rolls back only this applicant's failed backfill.
            # Without it, PostgreSQL marks the whole migration transaction as
            # aborted and every subsequent migration script fails with
            # "current transaction is aborted".
            _logger.exception(
                "kavi_hr_job_custom 19.0.3.27.0 post-migration: failed to "
                "backfill Source from job_board_id for hr.applicant id=%s",
                applicant_id,
            )
