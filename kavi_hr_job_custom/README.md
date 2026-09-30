# kavi_hr_job_custom

Custom Odoo module implementing the Job Position (hr.job) requirements.

## Requirements covered
- Roles & Responsibilities — Html field, new notebook page, tracked (chatter shows old/new diff = "version history").
- Budgeting Information — Html field, new notebook page, tracked.
- Work Mode — Selection (Hybrid / Onsite / Office).
- Job Boards — Many2many to new custom model `hr.job.board`, new page, visible **only** to Recruitment User/Manager (not Interviewer).
- Vendors — Many2many to new custom model `hr.recruitment.vendor`, new page, visible **only** to Recruitment User/Manager. Each Vendor requires a `utm.source`. Adding a Vendor to a Job auto-creates **one** `hr.job.vendor.tracker.link` record. The Vendors tab displays the exact standard Odoo Tracker URL and, immediately after it, an Email Link generated from the Job Position Email Alias + Job Position name.
- Interviewer → "Hiring Manager" — see the ASSUMPTION note below.
- Published field hidden on the form.

## Install (Odoo 19.0)
1. Copy the `kavi_hr_job_custom` folder into your Odoo 19 addons path.
2. Update Apps List, then install **Kavi HR Job Position Customization**.
3. Restart the server if needed.

## Fix for the install error you hit
`ParseError: Element '<xpath expr="//field[@name='employment_type_id']">' cannot be located in parent view`

This happened because the module tried to anchor new fields next to specific existing fields (`employment_type_id`, `user_id`) on your `hr.job` form, and those exact fields/positions aren't there in your instance's layout. Fixed by:
- Anchoring everything only on `<notebook>` (adds a new tab) instead of any specific sibling field — this is present on essentially every tabbed form view regardless of customization.
- Moving the "hide Published" logic out of XML view-inheritance entirely and into a Python field override (`groups='base.group_no_one'` on `website_published`) in `models/hr_job.py` — this hides it wherever it's rendered without needing to know the exact view id website_hr_recruitment uses.

If your Published field is stored as `is_published` instead of `website_published` in your version, uncomment the second line right below it in `models/hr_job.py`.

