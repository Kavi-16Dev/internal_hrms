from odoo import models, fields, api
from odoo.exceptions import UserError, ValidationError
from datetime import timedelta

class MailActivityInherit(models.Model):
    _inherit = 'mail.activity'

    # def action_feedback(self, feedback=False, attachment_ids=None):
    #     print("action_feedback called")
    #     print("\n"*5)
    #     """
    #     Override action_feedback (Mark as Done).
    #     When a 'PO Returned:' or 'Approval Required:' activity is marked as done,
    #     cancel the same activity for all other users on the same PO.
    #     """
    #     for activity in self:
    #         if (
    #             activity.res_model == 'purchase.order'
    #             and activity.activity_type_id == self.env.ref('mail.mail_activity_data_todo')
    #             and activity.summary
    #             and (
    #                 activity.summary.startswith('PO Returned:')
    #                 or activity.summary.startswith('Approval Required:') 
    #                 or activity.summary.startswith('PO Recommendation Required:')
    #             )
    #         ):
    #             # Find sibling activities on the same PO with the same summary
    #             sibling_activities = self.env['mail.activity'].search([
    #                 ('res_model', '=', 'purchase.order'),
    #                 ('res_id', '=', activity.res_id),
    #                 ('summary', '=', activity.summary),
    #                 ('user_id', '!=', self.env.uid),
    #                 ('id', '!=', activity.id),
    #             ])
    #             if sibling_activities:
    #                 sibling_activities.unlink()

    #     return super().action_feedback(feedback=feedback, attachment_ids=attachment_ids)


    def action_feedback(self, feedback=False, attachment_ids=None):
        """
        Override action_feedback (Mark as Done).
        - Clears the activity's `note` before completion so the chatter's
        "Original note" section never renders (regardless of source).
        - When a 'PO Returned:' or 'Approval Required:' activity is marked as
        done, cancel the same activity for all other users on the same PO.
        """
        for activity in self:
            if (
                activity.res_model == 'purchase.order'
                and activity.activity_type_id == self.env.ref('mail.mail_activity_data_todo')
                and activity.summary
                and (
                    activity.summary.startswith('PO Returned:')
                    or activity.summary.startswith('Approval Required:')
                    or activity.summary.startswith('PO Recommendation Required:')
                )
            ):
                # Wipe the note so the "Original note" block is skipped entirely
                if activity.note:
                    activity.write({'note': False})

                # Find sibling activities on the same PO with the same summary
                sibling_activities = self.env['mail.activity'].search([
                    ('res_model', '=', 'purchase.order'),
                    ('res_id', '=', activity.res_id),
                    ('summary', '=', activity.summary),
                    ('user_id', '!=', self.env.uid),
                    ('id', '!=', activity.id),
                ])
                if sibling_activities:
                    sibling_activities.unlink()

        return super().action_feedback(feedback=feedback, attachment_ids=attachment_ids)