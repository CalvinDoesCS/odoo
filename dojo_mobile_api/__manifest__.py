{
    'name': 'Dojo Mobile API',
    'summary': 'JSON REST controllers for mobile app — member profile, booking, check-in, wallet, announcements, curriculum',
    'version': '19.0.1.0.0',
    'category': 'Hidden',
    'author': 'Dojo',
    'depends': [
        'disaster_member_belts',
        'dojo_attendance',
        'dojo_contracts',
        'dojo_announcements',
        'dojo_ranks',
        'dojo_members',
    ],
    'data': [
        'security/ir.model.access.csv',
        'data/api_token_sequence.xml',
    ],
    'installable': True,
    'application': False,
    'license': 'LGPL-3',
}
