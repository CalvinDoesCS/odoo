{
    'name': 'Dojo Dashboard',
    'summary': 'Standalone Dojo analytics dashboard — members, attendance, billing, memberships, appointments and kiosk shortcuts.',
    'version': '19.0.4.0.0',
    'category': 'Membership',
    'author': 'Dojo',
    'depends': [
        'disaster_member_belts',
        'web',
        'project_todo',
        'calendar',
    ],
    'data': [
        'security/res_groups.xml',
        'security/ir.model.access.csv',
        'security/hr_menu_restrict.xml',
        'views/menus.xml',
    ],
    'assets': {
        'web.assets_backend': [
            'dojo_dashboard/static/src/css/dojo_dashboard.css',
            'dojo_dashboard/static/src/xml/dojo_widgets.xml',
            'dojo_dashboard/static/src/xml/dojo_dashboard.xml',
            'dojo_dashboard/static/src/js/dojo_widgets.js',
            'dojo_dashboard/static/src/js/dojo_dashboard.js',
        ],
    },
    'installable': True,
    'application': True,
    'license': 'LGPL-3',
}
