# models/mail_activity.py

from odoo import models

class MailActivity(models.Model):
    _inherit = 'mail.activity'

    def action_feedback(self, feedback=False, attachment_ids=None):
        """
        When a 'Create Purchase Order' activity is marked done on a purchase.request,
        automatically CANCEL all other buyers' same activities on that PR.
        """
        for activity in self:
            if (
                activity.summary == 'Create Purchase Order'
                and activity.res_model == 'purchase.request'
            ):
                sibling_activities = self.env['mail.activity'].search([
                    ('res_model', '=', 'purchase.request'),
                    ('res_id', '=', activity.res_id),
                    ('summary', '=', 'Create Purchase Order'),
                    ('id', '!=', activity.id),
                ])

                # CANCEL siblings instead of marking them done
                sibling_activities.unlink()

        # Mark only the current activity as done (original behaviour)
        return super().action_feedback(feedback=feedback, attachment_ids=attachment_ids)