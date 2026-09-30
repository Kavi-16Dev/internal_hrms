# -*- coding: utf-8 -*-
import re

from odoo import _, api, fields, models


class HrJobVendorTrackerLink(models.Model):
    """Stores the auto-generated Tracker Link created whenever a Vendor
    is added to a Job Position. Exactly ONE row is auto-generated per
    (Job, Vendor) pair - see hr.job._create_vendor_tracker_links() -
    carrying the public Job Page tracker `url`.

    That row's `email_url` is the canonical Email mailto link on the SAME
    row, not a second row. It is generated from the Job Position's Email
    Email Alias + Source name and matches the standard Trackers tab.

    The Vendors tab list view additionally allows adding/editing rows
    directly (editable="bottom", "Add a line") - see
    _onchange_vendor_link_type() below, which is what fills in `url` for
    those manually-added rows so the required field is never left blank.
    Manually-added rows are the ONLY way more than one row per (Job,
    Vendor) can ever appear under "Link Type" - the automatic path never
    creates a second row for a Vendor that already has one (see
    hr.job._create_vendor_tracker_links()).
    """
    _name = 'hr.job.vendor.tracker.link'
    _description = 'Job / Vendor Tracker Link'
    _rec_name = 'url'
    _order = 'create_date desc'

    LINK_TYPE_SELECTION = [
        ('job_page', 'Job Page'),
        ('email', 'Email'),
    ]

    job_id = fields.Many2one('hr.job', string='Job Position', required=True, ondelete='cascade')
    vendor_id = fields.Many2one('hr.recruitment.vendor', string='Vendor', required=True, ondelete='cascade')
    source_id = fields.Many2one('utm.source', related='vendor_id.source_id', string='Source', store=True)
    link_type = fields.Selection(
        LINK_TYPE_SELECTION,
        string='Link Type',
        required=True,
        default='job_page',
        help='Which channel this Tracker Link is meant for. Only relevant '
             'for rows added manually ("Add a line") - the single row '
             'auto-generated when a Vendor is added is always Job Page; '
             'its Email Tracker link lives in the Email Tracker column '
             'instead of a second Link Type row.',
    )
    url = fields.Char(string='Tracker Link', required=True)
    email_url = fields.Char(
        string='Email Link',
        compute='_compute_email_url',
        store=True,
        help='Canonical mailto link built from the Job Position Email Alias '
             'and the Vendor Source (<alias>+<source>@<domain>).',
    )
    email_address = fields.Char(
        string='Email',
        compute='_compute_email_address',
        store=True,
        readonly=True,
        help='Generated email address built from the Job Position Email Alias '
             'and Vendor Source (<alias>+<source>@<domain>).',
    )
    email_sent = fields.Boolean(string='Email Sent', default=False)
    active = fields.Boolean(default=True)

    
    @api.depends(
        'job_id.name',
        'job_id.alias_name',
        'job_id.alias_full_name',
        'job_id.alias_domain_id',
        'job_id.company_id',
        'vendor_id.source_id',
        'vendor_id.source_id.name',
    )
    def _compute_email_url(self):
        """Build the source-specific Email link used by both Email columns."""
        for rec in self:
            rec.email_url = (
                rec.job_id._kavi_build_email_link(rec.vendor_id.source_id)
                if rec.job_id and rec.vendor_id.source_id
                else False
            )

    @api.depends(
        'job_id.name',
        'job_id.alias_name',
        'job_id.alias_full_name',
        'job_id.alias_domain_id',
        'job_id.company_id',
        'vendor_id.source_id',
        'vendor_id.source_id.name',
    )
    def _compute_email_address(self):
        """Build the source-specific Email address.

        Format: <Email Alias>+<Source>@<Email Alias Domain>.
        """
        for rec in self:
            rec.email_address = (
                rec.job_id._kavi_build_job_email_address(rec.vendor_id.source_id)
                if rec.job_id and rec.vendor_id.source_id
                else False
            )

    _job_vendor_link_type_uniq = models.Constraint(
        'UNIQUE(job_id, vendor_id, link_type)',
        'A tracker link of this type already exists for this Vendor on this Job Position.',
    )

    
    @api.onchange('job_id', 'vendor_id', 'link_type')
    def _onchange_vendor_link_type(self):
        for rec in self:
            if not (rec.job_id and rec.vendor_id and rec.link_type):
                continue

            duplicate = self.env['hr.job.vendor.tracker.link'].search([
                ('id', '!=', rec.id.origin if rec.id else False),
                ('job_id', '=', rec.job_id.id),
                ('vendor_id', '=', rec.vendor_id.id),
                ('link_type', '=', rec.link_type),
            ], limit=1)
            if duplicate:
                rec.url = False
                return {
                    'warning': {
                        'title': _('Tracker Link already exists'),
                        'message': _(
                            'A %(link_type)s Tracker Link already exists for vendor '
                            '"%(vendor)s" on this Job Position. Pick a different Vendor '
                            'or Link Type, or edit the existing row instead.'
                        ) % {
                            'link_type': dict(self.LINK_TYPE_SELECTION).get(rec.link_type, rec.link_type),
                            'vendor': rec.vendor_id.name,
                        },
                    }
                }

            if not rec.vendor_id.source_id:
                rec.url = False
                return {
                    'warning': {
                        'title': _('Vendor has no Source'),
                        'message': _(
                            'Vendor "%s" has no Source configured, so a Tracker Link URL '
                            'cannot be built for it. Set a Source on the Vendor first.'
                        ) % rec.vendor_id.name,
                    }
                }

            if rec.link_type == 'email' and not rec.job_id._kavi_has_job_email_alias():
                rec.url = False
                rec.link_type = 'job_page'
                return {
                    'warning': {
                        'title': _('Job Position has no Email Alias'),
                        'message': _(
                            'This Job Position has no Email Alias configured (Details tab), '
                            'so there is no vendor email to send and an Email Tracker Link '
                            'cannot be created. Set an Email Alias on the Job Position first, '
                            'or use the Job Page link type instead.'
                        ),
                    }
                }

            rec.url = rec.job_id._build_tracker_url(rec.vendor_id, rec.link_type)

    def unlink(self):
        vendor_pairs = {(link.job_id.id, link.vendor_id.id)
                          for link in self if link.job_id and link.vendor_id}
        source_pairs = {(link.job_id.id, link.source_id.id)
                          for link in self if link.job_id and link.source_id}
        res = super().unlink()
        self._kavi_cleanup_stale_vendor_ids(vendor_pairs)
        self._kavi_cleanup_orphaned_recruitment_sources(source_pairs)
        return res

    def _kavi_cleanup_stale_vendor_ids(self, pairs):
        """Keep the legacy primary Vendor pointer valid after unlink.

        Removing one Vendor must not clear the Job Position's Vendor pointer
        when other Vendors are still assigned through the Vendors tab.
        In that case the first remaining Vendor becomes the primary pointer.
        """
        for job_id, vendor_id in pairs:
            remaining_pair = self.search([
                ('job_id', '=', job_id),
                ('vendor_id', '=', vendor_id),
            ], limit=1)
            if remaining_pair:
                continue

            job = self.env['hr.job'].browse(job_id).exists()
            if not job or job.sudo().vendor_id.id != vendor_id:
                continue

            remaining_link = self.search([
                ('job_id', '=', job_id),
                ('vendor_id', '!=', False),
            ], order='id asc', limit=1)

            job.sudo().write({
                'vendor_id': remaining_link.vendor_id.id if remaining_link else False,
            })

    def _kavi_cleanup_orphaned_recruitment_sources(self, pairs):
        """Delete the mirrored hr.recruitment.source ("Trackers" tab) row
        for every (job, source) pair that no longer has ANY Vendor
        Tracker Link pointing at it - the exact counterpart of
        _sync_recruitment_source_tracker() below, which creates that row
        the moment a link is added. Only ever deletes rows this module's
        own sync created (matched by job_id + source_id, same lookup
        _sync_recruitment_source_tracker() uses); a Tracker row a
        recruiter added directly on the Trackers tab for a Source that
        happens to coincide with a vendor's Source is indistinguishable
        from one we created, so it is removed too once no Vendor Tracker
        Link justifies it any more - Vendors and Trackers are meant to
        always describe the same thing for that pair.
        """
        RecruitmentSource = self.env['hr.recruitment.source'].sudo()
        for job_id, source_id in pairs:
            remaining = self.search([
                ('job_id', '=', job_id),
                ('source_id', '=', source_id),
            ], limit=1)
            if remaining:
                continue
            RecruitmentSource.search([
                ('job_id', '=', job_id),
                ('source_id', '=', source_id),
            ]).unlink()

   
    @api.model_create_multi
    def create(self, vals_list):
       
        for vals in vals_list:
            job_id = vals.get('job_id')
            vendor_id = vals.get('vendor_id')
            link_type = vals.get('link_type')
            if not (job_id and vendor_id and link_type):
                continue
            job = self.env['hr.job'].browse(job_id)
            vendor = self.env['hr.recruitment.vendor'].browse(vendor_id)
            if job.exists() and vendor.exists() and vendor.source_id:
                vals['url'] = job._build_tracker_url(vendor, link_type)

        links = super().create(vals_list)
        links._sync_recruitment_source_tracker()
        links._sync_job_vendor_ids()
        return links

    def write(self, vals):
        
        old_vendor_pairs = set()
        old_source_pairs = set()
        if 'vendor_id' in vals or 'job_id' in vals:
            old_vendor_pairs = {(link.job_id.id, link.vendor_id.id)
                                  for link in self if link.job_id and link.vendor_id}
            old_source_pairs = {(link.job_id.id, link.source_id.id)
                                  for link in self if link.job_id and link.source_id}

        res = super().write(vals)
        if 'vendor_id' in vals or 'job_id' in vals:
            self._refresh_tracker_urls()
            self._sync_recruitment_source_tracker()
            self._sync_job_vendor_ids()

            new_vendor_pairs = {(link.job_id.id, link.vendor_id.id)
                                  for link in self if link.job_id and link.vendor_id}
            new_source_pairs = {(link.job_id.id, link.source_id.id)
                                  for link in self if link.job_id and link.source_id}
            self._kavi_cleanup_stale_vendor_ids(old_vendor_pairs - new_vendor_pairs)
            self._kavi_cleanup_orphaned_recruitment_sources(old_source_pairs - new_source_pairs)
        return res

    def _refresh_tracker_urls(self):
        """Keep stored Tracker Link values identical to the URL that
        Odoo's standard Recruitment > Trackers row currently exposes.

        This is intentionally called after a link's Job/Vendor changes and
        from the Job/Vendor models when the public Job URL or Vendor Source
        changes, so the two tabs never show different URLs for the same
        source.
        """
        for link in self:  # noqa: B007 - each row needs its own Job/Vendor
            if not link.job_id or not link.vendor_id or not link.vendor_id.source_id:
                continue
            new_url = link.job_id._build_tracker_url(link.vendor_id, link.link_type)
            if link.url != new_url:
                link.with_context(kavi_skip_tracker_url_sync=True).write({'url': new_url})

   
    def _sync_job_vendor_ids(self):
        """Keep the legacy ``hr.job.vendor_id`` pointer synchronized.

        A Job Position is allowed to have multiple Vendors. The actual
        relationship is represented by ``tracker_link_ids`` (one or more
        rows per Job/Vendor), while ``hr.job.vendor_id`` is retained only
        as a backward-compatible primary Vendor pointer for older code and
        integrations.

        The previous implementation raised ValidationError whenever a
        second Vendor was added. That was the root cause of the Validation
        Error shown in the Vendors tab. The method now:
          * keeps the existing primary Vendor when it is still linked;
          * assigns the first linked Vendor as primary when the pointer is
            empty or stale;
          * never rejects a second or subsequent Vendor.
        """
        jobs = self.mapped('job_id').filtered(bool)
        for job in jobs:
            linked_vendor = self.search([
                ('job_id', '=', job.id),
                ('vendor_id', '!=', False),
            ], order='id asc', limit=1).vendor_id

            if not linked_vendor:
                if job.vendor_id:
                    job.sudo().write({'vendor_id': False})
                continue

            current_is_linked = bool(self.search([
                ('job_id', '=', job.id),
                ('vendor_id', '=', job.vendor_id.id),
            ], limit=1)) if job.vendor_id else False

            if not current_is_linked:
                job.sudo().write({'vendor_id': linked_vendor.id})

    def _sync_recruitment_source_tracker(self):
        """Ensure each Vendor Tracker Link has a matching entry on the
        standard "Trackers" tab (hr.recruitment.source) for the same
        Job Position and the same Source (vendor_id.source_id).

        Uses sudo() because the Vendors tab is available to groups
        (e.g. kavi_hr_job_custom.group_hr_recruitment_hiring_manager)
        that are not necessarily granted create rights on
        hr.recruitment.source itself; the sync is a system-triggered
        side effect of an already-authorized Vendor Tracker Link
        creation, not a new user-facing write.
        """
        RecruitmentSource = self.env['hr.recruitment.source'].sudo()
        website_medium = self.env['utm.medium'].sudo()._fetch_or_create_utm_medium('website')
        job_campaign = self.env.ref('hr_recruitment.utm_campaign_job', raise_if_not_found=False)

        for link in self:
            if not link.job_id or not link.vendor_id.source_id:
                # No Source on the Vendor -> nothing to mirror; same
                # guard used by hr.job._create_vendor_tracker_links().
                continue

            existing = RecruitmentSource.search([
                ('job_id', '=', link.job_id.id),
                ('source_id', '=', link.vendor_id.source_id.id),
            ], limit=1)
            if existing:
                continue

            RecruitmentSource.create({
                'job_id': link.job_id.id,
                'source_id': link.vendor_id.source_id.id,
                'medium_id': website_medium.id,
                'campaign_id': job_campaign.id if job_campaign else False,
            })