# -*- coding: utf-8 -*-

"""Post-migration 19.0.3.27.8.

No ORM work is performed during registry upgrade.  The previous implementation
read stored computed fields while the schema could still be incomplete.
"""

def migrate(cr, version):
    return
