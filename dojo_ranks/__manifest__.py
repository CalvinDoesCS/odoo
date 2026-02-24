# -*- coding: utf-8 -*-
{
    'name': 'Dojo Ranks',
    'summary': 'Curriculum content library, rank requirements, and promotion history',
    'description': """
Dojo Ranks
==========
Builds on disaster_member_belts belt-rank system:
- Extends belt rank config with minimum days and JSON requirements
- Curriculum content (video/doc/link) library per rank
- Formal rank promotion history log
- Curriculum tag cloud
    """,
    'version': '19.0.2.0.0',
    'category': 'Membership',
    'author': 'Dojo Manager',
    'license': 'LGPL-3',
    'application': True,
    'depends': ['disaster_member_belts'],
    'data': [
        'security/ir.model.access.csv',
        'views/dojo_curriculum_views.xml',
        'views/dojo_rank_history_views.xml',
        'views/belt_rank_ext_views.xml',
        'views/menus.xml',
    ],
    'installable': True,
    'auto_install': False,
}
