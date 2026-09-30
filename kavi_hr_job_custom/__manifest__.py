{
    'name': 'Kavi HR Job Position Customization',
    'version': '19.0.26.0.0',
    'summary': 'Custom fields on Job Position for Offer Letter Generation, '
               'Job Boards, Vendors and Tracker Link automation.',
    'description': """
Adds to hr.job (Job Position):
  - Key Roles and Responsibilities (Html, tracked/versioned - displayed
    wherever your existing view places it, no dedicated page added by
    this module)
  -
""",
    'category': 'Human Resources/Recruitment',
    'author': 'Kavi Global',
    'depends': [
        'base',
        'portal',
        'hr_recruitment',
        'website_hr_recruitment',
        'mail',
        'utm',
        'html_editor',
        'hr_skills',
        'hr_recruitment_skills',
        # The offer-letter report is defined by this installed customization.
        # We inherit its QWeb template below to make the employee lookup
        # permission-safe for Recruitment users/interviewers.
        'ats_recruitment_customization',
    ],
    'data': [
        'security/security.xml',
        'security/ir.model.access.csv',
        'data/mail_template_data.xml',
        'data/version_history_data.xml',
        'data/hr_job_tracked_field_data.xml',
        'views/job_board_views.xml',
        'views/vendor_views.xml',
        'views/res_partner_views.xml',
        'views/tracker_link_views.xml',
        'views/hr_job_tracked_field_views.xml',
        'views/hr_job_views.xml',
        'views/hr_applicant_resume_line_views.xml',
        'views/hr_applicant_views.xml',
        'views/version_history_views.xml',
        'views/hr_job_version_history_views.xml',
        'views/hr_job_version_history_wizard_views.xml',
        'views/hr_applicant_version_history_views.xml',
        'views/hr_applicant_version_history_wizard_views.xml',
        'views/version_history_actions.xml',
        'views/job_board_account_views.xml',
    ],
    'assets': {
        'web.assets_backend': [
            'kavi_hr_job_custom/static/src/scss/kavi_version_history_wizard.scss',
            'kavi_hr_job_custom/static/src/js/kavi_version_history_wizard_header_menu.js',
            'kavi_hr_job_custom/static/src/js/kavi_timeline_radio_field.js',
            'kavi_hr_job_custom/static/src/xml/kavi_timeline_radio_field.xml',
            'kavi_hr_job_custom/static/src/js/kavi_html_field_history.js',
            'kavi_hr_job_custom/static/src/js/kavi_email_tracker_field.js',
            'kavi_hr_job_custom/static/src/xml/kavi_email_tracker_field.xml',
            'kavi_hr_job_custom/static/src/js/kavi_hr_job_form_view.js',
            'kavi_hr_job_custom/static/src/js/kavi_hr_applicant_form_view.js',
        ],
    },
    'installable': True,
    'application': False,
    'license': 'LGPL-3',
    'post_init_hook': 'post_init_hook',
}
