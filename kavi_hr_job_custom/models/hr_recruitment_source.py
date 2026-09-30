# -*- coding: utf-8 -*-
from odoo import _, api, fields, models
from odoo.exceptions import UserError


class HrRecruitmentSource(models.Model):
    """Makes the standard "Trackers" tab (hr.recruitment.source) Email
    column respect THIS Job Position's own "Email Alias" field
    (hr.job.alias_name, Details tab) instead of only checking whether
    the company has *some* alias domain configured somewhere.

    Core Odoo's Email column is a clickable RecruitmentCopyClipboardChar
    widget (see hr_recruitment/views/hr_recruitment_source_views.xml,
    field "email") whose visibility is `invisible="not has_domain"`.
    Core `_compute_has_domain()` sets that flag from
    `job_id.company_id.alias_domain_id or self.env.company.alias_domain_id`
    - a COMPANY-level setting that exists independently of whether this
    specific Job Position's Email Alias field has ever been filled in.
    That's why the Email link/button was showing up (and, if clicked,
    silently creating a real forwarding alias - core `create_alias()`
    falls back to the Job's plain `name` as the alias prefix when
    `alias_name` is empty) on Job Positions with a completely blank
    Email Alias field, as long as the company had an alias domain
    configured at all - i.e. an Email Tracker appearing with no Email
    Alias entered, which is the exact bug reported: the Email column
    must be empty/hidden until an Email Alias is actually typed into
    the Job Position's Details tab.

    Applies regardless of whether an alias was already generated for
    this row in the past (`alias_id` already set): if the Job's Email
    Alias field is empty right now, the column stays hidden either way
    - this only controls the column's visibility, it does not delete
    any alias/record that may already exist.
    """
    _inherit = 'hr.recruitment.source'

    @api.depends('job_id.alias_name')
    def _compute_has_domain(self):
        super()._compute_has_domain()
        for source in self:
            if source.job_id and not source.job_id.alias_name:
                source.has_domain = False



    kavi_email_address = fields.Char(
        string='Email',
        compute='_compute_kavi_email_tracking',
        store=True,
        readonly=True,
        help='The same Email address shown in the Vendors tab, built from '
             'the Job Position Email Alias and Source (<alias>+<source>@<domain>).',
    )

    kavi_email_url = fields.Char(
        string='Email Link',
        compute='_compute_kavi_email_tracking',
        store=True,
        readonly=True,
        help='The same mailto Email link shown in the Vendors tab.',
    )

    @api.depends(
        'job_id.name',
        'job_id.alias_name',
        'job_id.alias_full_name',
        'job_id.alias_domain_id',
        'job_id.company_id',
        'source_id.name',
    )
    def _compute_kavi_email_tracking(self):
        """Expose the exact same Email data used by the Vendors tab.

        Both surfaces use the same source-specific Email builder.
        """
        for source in self:
            source.kavi_email_address = False
            source.kavi_email_url = False

            if not source.job_id:
                continue

            source.kavi_email_address = source.job_id._kavi_build_job_email_address(source.source_id)
            source.kavi_email_url = source.job_id._kavi_build_email_link(source.source_id)

    def create_alias(self):
        
        blocked = self.filtered(lambda s: s.job_id and not s.job_id.alias_name)
        if blocked:
            raise UserError(_(
                'Cannot generate an Email Tracker for "%s": this Job '
                'Position has no Email Alias configured yet (Details '
                'tab). Set an Email Alias first, then try again.'
            ) % blocked[0].job_id.name)
        return super().create_alias()
