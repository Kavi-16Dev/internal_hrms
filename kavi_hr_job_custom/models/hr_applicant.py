# -*- coding: utf-8 -*-
import logging

from markupsafe import Markup
from odoo import api, fields, models, _
from odoo.addons.html_editor.tools import handle_history_divergence

_logger = logging.getLogger(__name__)


class HrApplicant(models.Model):
    """Extend the Applicant form with:

      1) A set of always-visible Applicant Details fields (Total
         Experience, Current Organization, Current Location, Notice
         Period, Portfolio Link).

      2) A set of Offer Letter fields (Designation, Salary Structure,
         Joining Date, Other Offer Letter Components) and a separate
         Confidential Notes field - both restricted the same way as
         Budgeting Information on hr.job in this same module: visible
         only to Recruitment Access users (Officer/Administrator) and
         the custom Hiring Manager role, but NOT to Interviewers.

    NOTE: We deliberately do NOT override any stock hr.applicant field
    (e.g. 'linkedin_profile', 'availability') - all new fields below are
    our own, anchored safely via xpath in views/hr_applicant_views.xml
    next to the stock fields they relate to.

    NOTE: tracking=True is NOT set on the Html fields here, since Odoo's
    mail.tracking.value does not support Html fields (raises
    NotImplementedError on write) - same caveat documented in hr_job.py.
    """
    _inherit = ['hr.applicant', 'mail.thread', 'mail.activity.mixin', 'html.field.history.mixin']

  
    def _get_versioned_fields(self):
        """Return the fields handled by Odoo's native HTML HistoryDialog.

        Salary Structure exists in different ATS deployments under either
        ``offer_salary_structure`` (HTML) or ``salary_structure`` (plain text).
        The hidden ``kavi_salary_structure_history`` HTML field is the stable
        native-history field for both variants.  Confidential Notes remains
        a normal HTML versioned field.

        We deliberately do NOT native-version ``offer_salary_structure``
        directly.  The hidden mirror is synchronized from it before the
        html.field.history.mixin writes, which makes the history chain
        independent of whether the ATS field is Html, Text, or Char and
        gives the Version History menu one stable field to open.
        """
        versioned_fields = []
        for fname in ('kavi_salary_structure_history', 'confidential_notes'):
            field = self._fields.get(fname)
            if (
                field
                and getattr(field, 'type', None) == 'html'
                and getattr(field, 'sanitize', False)
            ):
                versioned_fields.append(fname)

        if self.env.context.get('kavi_skip_native_salary_history'):
            versioned_fields = [
                f for f in versioned_fields
                if f != 'kavi_salary_structure_history'
            ]
        return versioned_fields

    # ------------------------------------------------------------------
    # Applicant Details - visible to anyone who can see the Applicant
    # form (Details tab, "Applicant" group).
    # ------------------------------------------------------------------
    total_experience = fields.Char(string='Total Experience (Years)')
    current_organization = fields.Char(string='Current Organization')
    current_location = fields.Char(string='Current Location')
    notice_period = fields.Char(string='Notice Period')

    # Shown right under the stock 'LinkedIn Profile' field, top of form.
    portfolio_link = fields.Char(string='Portfolio Link')

   
    resume_line_ids = fields.One2many(
        'hr.applicant.resume.line', 'applicant_id', string='Resume lines',
    )

    # ------------------------------------------------------------------
    # Job Board -> Source auto-fill / restriction
    # ------------------------------------------------------------------
    # There is no separate "Job Board" field on the Applicant anymore.
    # The stock 'Source' field (source_id) IS the Job Board field now:
    # its selection is restricted (via the domain on source_id in
    # views/hr_applicant_views.xml) to the Source(s) that correspond to
    # the Job Boards configured on the Applied Job (see job_board_ids
    # on hr.job / hr.job.board._get_or_create_utm_source()). When the
    # Applied Job has no Job Boards configured at all, every Source is
    # offered (unrestricted), matching stock behaviour for Jobs that
    # don't use the Job Boards feature.
    job_board_source_ids = fields.Many2many(
        'utm.source',
        compute='_compute_job_board_source_ids',
        string='Job Board Sources',
        help='Technical: the Source(s) this Applicant is allowed to pick '
             'in the Source field above, derived from the Applied Job\'s '
             'configured Job Boards. Not shown on the form.',
    )

    @api.depends('job_id.job_board_ids')
    def _compute_job_board_source_ids(self):
        UtmSource = self.env['utm.source'].sudo()
        for applicant in self:
            # `job_board_ids` is intentionally restricted to Recruitment
            # Officer/Administrator on hr.job. Interviewers still need to
            # open Applicant records, and this technical computed field is
            # present in the Applicant form only to build the Source domain.
            # Reading the restricted Job Board field with the Interviewer's
            # normal environment therefore caused: "You do not have enough
            # rights to access the field job_board_ids on Job Position".
            #
            # Read the configuration with sudo, but keep the result limited
            # to the utm.source records the applicant actually needs. This
            # does NOT grant the interviewer access to hr.job.job_board_ids;
            # it only prevents a technical computation from leaking that
            # field-level access error into the Applicant form.
            job = applicant.job_id.sudo()
            boards = job.job_board_ids
            if not boards:
                # No Job Boards configured on the Applied Job: don't
                # restrict Source at all, so Jobs that don't use the
                # Job Boards feature keep free choice of Source.
                applicant.job_board_source_ids = UtmSource.search([])
                continue
            sources = UtmSource
            for board in boards:
                sources |= board._get_or_create_utm_source()
            applicant.job_board_source_ids = sources

   
    _OFFER_LETTER_GROUPS = (
        'hr_recruitment.group_hr_recruitment_user,'
        'hr_recruitment.group_hr_recruitment_manager,'
        'kavi_hr_job_custom.group_hr_recruitment_hiring_manager'
    )

   
    _KAVI_HIDDEN_PAGE_STRINGS_FOR_INTERVIEWER = (
        'Offer Letter Components',
        'Offer Letter',
    )
    _KAVI_PAGE_NAME_MARKERS_FOR_INTERVIEWER = (
        'offer_letter_components',
        'offer_letter',
    )
    _KAVI_RESTRICTED_FORM_FIELDS_FOR_INTERVIEWER = {
        # These fields are supplied by ats_recruitment_customization and
        # cannot safely be made group-restricted here because their original
        # field definitions belong to that module. We therefore remove them
        # from the Interviewer's compiled Applicant form.
        'designation',
        'salary_structure',
        'joining_date',
        'offer_letter_components',
        'other_offer_letter_components',
        'offer_salary_structure',
    }

    def _kavi_user_is_interviewer_only(self):
        user = self.env.user
        if not user.has_group('hr_recruitment.group_hr_recruitment_interviewer'):
            return False
        allowed_groups = (
            'hr_recruitment.group_hr_recruitment_user',
            'hr_recruitment.group_hr_recruitment_manager',
            'kavi_hr_job_custom.group_hr_recruitment_hiring_manager',
        )
        return not any(user.has_group(group) for group in allowed_groups)

    @api.model
    def get_view(self, view_id=None, view_type='form', **options):
        # Interviewers must be able to open the Applicant form, but must not
        # receive the Offer Letter / confidential fields in the compiled XML
        # at all. Field-level groups on our own fields handle ORM access; the
        # dependency-owned fields (salary_structure/joining_date/etc.) are
        # filtered here because we do not own their field definitions.
        result = super().get_view(view_id=view_id, view_type=view_type, **options)
        if view_type != 'form' or not self._kavi_user_is_interviewer_only():
            return result

        arch = result.get('arch') or ''
        if not arch:
            return result

        from lxml import etree
        doc = etree.fromstring(arch.encode('utf-8'))
        changed = False

        # Remove whole Offer Letter / Offer Letter Components pages first.
        for page in list(doc.xpath('//page')):
            page_string = (page.get('string') or '').strip().lower()
            page_name = (page.get('name') or '').strip().lower()
            hide_by_string = page_string in {
                value.lower() for value in self._KAVI_HIDDEN_PAGE_STRINGS_FOR_INTERVIEWER
            }
            hide_by_name = any(
                marker in page_name
                for marker in self._KAVI_PAGE_NAME_MARKERS_FOR_INTERVIEWER
            )
            if hide_by_string or hide_by_name:
                parent = page.getparent()
                if parent is not None:
                    parent.remove(page)
                    changed = True

        # Remove the individual restricted fields wherever an external
        # inherited view placed them (for example directly on Application
        # Details). This is what prevents Joining Date / Salary Structure from
        # remaining visible outside a dedicated Offer Letter page.
        for field in list(doc.xpath('//field')):
            field_name = (field.get('name') or '').strip()
            if field_name in self._KAVI_RESTRICTED_FORM_FIELDS_FOR_INTERVIEWER:
                parent = field.getparent()
                if parent is not None:
                    parent.remove(field)
                    changed = True

        # Remove our custom Confidential Notes page as an extra defensive
        # measure, even though its page `groups` attribute already excludes
        # Interviewers.
        for page in list(doc.xpath('//page')):
            page_name = (page.get('name') or '').strip().lower()
            if page_name == 'kavi_confidential_notes_page':
                parent = page.getparent()
                if parent is not None:
                    parent.remove(page)
                    changed = True

        # The Applicant JS controller adds Salary Structure / Confidential
        # Notes Version History entries. Interviewers must not get those
        # actions either, because the corresponding content is deliberately
        # hidden from them. Remove the custom js_class from their compiled
        # form so the stock Recruitment form controller is used.
        form = doc.xpath('//form')
        if form and form[0].get('js_class') == 'kavi_hr_applicant_form':
            form[0].attrib.pop('js_class', None)
            changed = True

        if changed:
            result['arch'] = etree.tostring(doc, encoding='unicode')
        return result

    designation = fields.Char(
        string='Designation',
        groups=_OFFER_LETTER_GROUPS,
    )
    # offer_salary_structure = fields.Html(
    #     string='Salary Structure',
    #     sanitize=True,
    #     groups=_OFFER_LETTER_GROUPS,
    # )
    # joining_date = fields.Date(
    #     string='Joining Date',
    #     groups=_OFFER_LETTER_GROUPS,
    # )
    # offer_letter_components = fields.Html(
    #     string='Other Offer Letter Components',
    #     sanitize=True,
    #     groups=_OFFER_LETTER_GROUPS,
    # )

    # ------------------------------------------------------------------
    # Confidential Notes - own notebook page, same restricted audience.
    # ------------------------------------------------------------------
    confidential_notes = fields.Html(
        string='Confidential Notes',
        sanitize=True,
        default='',
        groups=_OFFER_LETTER_GROUPS,
    )

   
    # `salary_structure` is the real field supplied by the
    # ats_recruitment_customization dependency. It is a plain-text field and
    # remains the source of truth for Salary Structure.
    #
    # The structured Version History model continues to log the real field.
    _KAVI_HTML_TRACKED_FIELDS = {
        # Both names are supported because the ATS customization changed
        # technical field names across deployed versions.
        'offer_salary_structure': 'Salary Structure',
        'salary_structure': 'Salary Structure',
        'confidential_notes': 'Confidential Notes',
    }

    # Hidden Html mirror used exclusively by Odoo's native
    # html.field.history.mixin / HistoryDialog for Salary Structure.
    kavi_salary_structure_history = fields.Html(
        string='Salary Structure History Content',
        sanitize=True,
        default='',
        copy=False,
        groups=_OFFER_LETTER_GROUPS,
    )

   
    _KAVI_ALSO_LOG_TO_CHATTER = False

    applicant_version_history_ids = fields.One2many(
        'hr.applicant.version.history', 'applicant_id', string='Version History',
    )
    applicant_version_history_count = fields.Integer(
        string='Version History Count',
        compute='_compute_applicant_version_history_count',
    )

    is_accessible_to_current_user = fields.Boolean(
        string="Accessible",
        compute="_compute_is_accessible_to_current_user",
        store=True,
    )

    @api.depends('user_id')
    def _compute_is_accessible_to_current_user(self):
        current_user = self.env.user
        for rec in self:
            rec.is_accessible_to_current_user = (
                rec.user_id == current_user
                or current_user.has_group('hr_recruitment.group_hr_recruitment_manager')
            )

    def _compute_applicant_version_history_count(self):
        counts = self.env['hr.applicant.version.history']._read_group(
            [('applicant_id', 'in', self.ids)], ['applicant_id'], ['__count'],
        )
        count_by_applicant = {applicant.id: count for applicant, count in counts}
        for applicant in self:
            applicant.applicant_version_history_count = count_by_applicant.get(applicant.id, 0)

    def action_open_applicant_version_history(self):
        """Clicking 'Version History' now opens the popup wizard (see
        models/hr_applicant_version_history_wizard.py / views/
        hr_applicant_version_history_wizard_views.xml) as a dialog
        (target='new'), matching the reference UI - and matching
        action_open_job_version_history() in hr_job.py exactly: a
        timeline of past versions on the left, the selected version's
        content on the right, a 'View comparison' toggle, and
        Restore/Discard buttons.
        """
        self.ensure_one()

        has_history = bool(self.env['hr.applicant.version.history'].search_count(
            [('applicant_id', '=', self.id)],
        ))
        if not has_history:
            return {
                'type': 'ir.actions.client',
                'tag': 'display_notification',
                'params': {
                    'title': _('No Version History Yet'),
                    'message': _(
                        'No tracked changes have been saved for this '
                        'Applicant yet. Edit Salary Structure or '
                        'Confidential Notes and save the record, then try '
                        'again.'
                    ),
                    'type': 'info',
                    'sticky': False,
                },
            }

        wizard_form = self.env.ref('kavi_hr_job_custom.view_kavi_applicant_version_history_wizard_form')
        return {
            'type': 'ir.actions.act_window',
            'name': _('Version History'),
            'res_model': 'hr.applicant.version.history.wizard',
            'view_mode': 'form',
            'views': [(wizard_form.id, 'form')],
            'target': 'new',
            'context': {'default_applicant_id': self.id},
        }


   
    # The native HistoryDialog always uses this stable hidden HTML field for
    # Salary Structure.  The actual ATS Salary Structure field is mirrored
    # into it in create()/write().
    _KAVI_NATIVE_HISTORY_FIELD_CANDIDATES = (
        'kavi_salary_structure_history',
        'confidential_notes',
    )

    def _kavi_native_history_fields(self):
        return [
            f for f in self._KAVI_NATIVE_HISTORY_FIELD_CANDIDATES
            if f in self._fields
        ]

    @staticmethod
    def _kavi_salary_structure_to_history_html(value):
        """Convert the real plain-text Salary Structure into safe Html.

        The mirror must be Html because Odoo's native HTML history mixin
        requires versioned fields to have ``sanitize=True``. The conversion
        is deliberately one-way: `salary_structure` remains the source of
        truth and the mirror is never shown as an editable business field.
        """
        from odoo.tools import plaintext2html

        if not value:
            return ''
        return plaintext2html(str(value))

    
    @staticmethod
    def _kavi_clean_salary_html(value):
        """Return Salary Structure HTML safe for the hidden native-history mirror.

        The ATS Html editor can embed ``data-last-history-steps`` metadata in
        its value.  That metadata belongs to the real ATS field's editor
        history, not to our hidden mirror.  Remove it before copying the value
        so the mirror starts its own independent native-history chain.
        """
        import re

        if not value:
            return ''
        return re.sub(r' data-last-history-steps="[^"]*"', '', str(value))

    def _kavi_salary_structure_current_html(self):
        """Return the currently deployed Salary Structure as HTML."""
        self.ensure_one()
        if 'offer_salary_structure' in self._fields:
            return self._kavi_clean_salary_html(self.offer_salary_structure or '')
        if 'salary_structure' in self._fields:
            return self._kavi_salary_structure_to_history_html(
                self.salary_structure or ''
            )
        return ''

    def _kavi_sync_salary_history_mirror(self, vals):
        """Mirror the real Salary Structure into the stable HTML history field.

        ``offer_salary_structure`` is the field used by the current form.
        Older databases may instead expose ``salary_structure``.  The mirror
        is written in the same ORM write as the business field, so
        html.field.history.mixin records the *previous* Salary Structure
        exactly like it records Confidential Notes.
        """
        if 'kavi_salary_structure_history' not in self._fields:
            return vals
        if self.env.context.get('kavi_skip_salary_history_mirror'):
            return vals

        salary_value = None
        if 'offer_salary_structure' in vals:
            salary_value = self._kavi_clean_salary_html(vals.get('offer_salary_structure'))
        elif 'salary_structure' in vals:
            salary_value = self._kavi_salary_structure_to_history_html(
                vals.get('salary_structure')
            )
        else:
            return vals

        vals = dict(vals)
        vals['kavi_salary_structure_history'] = salary_value
        return vals

    def _kavi_reset_native_html_history(self, field_names):
        for applicant in self.sudo():
            metadata = dict(applicant.html_field_history_metadata or {})
            changed = False
            for fname in field_names:
                if metadata.pop(fname, None) is not None:
                    changed = True
            if changed:
                applicant.write({'html_field_history_metadata': metadata})

   
    def html_field_history_get_content_at_revision(self, *args, **kwargs):
        try:
            return super().html_field_history_get_content_at_revision(*args, **kwargs)
        except IndexError:
            field_name = args[0] if args else kwargs.get('field_name')
            self.ensure_one()
            _logger.warning(
                "kavi_hr_job_custom: stale html_field_history_metadata "
                "detected for hr.applicant id=%s field=%s while opening "
                "its native History dialog; clearing that field's stored "
                "history and falling back to its current content so the "
                "dialog opens cleanly instead of erroring.",
                self.id, field_name,
            )
            if field_name in self._kavi_native_history_fields():
                self._kavi_reset_native_html_history([field_name])
            if field_name and field_name in self._fields:
                return self[field_name] or ''
            return ''

    def write(self, vals):
        # Salary Structure is a plain-text dependency field, so mirror every
        # explicit change into a sanitize=True Html field. That mirror is
        # what the native Odoo HistoryDialog versions.
        # Keep the Html mirror synchronized whenever the legacy plain-text
        # salary_structure field exists.  In deployments that also have
        # offer_salary_structure, that Html field is tracked directly too;
        # the mirror keeps older salary_structure history fully compatible.
        # Synchronize the stable native-history mirror BEFORE calling
        # super().write().  This is the key point: html.field.history.mixin
        # then sees the old mirror value and the new mirror value and creates
        # the same revision chain that Confidential Notes uses.
        vals = self._kavi_sync_salary_history_mirror(vals)

        # Job Board -> Source auto-fill (mirrors create()/onchange above)
        # for writes that don't go through the form's onchange, e.g. API
        # calls, imports, or server actions setting job_id.
        kavi_sync_job_board_source = (
            'job_id' in vals and 'source_id' not in vals
        )

        if len(self) == 1:
            native_history_fields = self._kavi_native_history_fields()
            for fname in native_history_fields:
                if fname in vals and not self[fname]:
                    super(HrApplicant, self).write({fname: ''})
                    self._kavi_reset_native_html_history([fname])
            for fname in native_history_fields:
                if fname in vals:
                    handle_history_divergence(self, fname, vals)

        tracked_fields = {
            f: label for f, label in self._KAVI_HTML_TRACKED_FIELDS.items() if f in self._fields
        }
        changed_fields = [f for f in tracked_fields if f in vals]

       
        sudo_self = self.sudo()

        old_values = {}
        if changed_fields:
            for applicant in sudo_self:
                old_values[applicant.id] = {
                    f: (applicant[f] or '') for f in changed_fields
                }

        res = super().write(vals)

        if kavi_sync_job_board_source:
            for applicant in self:
                if applicant.source_id:
                    # Never overwrite a Source the user already picked -
                    # matches the onchange's behaviour.
                    continue
                source = applicant._kavi_get_job_board_source(applicant.job_id)
                if source:
                    # 'source_id' is deliberately absent from `vals` here
                    # (guarded by kavi_sync_job_board_source above), so
                    # this assignment's own internal write() call cannot
                    # re-enter this branch - no recursion guard needed.
                    applicant.source_id = source

        if changed_fields:
            subtype = self.env.ref(
                'kavi_hr_job_custom.mail_message_subtype_applicant_version_history',
                raise_if_not_found=False,
            )
            HistoryModel = self.env['hr.applicant.version.history'].sudo()
            for applicant in sudo_self:
                for fname in changed_fields:
                    old_val = old_values[applicant.id].get(fname, '')
                    new_val = applicant[fname] or ''
                    if old_val == new_val:
                        continue
                    label = tracked_fields[fname]

                  
                    try:
                        HistoryModel.create({
                            'applicant_id': applicant.id,
                            'field_name': fname,
                            'field_label': label,
                            'old_value': old_val,
                            'new_value': new_val,
                        })
                    except Exception:
                        _logger.exception(
                            "kavi_hr_job_custom: failed to log version "
                            "history for hr.applicant id=%s field=%s",
                            applicant.id, fname,
                        )

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
                        applicant.message_post(
                            body=body,
                            subtype_id=subtype.id if subtype else False,
                        )

        return res

    def _kavi_populate_resume_from_ocr(self, parsed_data):
        self.ensure_one()
        if not parsed_data:
            return

        def _first(d, *keys):
            """Return the first non-empty value found under any of
            `keys` in dict `d` (case-sensitive keys, as OCR payloads
            typically are). Silently returns False if none match or
            `d` isn't a dict - keeps this method safe to call with
            whatever shape your OCR result actually has."""
            if not isinstance(d, dict):
                return False
            for key in keys:
                value = d.get(key)
                if value:
                    return value
            return False

        ResumeLineType = self.env['hr.resume.line.type'].sudo()
        experience_type = ResumeLineType.search([('name', '=', 'Experience')], limit=1) \
            or ResumeLineType.create({'name': 'Experience', 'sequence': 10})
        education_type = ResumeLineType.search([('name', '=', 'Education')], limit=1) \
            or ResumeLineType.create({'name': 'Education', 'sequence': 20})

        today = fields.Date.context_today(self)
        new_lines = []

        experience_entries = _first(parsed_data, 'experience', 'work_experience', 'experiences', 'work_history') or []
        for entry in experience_entries:
            new_lines.append((0, 0, {
                'line_type_id': experience_type.id,
                'name': _first(entry, 'title', 'position', 'job_title', 'role', 'company', 'employer') or _('Experience'),
                'date_start': _first(entry, 'date_start', 'start_date') or today,
                'date_end': _first(entry, 'date_end', 'end_date') or False,
                'description': _first(entry, 'description', 'summary') or False,
            }))

        education_entries = _first(parsed_data, 'education', 'educations', 'education_history') or []
        for entry in education_entries:
            new_lines.append((0, 0, {
                'line_type_id': education_type.id,
                'name': _first(entry, 'title', 'degree', 'course', 'school', 'institution') or _('Education'),
                'date_start': _first(entry, 'date_start', 'start_date') or today,
                'date_end': _first(entry, 'date_end', 'end_date') or False,
                'description': _first(entry, 'description', 'summary') or False,
            }))

        vals = {}
        if new_lines:
            vals['resume_line_ids'] = new_lines

        # Only fill these if they're still empty on the applicant, so we
        # never clobber something a recruiter already typed in by hand.
        simple_field_sources = {
            'total_experience': ('total_experience', 'total_years_of_experience'),
            'current_organization': ('current_organization', 'current_company'),
            'current_location': ('current_location', 'location'),
        }
        for field_name, source_keys in simple_field_sources.items():
            if self[field_name]:
                continue
            value = _first(parsed_data, *source_keys)
            if value:
                vals[field_name] = str(value)

        if vals:
            try:
                self.write(vals)
            except Exception:
                _logger.exception(
                    "kavi_hr_job_custom: failed to auto-fill Resume page "
                    "from Digitize Resume (OCR) data for hr.applicant id=%s",
                    self.id,
                )

    def _get_employee_create_vals(self):
        """When an Applicant is hired, carry their Resume lines over to
        the new hr.employee record's own Resume page - same continuity
        pattern core Odoo already uses for Skills
        (hr_recruitment_skills.HrApplicant._get_employee_create_vals).
        """
        vals = super()._get_employee_create_vals()
        vals['resume_line_ids'] = [
            (0, 0, {
                'name': line.name,
                'date_start': line.date_start,
                'date_end': line.date_end,
                'duration': line.duration,
                'description': line.description,
                'line_type_id': line.line_type_id.id,
                'course_type': line.course_type,
                'external_url': line.external_url,
                'certificate_filename': line.certificate_filename,
                'certificate_file': line.certificate_file,
            })
            for line in self.resume_line_ids
        ]
        return vals

    
    def _kavi_get_job_board_source(self, job):
        """Return the `utm.source` to auto-fill on this Applicant's
        Source field: when the Applied Job has exactly ONE Job Board
        configured, that Job Board's Source (creating a matching
        Source if one does not already exist).

        Returns an empty recordset when the Job has no Job Board
        configured, or more than one - in which case Source can no
        longer be guessed automatically and must be picked by hand,
        restricted to the Job's configured Job Boards (see
        `job_board_source_ids` / the domain on `source_id` in
        views/hr_applicant_views.xml).
        """
        if not job:
            return self.env['utm.source']
        # Job Boards are restricted to Recruitment Officer/Administrator on
        # hr.job. Use a sudoed Job record for this technical auto-fill so an
        # Interviewer can still create/change an Applicant without a field
        # access error.
        job = job.sudo()
        boards = job.job_board_ids
        if len(boards) != 1:
            return self.env['utm.source']
        return boards._get_or_create_utm_source()

    @api.onchange('job_id')
    def _onchange_job_id_kavi_job_board_source(self):
        """Live UI feedback: picking a Job Position - if it has exactly
        one Job Board configured - fills in Source right away, the same
        way create()/write() do it on save. Only ever touches Source,
        and only when Source is still empty (never overwrites a Source
        the user already picked). Medium is never touched here either.
        """
        for applicant in self:
            if applicant.source_id:
                continue
            source = applicant._kavi_get_job_board_source(applicant.job_id)
            if source:
                applicant.source_id = source

    @api.model_create_multi
    def create(self, vals_list):
        # Seed the hidden Html mirror when an Applicant is created with a
        # Salary Structure. Creation itself does not create an HTML history
        # revision (Odoo's mixin intentionally skips history on create), so
        # the first subsequent Salary Structure edit becomes the first native
        # history entry.
        for vals in vals_list:
            if (
                'offer_salary_structure' in vals
                or 'salary_structure' in vals
            ):
                synced = self._kavi_sync_salary_history_mirror(vals)
                vals.clear()
                vals.update(synced)

        JobModel = self.env['hr.job']
        for vals in vals_list:
            if vals.get('source_id'):
                continue
            job = JobModel.browse(vals['job_id']) if vals.get('job_id') else JobModel
            if not job:
                continue
            source = self._kavi_get_job_board_source(job)
            if source:
                vals['source_id'] = source.id

        applicants = super().create(vals_list)

        
        HistoryModel = self.env['hr.applicant.version.history'].sudo()
        for applicant in applicants:
            try:
                HistoryModel.create({
                    'applicant_id': applicant.id,
                    'field_name': '__baseline__',
                    'field_label': _('Applicant Created'),
                    'old_value': '',
                    'new_value': applicant.partner_name or applicant.display_name or '',
                })
            except Exception:
                _logger.exception(
                    "kavi_hr_job_custom: failed to create baseline "
                    "version history for new hr.applicant id=%s",
                    applicant.id,
                )

        return applicants

