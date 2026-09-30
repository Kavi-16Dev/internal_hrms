{
    'name': 'Job Position Publish Approval Flow',
    'version': '19.0.4.0.0',
    'category': 'Human Resources/Recruitment',
    'summary': 'Approval workflow for publishing Job Positions (Submit / Approve / Reject / Close / Cancel)',
    'description': """
    Job Position Publish Approval Flow
    ===================================
    """,
    'author': 'Kishor Kumar Ramesh',
    'depends': ['base', 'hr','hr_recruitment', 'website_hr_recruitment', 'mail'],
    'data': [
        'data/mail_template_data.xml',
        'views/res_users_views.xml',
        'views/hr_job_views.xml',
    ],
    'installable': True,
    'application': False,
    'license': 'LGPL-3',
}
