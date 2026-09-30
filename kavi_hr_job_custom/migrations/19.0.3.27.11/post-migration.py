# -*- coding: utf-8 -*-

"""Post-migration 19.0.3.27.11.

Kept as an idempotent no-op.  Salary Structure schema initialization and
backfill are handled by 27.12 without ORM model searches.
"""

def migrate(cr, version):
    return