## What changed for Odoo 19 (vs. the earlier 17.0 draft)
- **Manifest version** bumped to `19.0.1.0.0`.
- **Fixed the base view reference.** `hr.job`'s form view is defined in the core `hr` module as `hr.view_hr_job_form` — NOT `hr_recruitment.view_hr_job_form` (that id doesn't exist; `hr_recruitment` only *inherits* the `hr` view). All new pages/fields now correctly inherit `hr.view_hr_job_form`.
- **Fixed "Hide Published" to target the right view.** The Publish button/field is added by `website_hr_recruitment` in its own dedicated inherited view, `website_hr_recruitment.view_hr_job_form_website_published_button`. The module now inherits that view specifically instead of guessing the field lives in the main form.
- **Removed `werkzeug.urls.url_encode`.** That helper was removed from modern Werkzeug (the version Odoo 19's Python 3.12-based stack ships with), which would have crashed the vendor-tracker-link automation at runtime. Swapped to Python's built-in `urllib.parse.urlencode` — no functional change, just future-proof.
- View syntax (`<list>` instead of `<tree>`, `invisible="1"` instead of the old `attrs="{...}"`) was already 17+ compatible and carries forward unchanged into 19.0.
- `hr_recruitment.group_hr_recruitment_user` / `_manager` / `_interviewer`, and the `groups=` attribute on Python fields, are confirmed still current in the 19.0 codebase.

## Assumptions still worth verifying against your instance
1. **"Interviewer" field**: I could not see your screenshot, so I don't know whether an `interviewer_ids` field already exists on `hr.job` from your earlier Bug-list work.
   - If it does NOT exist yet → keep `hiring_manager_ids` as defined in `models/hr_job.py` (this is what's active right now).
   - If it DOES already exist (e.g. named `interviewer_ids`) → delete the `hiring_manager_ids` field block from `models/hr_job.py`, and in `views/hr_job_views.xml` uncomment the xpath block that simply relabels `interviewer_ids` to "Hiring Manager", and remove the `hiring_manager_ids` xpath block.
2. **Hide Published field fallback**: if the `field[@name='website_published']` xpath errors on load (some deployments/Enterprise variants render it only as `<widget name="website_publish_button"/>`), uncomment the fallback xpath included right below it in `views/hr_job_views.xml`.
3. **Groups used**: `hr_recruitment.group_hr_recruitment_user` (Recruitment User), `hr_recruitment.group_hr_recruitment_manager` (Admin), `hr_recruitment.group_hr_recruitment_interviewer` (Interviewer/Hiring Manager). If your "Hiring Manager" is actually a distinct security group (not the Interviewer group), tell me and I'll add a dedicated `res.groups` record instead of reusing the Interviewer group.
4. **Tracker link URLs**: the Vendors-tab `Tracker Link` is exactly the same URL as Odoo's standard Recruitment > Trackers `Tracker URL` (`utm_campaign=Job Campaign`, `utm_medium=Website`, `utm_source=<Vendor Source>`). The `Email Link` immediately follows it and uses the canonical `<alias>+<job-position>@<domain>` mailto format.
5. **Job Boards / Vendors menu location**: placed under Recruitment > Configuration. Move via `parent=` in the `<menuitem>` tags if you want them elsewhere.
6. **`employment_type_id` / `user_id` field names**: these are the standard field names on `hr.job` used as anchor points for the xpaths. If your database has renamed or removed them (via Studio, etc.), the corresponding xpath will fail on module install — tell me and I'll point it at a different anchor field.

## Files
```
kavi_hr_job_custom/
├── __init__.py
├── __manifest__.py
├── models/
│   ├── __init__.py
│   ├── hr_job.py            # hr.job extension + vendor automation
│   ├── job_board.py          # hr.job.board model
│   ├── vendor.py              # hr.recruitment.vendor model
│   └── tracker_link.py        # hr.job.vendor.tracker.link model
├── security/
│   ├── security.xml           # record rules restricting Job Boards/Vendors to Recruitment Access
│   └── ir.model.access.csv
├── data/
│   └── mail_template_data.xml # vendor notification email template
└── views/
    ├── hr_job_views.xml        # main form inheritance (pages, visibility, rename, hide)
    ├── job_board_views.xml
    ├── vendor_views.xml
    └── tracker_link_views.xml
```


### Offer Letter report access fix

The module includes a QWeb inheritance for `ats_recruitment_customization.report_offer_letter`.
The report previously evaluated `employee_id.job_title` under the current user's permissions,
which could trigger an AccessError for the restricted `hr.employee.version_id` field during Odoo's
prefetching. The inherited template evaluates only the Employee display value with `sudo()`.
This does not grant the user Employee access and does not expose the `version_id` field in the UI.

- **Tracker Email label**: the Email column in the Recruitment > Trackers tab and the Job Position > Vendors tracker list is explicitly labeled **Email** and forced visible as a list column.


## 19.0.3.27.11

- Fixes the `hr.job` RPC error raised for Interviewers by Odoo's stock `_compute_document_ids` when an ATS customization restricts `hr.applicant.employee_id`. The computation now performs only that internal employee check in sudo.
- Adds a mandatory module-upgrade migration for the `kavi_salary_structure_history` column introduced for native Salary Structure HTML history.
- Seeds/rebuilds Salary Structure native HTML history metadata for existing Applicants where the existing structured audit trail is continuous.

**Important:** after replacing the module files, upgrade `kavi_hr_job_custom` in Odoo. Merely restarting Odoo does not update the database schema.

## 19.0.3.27.12
- Fixes databases where `kavi_salary_structure_history` was declared in the Python model but its PostgreSQL column was never created.
- Uses an idempotent pre-migration and post-migration `ALTER TABLE ... ADD COLUMN IF NOT EXISTS` so an incomplete prior 19.0.3.27.11 upgrade can be repaired safely.
- Seeds the hidden Salary Structure HTML mirror from the existing plain-text Salary Structure.


## 19.0.3.27.17 database compatibility fix

The `hr.recruitment.vendor.contact_person` field is now a non-stored computed
field with an inverse method. Its source of truth is the existing
`contact_person_id` child `res.partner` record. This is intentional: older
databases may have `contact_person_id` but no physical
`hr_recruitment_vendor.contact_person` column. The previous stored Char field
caused registry flush failures such as `UndefinedColumn: contact_person`.

Upgrade with:

```text
python odoo-bin -d <database> -u kavi_hr_job_custom --stop-after-init
```

Then start Odoo normally.
