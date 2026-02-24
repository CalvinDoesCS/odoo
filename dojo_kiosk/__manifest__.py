# -*- coding: utf-8 -*-
{
    'name': 'Dojo Kiosk',
    'version': '19.0.2.0.0',
    'summary': 'Fullscreen kiosk — badge/name check-in for students, management panel for staff',
    'category': 'Dojo',
    'author': 'Dojo',
    'depends': [
        'disaster_member_belts',
        'dojo_attendance',
        'web',
    ],
    'data': [
        'security/ir.model.access.csv',
        'views/kiosk_config_views.xml',
        'views/menus.xml',
        'data/default_config.xml',
    ],
    'assets': {
        'web.assets_backend': [
            'dojo_kiosk/static/src/xml/kiosk.xml',
            'dojo_kiosk/static/src/css/kiosk.css',
            'dojo_kiosk/static/src/js/kiosk_app.js',
        ],
    },
    'installable': True,
    'application': True,
    'license': 'LGPL-3',
}
