{
    'name': 'Applicant Blacklist',
    'version': '19.0.1.1.1',
    'category': 'Human Resources/Recruitment',
    'summary': 'Blacklist / un-blacklist applicants with reasons and a banner',
    'depends': ['hr_recruitment'],
    'data': [
        'security/ir.model.access.csv',
        'wizard/blacklist_wizard_views.xml',
        'wizard/remove_blacklist_wizard_views.xml',
        'data/ir_actions_server.xml',
        'views/hr_applicant_views.xml',
    ],
    'license': 'LGPL-3',
    'installable': True,
    'application': False,
}
