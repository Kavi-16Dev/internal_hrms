# -*- coding: utf-8 -*-
import logging
import re

from markupsafe import Markup
from odoo import fields, models, api, _
from odoo.addons.html_editor.tools import handle_history_divergence
from odoo.exceptions import AccessError
from odoo.tools import urls
from urllib.parse import urlencode

_logger = logging.getLogger(__name__)


class HrJob(models.Model):
    _inherit = ['hr.job', 'mail.thread', 'mail.activity.mixin', 'html.field.history.mixin']

   
    def _get_versioned_fields(self):
        return ['budgeting_information', 'key_responsibilities']

    website_published = fields.Boolean()

   
    budgeting_information = fields.Html(
        string='Budgeting Information', sanitize=True, default='',
        groups='hr_recruitment.group_hr_recruitment_user,'
               'hr_recruitment.group_hr_recruitment_manager,'
               'kavi_hr_job_custom.group_hr_recruitment_hiring_manager',)

    
    key_responsibilities = fields.Html(
        string='Key Roles and Responsibilities', sanitize=True, default='',
        groups='hr_recruitment.group_hr_recruitment_user,'
               'hr_recruitment.group_hr_recruitment_manager,'
               'kavi_hr_job_custom.group_hr_recruitment_hiring_manager',)

    
    work_mode = fields.Selection(
        selection=[
            ('hybrid', 'Hybrid'),
            ('onsite', 'Onsite'),
            ('office', 'Office'),
        ],
        string='Work Mode',
        tracking=True,
        groups='hr_recruitment.group_hr_recruitment_user,'
               'hr_recruitment.group_hr_recruitment_manager,'
               'kavi_hr_job_custom.group_hr_recruitment_hiring_manager',
    )

    job_board_ids = fields.Many2many(
        'hr.job.board',
        'hr_job_job_board_rel',
        'job_id', 'job_board_id',
        string='Job Boards',
        groups='hr_recruitment.group_hr_recruitment_user,'
               'hr_recruitment.group_hr_recruitment_manager',
    )

    def _compute_document_ids(self):
        """Compute recruitment documents without crossing restricted
        Applicant field permissions.

        Odoo's stock ``hr.job._compute_document_ids`` filters the Job's
        ``application_ids`` on ``employee_id``.  Some ATS customizations
        restrict ``hr.applicant.employee_id`` to recruitment users, while
        Odoo intentionally allows Interviewers to open Job Positions.
        Reading ``employee_id`` with the Interviewer's environment therefore
        raises an AccessError/RPC_ERROR while simply opening ``hr.job``.

        Interviewers are already authorized to see the Job's applications.
        The ``employee_id`` check is only an internal implementation detail
        used to exclude hired applicants from the attachment aggregation, so
        perform that internal read in sudo and keep the resulting attachment
        access in the current user's environment.  This does not grant the
        Interviewer access to ``employee_id`` or any restricted Applicant
        field.
        """
        applicants = self.mapped('application_ids').sudo().filtered(
            lambda applicant: not applicant.employee_id
        )
        app_to_job = {applicant.id: applicant.job_id.id for applicant in applicants}
        attachments = self.env['ir.attachment'].search([
            '|',
            '&', ('res_model', '=', 'hr.job'), ('res_id', 'in', self.ids),
            '&', ('res_model', '=', 'hr.applicant'), ('res_id', 'in', applicants.ids),
        ])
        result = dict.fromkeys(self.ids, self.env['ir.attachment'])
        for attachment in attachments:
            if attachment.res_model == 'hr.applicant':
                job_id = app_to_job.get(attachment.res_id)
                if job_id in result:
                    result[job_id] |= attachment
            else:
                result[attachment.res_id] |= attachment
        for job in self:
            job.document_ids = result.get(job.id, False)
            job.documents_count = len(job.document_ids)

    vendor_id = fields.Many2one(
        'hr.recruitment.vendor',
        string='Primary Vendor',
        ondelete='set null',
        index=True,
        groups='hr_recruitment.group_hr_recruitment_user,'
               'hr_recruitment.group_hr_recruitment_manager',
        help='Legacy primary Vendor field kept for backward compatibility. '
             'A Job Position can have multiple Vendors; the Vendors tab '
             '(tracker_link_ids) is the source of truth for all Vendor assignments. '
             'This field points to the first/primary Vendor when one exists.',
    )

    # Backward-compatible vendor relation used by older portal customizations.
    # Vendor assignments are stored through tracker_link_ids; this computed
    # field keeps domains such as ('vendor_ids', 'in', vendor_id) working.
    vendor_ids = fields.Many2many(
        'hr.recruitment.vendor',
        string='Vendors',
        compute='_compute_vendor_ids',
        search='_search_vendor_ids',
        help='Compatibility field. Vendor assignments are sourced from Vendor Tracker Links.',
    )

    @api.depends('vendor_id', 'tracker_link_ids.vendor_id')
    def _compute_vendor_ids(self):
        # sudo() here for the same reason as res.partner's write() override:
        # `vendor_ids` itself carries no `groups=` restriction, so any user
        # who can read/search hr.job (e.g. an Interviewer, or a portal
        # domain evaluation) forces this compute to run. tracker_link_ids
        # IS restricted (groups='hr_recruitment.group_hr_recruitment_user,
        # hr_recruitment.group_hr_recruitment_manager') and
        # hr.job.vendor.tracker.link's ir.model.access.csv only grants read
        # to Recruitment User/Manager + Portal - so without sudo() this
        # raises the same "not allowed to access" AccessError for any other
        # user/context that merely triggers this compute.
        for job in self:
            vendors = job.sudo().tracker_link_ids.mapped('vendor_id')
            if job.vendor_id:
                vendors |= job.vendor_id
            job.vendor_ids = vendors

    def _search_vendor_ids(self, operator, value):
        if operator in ('=', '!=') and value is False:
            linked = self.env['hr.job.vendor.tracker.link'].sudo().search([
                ('vendor_id', '!=', False)
            ]).mapped('job_id').ids
            domain = [('id', 'not in' if operator == '=' else 'in', linked)]
            return domain
        return ['|', ('vendor_id', operator, value),
                ('tracker_link_ids.vendor_id', operator, value)]

    tracker_link_ids = fields.One2many(
        'hr.job.vendor.tracker.link', 'job_id',
        string='Vendor Tracker Links',
        groups='hr_recruitment.group_hr_recruitment_user,'
               'hr_recruitment.group_hr_recruitment_manager',
    )

    hiring_manager_ids = fields.Many2many(
        'res.users',
        'hr_job_hiring_manager_rel',
        'job_id', 'user_id',
        string='Hiring Manager',
        groups='hr_recruitment.group_hr_recruitment_user,'
               'hr_recruitment.group_hr_recruitment_manager,'
               'hr_recruitment.group_hr_recruitment_interviewer',
    )

   
    _KAVI_HTML_TRACKED_FIELDS_FALLBACK = {
        'budgeting_information': 'Budgeting Information',
        'key_responsibilities': 'Key Roles and Responsibilities',
    }

    def _get_kavi_tracked_fields(self):
        tracked = self.env['hr.job.tracked.field']._get_tracked_fields_map()
        return tracked or self._KAVI_HTML_TRACKED_FIELDS_FALLBACK

  
    _KAVI_SELECTION_TRACKED_FIELDS = {
        'work_mode': 'Work Mode',
    }

   
    _KAVI_ALSO_LOG_TO_CHATTER = False

    job_version_history_ids = fields.One2many(
        'hr.job.version.history', 'job_id', string='Version History',
    )
    job_version_history_count = fields.Integer(
        string='Version History Count',
        compute='_compute_job_version_history_count',
    )

    def _compute_job_version_history_count(self):
        counts = self.env['hr.job.version.history']._read_group(
            [('job_id', 'in', self.ids)], ['job_id'], ['__count'],
        )
        count_by_job = {job.id: count for job, count in counts}
        for job in self:
            job.job_version_history_count = count_by_job.get(job.id, 0)

    def action_open_job_version_history(self):
        """Clicking 'Version History' now opens the popup wizard (see
        models/hr_job_version_history_wizard.py / views/
        hr_job_version_history_wizard_views.xml) as a dialog
        (target='new'), matching the reference UI: a timeline of past
        versions on the left, the selected version's content on the
        right, a 'View comparison' toggle, and Restore/Discard buttons.
        """
        self.ensure_one()

        has_history = bool(self.env['hr.job.version.history'].search_count(
            [('job_id', '=', self.id)],
        ))
        if not has_history:
            return {
                'type': 'ir.actions.client',
                'tag': 'display_notification',
                'params': {
                    'title': _('No Version History Yet'),
                    'message': _(
                        'No tracked changes have been saved for this Job '
                        'Position yet. Edit Budgeting Information (or another '
                        'tracked field) and save the record, then try again.'
                    ),
                    'type': 'info',
                    'sticky': False,
                },
            }

        wizard_form = self.env.ref('kavi_hr_job_custom.view_kavi_job_version_history_wizard_form')
        return {
            'type': 'ir.actions.act_window',
            'name': _('Version History'),
            'res_model': 'hr.job.version.history.wizard',
            'view_mode': 'form',
            'views': [(wizard_form.id, 'form')],
            'target': 'new',
            'context': {'default_job_id': self.id},
        }


    
    _KAVI_NATIVE_HISTORY_FIELDS = ('budgeting_information', 'key_responsibilities')

   
    _KAVI_HTML_FIELD_INTERVIEWER_READONLY = ()

  
    _KAVI_HIDDEN_PAGE_STRINGS_FOR_INTERVIEWER = ('Offer Letter Components',)

    _KAVI_HTML_FIELD_EDIT_GROUPS = (
        'hr_recruitment.group_hr_recruitment_user',
        'hr_recruitment.group_hr_recruitment_manager',
        'kavi_hr_job_custom.group_hr_recruitment_hiring_manager',
    )

    def _kavi_user_is_interviewer_only(self):
        user = self.env.user
        if not user.has_group('hr_recruitment.group_hr_recruitment_interviewer'):
            return False
        return not any(user.has_group(g) for g in self._KAVI_HTML_FIELD_EDIT_GROUPS)

 
    def _kavi_reset_native_html_history(self, field_names):
        for job in self.sudo():
            metadata = dict(job.html_field_history_metadata or {})
            changed = False
            for fname in field_names:
                if metadata.pop(fname, None) is not None:
                    changed = True
            if changed:
                job.write({'html_field_history_metadata': metadata})

  
    def html_field_history_get_content_at_revision(self, *args, **kwargs):
        try:
            return super().html_field_history_get_content_at_revision(*args, **kwargs)
        except IndexError:
            field_name = args[0] if args else kwargs.get('field_name')
            self.ensure_one()
            _logger.warning(
                "kavi_hr_job_custom: stale html_field_history_metadata "
                "detected for hr.job id=%s field=%s while opening its "
                "native History dialog; clearing that field's stored "
                "history and falling back to its current content so "
                "the dialog opens cleanly instead of erroring.",
                self.id, field_name,
            )
            if field_name in self._KAVI_NATIVE_HISTORY_FIELDS:
                self._kavi_reset_native_html_history([field_name])
            if field_name and field_name in self._fields:
                return self[field_name] or ''
            return ''

    def write(self, vals):
       
        if not self.env.su and self._kavi_user_is_interviewer_only():
            locked_fields = [f for f in self._KAVI_HTML_FIELD_INTERVIEWER_READONLY if f in vals]
            if locked_fields:
                tracked_labels = self._get_kavi_tracked_fields()
                labels = ', '.join(
                    tracked_labels.get(f, f) for f in locked_fields
                )
                raise AccessError(_(
                    'Interviewers have view-only access to %s and cannot '
                    'edit it.'
                ) % labels)

       
        if len(self) == 1:
            for fname in self._KAVI_NATIVE_HISTORY_FIELDS:
                if fname in vals:
                    if not self[fname]:
                        super(HrJob, self).write({fname: ''})
                        self._kavi_reset_native_html_history([fname])
                    elif not (self.html_field_history_metadata or {}).get(fname):
                        self._kavi_reset_native_html_history([fname])
            for fname in self._KAVI_NATIVE_HISTORY_FIELDS:
                if fname in vals:
                    handle_history_divergence(self, fname, vals)

        tracked_fields = self._get_kavi_tracked_fields()
        selection_tracked_fields = self._KAVI_SELECTION_TRACKED_FIELDS
        changed_fields = [f for f in tracked_fields if f in vals]
        changed_selection_fields = [f for f in selection_tracked_fields if f in vals]

       
        sudo_self = self.sudo()

        old_values = {}
        if changed_fields or changed_selection_fields:
            for job in sudo_self:
                old_values[job.id] = {}
                for f in changed_fields:
                    old_values[job.id][f] = job[f] or ''
                for f in changed_selection_fields:
                   
                    old_values[job.id][f] = job[f]

        old_vendors = {
            job.id: job.vendor_id.id
            for job in self
        } if 'vendor_id' in vals else {}

        res = super().write(vals)

        if changed_fields or changed_selection_fields:
            subtype = self.env.ref(
                'kavi_hr_job_custom.mail_message_subtype_version_history',
                raise_if_not_found=False,
            )
            HistoryModel = self.env['hr.job.version.history'].sudo()
         
            for job in sudo_self:
               
                entries = []

                for fname in changed_fields:
                    old_val = old_values[job.id].get(fname, '')
                    new_val = job[fname] or ''
                    if old_val == new_val:
                        continue
                    entries.append((fname, tracked_fields[fname], old_val, new_val))

                for fname in changed_selection_fields:
                    old_key = old_values[job.id].get(fname)
                    new_key = job[fname]
                    if old_key == new_key:
                        continue
                    selection_map = dict(job._fields[fname].selection)
                    old_val = selection_map.get(old_key, old_key) or _('(empty)')
                    new_val = selection_map.get(new_key, new_key) or _('(empty)')
                    entries.append((fname, selection_tracked_fields[fname], old_val, new_val))

                for fname, label, old_val, new_val in entries:
                    
                    try:
                        HistoryModel.create({
                            'job_id': job.id,
                            'field_name': fname,
                            'field_label': label,
                            'old_value': old_val,
                            'new_value': new_val,
                        })
                    except Exception:
                        _logger.exception("kavi_hr_job_custom: failed to log version "
                            "history for hr.job id=%s field=%s", job.id, fname,)

                   
                    if self._KAVI_ALSO_LOG_TO_CHATTER:
                        body = Markup(
                            '<p><b>%s</b> was updated.</p>'
                            '<p><b>Previous value:</b></p><blockquote>%s</blockquote>'
                            '<p><b>New value:</b></p><blockquote>%s</blockquote>'
                        ) % (
                            label,
                            Markup(old_val) if old_val else _('(empty)'),
                            Markup(new_val) if new_val else _('(empty)'),
                        )
                        job.message_post(
                            body=body,
                            subtype_id=subtype.id if subtype else False,
                        )

        if 'vendor_id' in vals:
            # `vendor_id` is now only the legacy/primary Vendor pointer.
            # The Vendors tab supports multiple Vendor tracker rows. If a
            # user changes this legacy field, preserve the existing
            # multi-Vendor rows and only remove/recreate the row belonging
            # to the old primary Vendor.
            for job in self:
                new_vendor_id = job.vendor_id.id
                old_vendor_id = old_vendors.get(job.id)
                if old_vendor_id and old_vendor_id != new_vendor_id:
                    old_links = job.tracker_link_ids.filtered(
                        lambda link: link.vendor_id.id == old_vendor_id
                    )
                    if old_links:
                        old_links.unlink()
                if new_vendor_id and new_vendor_id != old_vendor_id:
                    job._create_vendor_tracker_links(job.vendor_id)

        if 'alias_name' in vals:
            # Email links are generated for every Vendor attached through
            # the Vendors tab, not only the legacy primary Vendor.
            for job in self:
                if job.tracker_link_ids:
                    job.tracker_link_ids._sync_recruitment_source_tracker()
                    job._kavi_send_pending_vendor_tracker_emails()

        if {'website_url', 'company_id'} & set(vals):
            for job in self:
                job.tracker_link_ids._refresh_tracker_urls()

        if 'job_board_ids' in vals:
            self._kavi_sync_applicant_job_board_source()

        return res

    def _kavi_sync_applicant_job_board_source(self):
        """Push Job Board -> Source auto-fill onto EXISTING Applicants
        whenever this Job Position's Job Boards change (e.g. a Job
        Board is added under the "Job Boards" tab after Applicants
        already exist).

        hr.applicant's own create()/write()/onchange hooks (see
        _kavi_get_job_board_source() in models/hr_applicant.py) only
        run when something changes ON the Applicant itself, so they
        never retroactively fill in Source for Applicants that already
        existed before a Job Board was added to their Job Position.
        This closes that gap the same way: only when the Job now has
        exactly ONE Job Board (still ambiguous otherwise - Source must
        be picked by hand in that case, restricted on the form to the
        Job's configured Job Boards), and only for Applicants that
        don't already have a Source (never overwrites a deliberate
        choice already made).
        """
        Applicant = self.env['hr.applicant'].sudo()
        for job in self:
            if len(job.job_board_ids) != 1:
                continue
            source = job.job_board_ids._get_or_create_utm_source()
            applicants = Applicant.search([
                ('job_id', '=', job.id),
                ('source_id', '=', False),
            ])
            if applicants:
                applicants.write({'source_id': source.id})

    @api.model_create_multi
    def create(self, vals_list):
        jobs = super().create(vals_list)

        
        HistoryModel = self.env['hr.job.version.history'].sudo()
        for job in jobs:
            try:
                HistoryModel.create({
                    'job_id': job.id,
                    'field_name': '__baseline__',
                    'field_label': _('Job Position Created'),
                    'old_value': '',
                    'new_value': job.name or '',
                })
            except Exception:
                _logger.exception(
                    "kavi_hr_job_custom: failed to create baseline "
                    "version history for new hr.job id=%s", job.id,
                )

        for job, vals in zip(jobs, vals_list):
            if vals.get('vendor_id'):
                job._create_vendor_tracker_links(job.vendor_id)
            if vals.get('job_board_ids'):
                job._kavi_sync_applicant_job_board_source()
        return jobs

    def _kavi_has_job_email_alias(self):
        """Whether this Job Position has a real, usable Email Alias
        configured (the "Email Alias" field shown on the Details tab -
        Field: alias_name, Model: hr.job, backed by mail.alias.mixin).

        Checks `alias_full_name` (the complete resolved address, e.g.
        "jobs@mycompany.com") first, and falls back to the raw
        `alias_name` (e.g. just "jobs") in case no alias domain is
        configured system-wide yet and the full address hasn't been
        computed - either one being set means the user has actually
        typed something into the Email Alias field.
        """
        self.ensure_one()
        return bool(self.alias_full_name or self.alias_name)

    def _kavi_get_alias_domain(self):
        """Best-effort resolution of the domain part of this Job
        Position's Email Alias.
        """
        self.ensure_one()
        alias_domain_id = getattr(self, 'alias_domain_id', False)
        if alias_domain_id:
            return alias_domain_id.name
        alias_domain = getattr(self, 'alias_domain', False)
        if alias_domain:
            return alias_domain
        if self.alias_full_name and '@' in self.alias_full_name:
            return self.alias_full_name.split('@', 1)[1]
        return False

    def _kavi_build_job_email_address(self, source=None):
        """Build the canonical Job Position email address for a source.

        Required format:
            <email-alias>+<source>@<alias-domain>

        The source is normally the ``utm.source`` record used by the Vendor.
        For example, with Email Alias ``jobs`` and Source ``priya`` the
        generated address is ``jobs+priya@example.com``.

        ``source`` may be an ``utm.source`` record, a source name string, or
        omitted for backward compatibility. When omitted, the method returns
        the base alias without a source suffix only when the caller explicitly
        needs it; the Vendor/Tracker email builders always pass their source.
        """
        self.ensure_one()

        if not self._kavi_has_job_email_alias():
            return False

        domain = self._kavi_get_alias_domain()
        if not domain:
            return False

        alias = self.alias_name or (
            self.alias_full_name.split('@', 1)[0]
            if self.alias_full_name and '@' in self.alias_full_name
            else False
        )
        if not alias:
            return False

        if hasattr(source, 'name'):
            source_name = source.name
        else:
            source_name = source

        if not source_name:
            return False

        safe_source = re.sub(
            r'[^A-Za-z0-9]+',
            '-',
            str(source_name).strip(),
        ).strip('-')
        if not safe_source:
            return False

        return '%s+%s@%s' % (
            alias.strip(),
            safe_source.lower(),
            domain.strip(),
        )

    def _kavi_build_email_link(self, source=None):
        """Return the clickable source-specific Email mailto link."""
        self.ensure_one()
        email_address = self._kavi_build_job_email_address(source)
        return 'mailto:%s' % email_address if email_address else False

    def _kavi_build_email_tracker_url(self, source=None):
        """Backward-compatible wrapper for the source-specific Email link."""
        self.ensure_one()
        return self._kavi_build_email_link(source)

    def _kavi_build_tracker_email(self, vendor):
        """Build the Vendor-specific email address from its Source."""
        self.ensure_one()
        return self._kavi_build_job_email_address(vendor.source_id if vendor else None)

    def _create_vendor_tracker_links(self, vendors):
        """Every Vendor added to this Job Position must have a Source
        (hr.recruitment.vendor.source_id) configured - that Source is
        what the Tracker Link's URL is built from. Vendors without one
        are skipped here; nothing is silently guessed on their behalf.
        """
        Link = self.env['hr.job.vendor.tracker.link']

        for vendor in vendors:
            if not vendor.source_id:
                continue

            existing = Link.search([
                ('job_id', '=', self.id),
                ('vendor_id', '=', vendor.id),
            ], limit=1)
            if existing:
                continue

            Link.create({
                'job_id': self.id,
                'vendor_id': vendor.id,
                'link_type': 'job_page',
                'url': self._build_tracker_url(vendor, 'job_page'),
            })

        self._kavi_send_pending_vendor_tracker_emails()

    def _kavi_send_pending_vendor_tracker_emails(self):
        """Email mail_template_vendor_tracker_link to every Vendor on
        this Job Position whose Tracker Link row has a usable Email
        Tracker link (`email_url`, populated once this Job Position has
        an Email Alias configured - see
        hr.job.vendor.tracker.link._compute_email_url()) that hasn't
        been sent yet.
        """
        self.ensure_one()
        template = self.env.ref(
            'kavi_hr_job_custom.mail_template_vendor_tracker_link', raise_if_not_found=False
        )
        if not template:
            return

        pending = self.tracker_link_ids.filtered(lambda l: l.email_url and not l.email_sent)
        for link in pending:
            template.send_mail(link.id, force_send=True)
            link.email_sent = True

    def _build_tracker_url(self, vendor, link_type='job_page'):
        """Build the exact same tracker URL used by Odoo's standard
        Recruitment > Trackers row.

        ``job_page`` is intentionally identical to the standard
        ``hr.recruitment.source.url`` value:

            <job-url>?utm_campaign=Job+Campaign&utm_medium=Website&utm_source=<Source>

        The email tracker uses the same Job URL and Source, but the
        medium is ``email``.  Keeping both URLs in one builder guarantees
        that the Vendors tab and the standard Trackers tab cannot drift
        apart.
        """
        self.ensure_one()

        job_path = self.website_url
        if not job_path or job_path == '#':
            job_path = '/jobs/detail/%s' % self.id

        source_name = vendor.source_id.name or vendor.name
        campaign = self.env.ref(
            'hr_recruitment.utm_campaign_job',
            raise_if_not_found=False,
        )
        website_medium = self.env['utm.medium'].sudo()._fetch_or_create_utm_medium('website')

        if link_type == 'email':
            return self._kavi_build_email_tracker_url(vendor.source_id)

        query_values = {
            'utm_campaign': campaign.name if campaign else 'Job Campaign',
            'utm_medium': website_medium.name if website_medium else 'Website',
            'utm_source': source_name,
        }

        return urls.urljoin(
            self.get_base_url(),
            '%s?%s' % (job_path, urlencode(query_values)),
        )

    # ------------------------------------------------------------------
    # Hide "Published" from the Job Position form only
    # ------------------------------------------------------------------
    def get_view(self, view_id=None, view_type='form', **options):
        """Strip the `website_published` field/button from the compiled
        Job Position FORM arch only.

        Deliberately done here instead of:
          - an XML <xpath> inheriting the specific view that renders the
            Publish button (website_hr_recruitment defines it under a
            view id that varies by version and isn't worth hardcoding), or
          - a `groups=` restriction on the field itself (tried and
            reverted - it removes the field from fields_get() for the
            restricted users project-wide, which breaks any OTHER view
            that reads it, e.g. the Job Positions Kanban card's
            "Published" ribbon, causing an OwlError:
            "Cannot read properties of undefined (reading 'type')").

        Doing it in get_view() only touches view_type == 'form', leaves
        website_published fully intact at the model/fields_get level for
        every other view, and is resilient to the field appearing as a
        plain <field name="website_published"/> or wrapped in a
        widget="website_redirect_button" - both are matched by name.
        """
        result = super().get_view(view_id=view_id, view_type=view_type, **options)
        if view_type == 'form' and 'website_published' in (result.get('arch') or ''):
            from lxml import etree
            doc = etree.fromstring(result['arch'])
            for node in doc.xpath("//field[@name='website_published']"):
                node.set("invisible", "1")
            # for node in doc.xpath("//field[@name='website_published']"):
            #     node.getparent().remove(node)
            result['arch'] = etree.tostring(doc, encoding='unicode')

       
        if view_type == 'form' and self._kavi_user_is_interviewer_only():
            arch = result.get('arch') or ''
            if any('name="%s"' % fname in arch for fname in self._KAVI_HTML_FIELD_INTERVIEWER_READONLY):
                from lxml import etree
                doc = etree.fromstring(result['arch'])
                changed = False
                for fname in self._KAVI_HTML_FIELD_INTERVIEWER_READONLY:
                    for node in doc.xpath("//field[@name='%s']" % fname):
                        node.set('readonly', '1')
                        changed = True
                if changed:
                    result['arch'] = etree.tostring(doc, encoding='unicode')

        
        if view_type == 'form' and self._kavi_user_is_interviewer_only():
            arch = result.get('arch') or ''
            if any(page_string in arch for page_string in self._KAVI_HIDDEN_PAGE_STRINGS_FOR_INTERVIEWER):
                from lxml import etree
                doc = etree.fromstring(result['arch'])
                changed = False
                for page_string in self._KAVI_HIDDEN_PAGE_STRINGS_FOR_INTERVIEWER:
                    for node in doc.xpath("//page[@string=$s]", s=page_string):
                        node.getparent().remove(node)
                        changed = True
                if changed:
                    result['arch'] = etree.tostring(doc, encoding='unicode')
        return result
