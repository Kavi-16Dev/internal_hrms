# -*- coding: utf-8 -*-
"""Post-migration 19.0.3.27.4.

Do not use the ORM here.  This migration used to recompute the stored
`email_url` on every tracker link.  That caused an implicit environment flush,
which could touch unrelated dirty Vendor records and fail when an older
partially-upgraded database did not yet have `hr_recruitment_vendor.contact_person`.

The current module's compute dependencies will cause the stored value to be
recomputed by Odoo after the registry is ready.  No one-time ORM operation is
required here.
"""


def migrate(cr, version):
    return
