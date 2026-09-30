# -*- coding: utf-8 -*-
"""Portal-access synchronization for Vendor Contact Persons."""

import logging

from odoo import _, models

_logger = logging.getLogger(__name__)


class ResUsers(models.Model):
    _inherit = 'res.users'

    def write(self, vals):
        """Add the same portal-granted chatter event to a Contact Person,
        and send a "Portal Access Granted"/"Portal Access Revoked" e-mail
        (see ``mail_template_portal_access_granted`` /
        ``mail_template_portal_access_revoked`` in
        ``data/mail_template_data.xml``) whenever a user's Portal access
        is granted or revoked.

        Odoo's standard *Grant Access* wizard updates the linked ``res.users``
        record.  Therefore listening on ``res.partner.write`` is not enough to
        reliably detect the action.  We compare portal membership before and
        after the user write and only create the chatter entry for linked Vendor
        Contact Persons whose access actually changed from non-portal to portal.
        """
        portal_group = self.env.ref('base.group_portal', raise_if_not_found=False)
        before_portal = {}
        if portal_group:
            for user in self:
                before_portal[user.id] = portal_group in user.group_ids

        result = super().write(vals)

        if not portal_group:
            return result

        for user in self:
            had_portal = before_portal.get(user.id, False)
            has_portal = portal_group in user.group_ids
            partner = user.partner_id

            # Only Contact Persons managed from the Recruitment Vendor form get
            # this additional message.  This keeps the Company's existing Odoo
            # chatter behaviour unchanged and prevents duplicate notifications.
            if (
                not self.env.context.get('kavi_skip_portal_access_notifications')
                and not had_portal
                and has_portal
                and partner
                and partner.sudo().contact_vendor_ids
            ):
                if not partner.is_vendor:
                    partner.with_context(kavi_portal_access_sync=True).write({
                        'is_vendor': True,
                    })

                partner.message_post(
                    body=_('Portal access granted'),
                    subtype_xmlid='mail.mt_note',
                )

            # Send a dedicated "Portal Access Granted"/"Portal Access
            # Revoked" e-mail whenever this user's Portal access actually
            # changed, no matter which code path triggered the change (the
            # standard "Grant Access" wizard, this module's Vendor/
            # Contact-Person sync, or a manual Group edit).
            #
            # NOTE: this used to call res.users._notify_security_setting_
            # update(), but that method always renders Odoo's built-in
            # "Password Changed" security template regardless of the
            # subject/content passed to it, so the e-mail actually sent
            # never mentioned Portal access at all. Using our own
            # mail.template below is what actually makes the "Portal
            # Access Granted/Revoked" e-mail body appear. Wrapped
            # defensively so an e-mail failure never blocks or alters the
            # access-granting/revoking logic that calls this write().
            if (
                had_portal != has_portal
                and user.email
                and not self.env.context.get('kavi_skip_portal_access_notifications')
            ):
                template_xmlid = (
                    'kavi_hr_job_custom.mail_template_portal_access_granted'
                    if has_portal else
                    'kavi_hr_job_custom.mail_template_portal_access_revoked'
                )
                try:
                    template = self.env.ref(template_xmlid, raise_if_not_found=False)
                    if template:
                        template.sudo().send_mail(user.id, force_send=True)
                except Exception:
                    _logger.exception(
                        "Kavi HR Job Custom: failed to send the Portal "
                        "Access %s e-mail to %s.",
                        "granted" if has_portal else "revoked",
                        user.display_name,
                    )

        return result
