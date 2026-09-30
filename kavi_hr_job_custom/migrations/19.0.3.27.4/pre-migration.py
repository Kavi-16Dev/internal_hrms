# -*- coding: utf-8 -*-
"""Pre-migration 19.0.3.27.4.

Some databases reached this migration with the ORM declaring the Vendor
`contact_person` Char field while the physical PostgreSQL column was still
missing.  During registry migration Odoo can flush dirty vendor records
before/while running post-migrations; that flush then fails with
`UndefinedColumn: hr_recruitment_vendor.contact_person`.

Create the column before the registry/post-migration work.  This is deliberately
SQL-only and idempotent so it is safe on both fully and partially upgraded DBs.
"""


def migrate(cr, version):
    cr.execute("""
        ALTER TABLE hr_recruitment_vendor
        ADD COLUMN IF NOT EXISTS contact_person varchar
    """)
