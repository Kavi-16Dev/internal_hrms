{
    'name': 'HR Recruitment - Duplicate',
    'version': '19.0.7.0.0',
    'category': 'Human Resources/Recruitment',
    'summary': 'Detect duplicate job applications (Email/Mobile) across Job Portal, Job Boards and Email sources',
    'description': """
Duplicate Application Detection
================================
This module prevents duplicate job applications based on Email OR Phone.

Business rules
--------------
1. Candidate Name and LinkedIn are never used for duplicate matching.
2. If an Email address already exists on any existing `hr.applicant`, a new
   application using that Email is blocked.
3. If a Phone number already exists on any existing `hr.applicant`, a new
   application using that Phone is blocked.
4. If both Email and Phone already exist, the application is also blocked.
5. The rule applies to every source: public Job Portal, Job Boards, Email,
   OCR / Digitize Resume, imports, and manual backend creation.
6. The same protection is applied when an existing applicant is edited so
   its Email or Phone would become a duplicate.
7. Public applicants receive an immediate warning for Email, Phone, or both.
   The browser prevents form submission when a duplicate is detected.
8. The Python create()/write() checks remain authoritative so the duplicate
   rule cannot be bypassed by disabling JavaScript or calling the server
   directly.
9. Phone values are normalized by removing formatting characters before
   comparison.

The Job Position name shown in the public warning is read dynamically from
the selected `hr.job` record. Candidate Name is never included in duplicate
matching.
""",

    'author': 'Custom Development',
    'license': 'LGPL-3',
    'depends': ['hr_recruitment', 'website_hr_recruitment'],
    'data': [
        'views/hr_applicant_views.xml',
    ],
    'assets': {
        'web.assets_frontend': [
            'hr_recruitment_duplicate_detection/static/src/js/hr_recruitment_form.js',
            'hr_recruitment_duplicate_detection/static/src/scss/duplicate_warning.scss',
        ],
    },
    'installable': True,
    'application': False,
    'auto_install': False,
}
