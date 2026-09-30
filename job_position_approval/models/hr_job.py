# -*- coding: utf-8 -*-
from odoo import api, fields, models, _
from odoo.exceptions import UserError
from markupsafe import Markup

APPROVAL_ACTIVITY_SUMMARY = _("Job Position Approval")
UNPUBLISH_ACTIVITY_SUMMARY = _("Unpublish Job Position Request")


class HrJob(models.Model):
    _inherit = 'hr.job'

    approval_state = fields.Selection(
        [
            ('draft', 'Draft'),
            ('submitted', 'Submitted'),
            ('approved', 'Approved'),
            ('closed', 'Closed'),
            ('cancel', 'Cancelled'),
        ],
        string="Approval Status",
        default='draft',
        tracking=True,
        copy=False,
        help="Publish approval workflow status of this Job Position.",
    )
    rejection_reason = fields.Text(string="Rejection Reason", copy=False)
    is_current_user_approver = fields.Boolean(
        string="Current User Is Approver",
        compute='_compute_is_current_user_approver',
    )

    @api.depends_context('uid')
    def _compute_is_current_user_approver(self):
        is_approver = self.env.user.job_position_approver
        for job in self:
            job.is_current_user_approver = is_approver

    # ---------------------------------------------------------
    # Helpers
    # ---------------------------------------------------------
    def _get_approver_users(self):
        return self.env['res.users'].sudo().search([('job_position_approver', '=', True)])

    def _close_activities(self, summary, feedback):
        activities = self.env['mail.activity'].sudo().search([
            ('res_model', '=', 'hr.job'), ('res_id', 'in', self.ids), ('summary', '=', summary),])
        if activities:
            activities.action_feedback(feedback=feedback)


    def _send_approval_email(self, approved):
        template_xmlid = (
            'job_position_approval.email_template_job_approved'
            if approved else
            'job_position_approval.email_template_job_rejected')
        
        template = self.env.ref(template_xmlid, raise_if_not_found=False)
        
        if not template:
            return

        for job in self:
            partner = job.user_id.partner_id
            if not partner:
                continue
            template.send_mail( job.id,
                force_send=True, email_layout_xmlid='mail.mail_notification_light',
                email_values={
                    'recipient_ids': [(6, 0, partner.ids)], 'email_to': False,  # avoid double-sending via a raw email_to as well
                },
            )

    # ---------------------------------------------------------
    # Workflow actions
    # ---------------------------------------------------------
    def action_submit_for_approval(self):
        approvers = self._get_approver_users()
        if not approvers:
            raise UserError(_(
                "No Job Position Approver is configured. Please ask an administrator "
                "to enable 'Job Position Approver' on at least one user "
                "(Settings > Users & Companies > Users)."
            ))
        for job in self:
            if job.approval_state != 'draft':
                raise UserError(_("Only Job Positions in Draft state can be submitted for approval."))
            job.approval_state = 'submitted'
            job.rejection_reason = False
            for approver in approvers:
                job.activity_schedule(
                    activity_type_id=self.env.ref('mail.mail_activity_data_todo').id,
                    summary=APPROVAL_ACTIVITY_SUMMARY,
                    note=_("%(user)s submitted the Job Position <b>%(job)s</b> for your approval.") % {
                        'user': self.env.user.name, 'job': job.name,
                    },
                    user_id=approver.id,
                )
            job.message_post(
                body=Markup(_("Job Position <b>Submitted</b> for approval by %s.")) % self.env.user.name,
                partner_ids=approvers.mapped('partner_id').ids,
            )

    def action_approve(self):
        if not self.env.user.job_position_approver:
            raise UserError(_("Only a Job Position Approver can approve a Job Position."))
        for job in self:
            if job.approval_state != 'submitted':
                raise UserError(_("Only Submitted Job Positions can be approved."))
            job.write({
                'approval_state': 'approved',
                'is_published': True,
            })
            job._close_activities(
                APPROVAL_ACTIVITY_SUMMARY,
                feedback=_("Approved by %s.") % self.env.user.name,
            )
            job._send_approval_email(approved=True)
            job.message_post(
                body=Markup(_("Job Position <b>Approved</b> and published by %s.")) % self.env.user.name,
                partner_ids=job.user_id.partner_id.ids if job.user_id else [],
            )
            
    def action_reject(self):
        if not self.env.user.job_position_approver:
            raise UserError(_("Only a Job Position Approver can reject a Job Position."))
        for job in self:
            if job.approval_state != 'submitted':
                raise UserError(_("Only Submitted Job Positions can be rejected."))
            job.write({
                'approval_state': 'draft',
                'is_published': False,
            })
            job._close_activities(
                APPROVAL_ACTIVITY_SUMMARY,
                feedback=_("Rejected by %s.") % self.env.user.name,
            )
            job._send_approval_email(approved=False)
            job.message_post(
                body=Markup(_("Job Position <b>Rejected</b> by %s. It has been reset to Draft.")) % self.env.user.name,
                partner_ids=job.user_id.partner_id.ids if job.user_id else [],
            )
    

    def action_request_unpublish(self):
        """Used by the Recruitment User once the position is filled: posts a
        log note to the Approver(s) and schedules a follow-up activity so the
        Admin knows to close/unpublish the position."""
        approvers = self._get_approver_users()
        for job in self:
            if job.approval_state != 'approved':
                raise UserError(_("Only Approved (Published) Job Positions can be requested for unpublishing."))
            job.message_post(
                body=Markup(_("%(user)s reports that the position <b>%(job)s</b> has been filled. "
                    "Requesting Admin to close/unpublish this Job Position."
                )) % {'user': self.env.user.name, 'job': job.name},
                partner_ids=approvers.mapped('partner_id').ids,
            )
            for approver in approvers:
                job.activity_schedule(
                    activity_type_id=self.env.ref('mail.mail_activity_data_todo').id,
                    summary=UNPUBLISH_ACTIVITY_SUMMARY,
                    note=Markup(_("Position filled — please close/unpublish Job Position <b>%s</b>.")) % job.name,
                    user_id=approver.id,
                )

    def action_close_unpublish(self):
        if not self.env.user.job_position_approver:
            raise UserError(_("Only a Job Position Approver can close/unpublish a Job Position."))
        for job in self:
            if job.approval_state != 'approved':
                raise UserError(_("Only Approved (Published) Job Positions can be closed/unpublished."))
            job.write({
                'approval_state': 'closed',
                'is_published': False,  # single flag drives visibility everywhere (website, careers page, etc.)
            })
            job._close_activities(
                UNPUBLISH_ACTIVITY_SUMMARY,
                feedback=_("Closed/Unpublished by %s.") % self.env.user.name,
            )
            job.message_post(body=Markup(_("Job Position <b>Closed</b> and unpublished by %s.")) % self.env.user.name)

    def action_cancel(self):
        for job in self:
            job.approval_state = 'cancel'
            job.is_published = False
            job._close_activities(APPROVAL_ACTIVITY_SUMMARY, feedback=_("Cancelled by %s.") % self.env.user.name)
            job._close_activities(UNPUBLISH_ACTIVITY_SUMMARY, feedback=_("Cancelled by %s.") % self.env.user.name)
            job.message_post(body=Markup(_("Job Position <b>Cancelled</b> by %s.")) % self.env.user.name)

    def action_reset_to_draft(self):
        for job in self:
            job.write({'approval_state': 'draft', 'is_published': False})
            job.message_post(body=Markup(_("Job Position <b>Reset to Draft</b> by %s.")) % self.env.user.name)

    # ---------------------------------------------------------
    # Enforce archive restriction (cog menu "Archive" included)
    # ---------------------------------------------------------
    def write(self, vals):
        if 'active' in vals and not vals['active']:
            if not self.env.user.job_position_approver and not self.env.su:
                raise UserError(_("Only a Job Position Approver can archive a Job Position."))
            if not self.env.su:
                for job in self:
                    if job.approval_state not in ('closed', 'cancel'):
                        raise UserError(_(
                            "A Job Position can only be archived once it is Closed or Cancelled."
                        ))
        return super().write(vals)
