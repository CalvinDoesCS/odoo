# -*- coding: utf-8 -*-
{
    'name': 'Dojo Members',
    'summary': 'Member profiles, households, consent, medical notes and member numbering',
    'version': '19.0.2.0.0',
    'category': 'Membership',
    'author': 'Dojo Manager',
    'license': 'LGPL-3',
    'application': True,
    'depends': ['disaster_member_belts'],
    'data': [
        'security/ir.model.access.csv',
        'data/dojo_member_sequence.xml',
        'views/dojo_household_views.xml',
        'views/res_partner_member_views.xml',
        'views/menus.xml',
    ],
    'installable': True,
}
