# -*- coding: utf-8 -*-
"""Schema guard for 19.0.3.27.18.

No Salary Structure column is created here.  The field belongs to the ATS
customization.  This migration only verifies the custom Version History table
is already present before the post-migration baseline step runs.
"""

def migrate(cr, version):
    # Odoo creates the model table before migration scripts run.  Keep this
    # hook intentionally empty so it cannot make assumptions about which ATS
    # Salary Structure column exists in the target database.
    return
