# -*- coding: utf-8 -*-
"""
Post-migration script: 19.0.2.1.1

Fixes the crash:

    UncaughtPromiseError > EvalError
    Can not evaluate python expression: ({'default_folder_id': ref('documents_folder_company')})
    Error: Name 'ref' is not defined

Root cause
----------
`ref('xml_id')` is only ever valid inside an `eval="..."` attribute,
which Odoo evaluates server-side (in Python, with `ref` injected into
the eval globals) while *loading* XML data - see how
`security/documents_security.xml` uses it correctly:

    <field name="user_ids" eval="[(4, ref('base.user_admin'))]"/>

It is NEVER valid inside the plain text of a `<field name="context">`
value (or a view's `context="..."` attribute). That text is stored
as-is in the `context` column of `ir_act_window` and is evaluated
*client-side* in JavaScript (py.js) whenever the action/menu is
opened - and the JS evaluator has no `ref()` function, hence the
`Name 'ref' is not defined` error.

This module's current XML no longer contains that mistake (all
context values use plain literal dicts, e.g.
`{'default_folder_is_company_drive': 1}`), but if an earlier version
of the module (or a manual edit via Settings > Technical > Actions >
Window Actions) ever stored a context containing `ref(...)`, that bad
string persists in the database until something rewrites it. A plain
`-u custom_documents` upgrade normally re-syncs `context` from the XML
- but only for actions that are *not* `noupdate="1"` and only if the
xml_id still resolves correctly, so we also sanitize defensively here
in case the action was hand-edited, duplicated, or renamed.
"""
import logging

_logger = logging.getLogger(__name__)

# xml_id (without module prefix) -> known-good context, taken straight
# from this module's own view definitions.
KNOWN_GOOD_CONTEXTS = {
    'documents_document_action': "{'search_default_my_documents': 0}",
    'documents_document_action_company_drive': "{'default_folder_is_company_drive': 1}",
    'documents_document_action_spreadsheet_templates': "{'default_folder_is_company_drive': 1}",
    'documents_document_action_recent': "{'search_default_recent': 1}",
    'documents_document_action_trash': "{'active_test': False}",
}


def migrate(cr, version):
    if not version:
        # Fresh install picks up the (already correct) XML directly.
        return

    env = _get_env(cr)

    fixed = 0

    # 1) Re-sync the specific actions this module ships, in case their
    #    stored context still contains a stale ref(...) call.
    for xml_suffix, good_context in KNOWN_GOOD_CONTEXTS.items():
        xml_id = 'custom_documents.%s' % xml_suffix
        action = env.ref(xml_id, raise_if_not_found=False)
        if action and action.context and 'ref(' in action.context:
            _logger.warning(
                "Repairing stale context on %s (contained ref(...)): %r -> %r",
                xml_id, action.context, good_context,
            )
            action.sudo().write({'context': good_context})
            fixed += 1

    # 2) Belt-and-suspenders: catch any *other* window action left over
    #    in the database (manually created/edited, duplicated, or from
    #    a since-renamed xml_id) that still has a raw ref(...) call in
    #    its context. We can't know the intended replacement for those,
    #    so we clear the context to an empty dict rather than leave it
    #    permanently broken - it can be re-edited by hand afterwards if
    #    a specific default was needed.
    stale = env['ir.actions.act_window'].sudo().search([('context', 'like', 'ref(')])
    for action in stale:
        _logger.warning(
            "Clearing unrecognised stale ref(...) context on action id=%s (%r): %r",
            action.id, action.name, action.context,
        )
        action.write({'context': '{}'})
        fixed += 1

    if fixed:
        _logger.info("custom_documents post-migrate: repaired %d action(s).", fixed)
    else:
        _logger.info("custom_documents post-migrate: no stale ref(...) contexts found.")


def _get_env(cr):
    """Return an environment, compatible with the Odoo version running
    this migration (env(cr) helper differs slightly across versions)."""
    from odoo import api, SUPERUSER_ID
    return api.Environment(cr, SUPERUSER_ID, {})
