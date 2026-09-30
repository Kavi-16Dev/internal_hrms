{
    'name': 'ATS Recruitment Customization',
    'version': '19.0.17.0.0',
    'summary': 'Recruitment Offer Letter Components',
    'description': 'Adds Offer Letter Components page in Applicant form',
    'author': 'Your Company',
    'category': 'Human Resources',
    'depends': ['base', 'hr_recruitment',],
    'data': [
        "views/res_users_views.xml",
        "views/hr_applicant_views.xml",
        'views/hr_job_views.xml',
        'reports/offer_letter_report.xml',
        'reports/report_action.xml'
    ],

    'assets': {
        'web.assets_tests': [
            'ats_recruitment_customization/static/tests/offer_letter_tour.js',
        ],
    },

    'installable': True,
    'application': False,
}