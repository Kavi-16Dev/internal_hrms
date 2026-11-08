# -*- coding: utf-8 -*-
"""My Drive folders must be root workspaces.

Older versions created every user's My Drive as a child of the Company
Drive, so everything a user stored in My Drive was listed under Company and
inherited the Company Drive's general access.  Detach the existing ones.
"""
import logging

from odoo import SUPERUSER_ID, api

_logger = logging.getLogger(__name__)


def migrate(cr, version):
    env = api.Environment(cr, SUPERUSER_ID, {})
    count = env['documents.folder']._detach_employee_drives_from_company()
    _logger.info('Documents: detached %s My Drive folder(s) from the Company Drive.', count)
