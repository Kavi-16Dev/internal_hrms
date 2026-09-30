# -*- coding: utf-8 -*-

"""Post-migration 19.0.3.27.9.

Salary Structure history is initialized in 27.12 using direct SQL.  Avoid ORM
reads here because this script runs while the registry is being rebuilt.
"""

def migrate(cr, version):
    return
