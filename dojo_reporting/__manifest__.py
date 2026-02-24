{
    'name': 'Dojo Reporting & Analytics',
    'summary': 'KPI dashboard, cohort retention, attendance heatmap, belt rank distribution',
    'version': '19.0.1.0.0',
    'category': 'Reporting',
    'author': 'Dojo',
    'depends': [
        'disaster_member_belts',
        'dojo_attendance',
        'dojo_contracts',
        'dojo_ranks',
    ],
    'data': [
        'security/ir.model.access.csv',
        'views/dojo_reporting_views.xml',
        'views/menus.xml',
    ],
    'installable': True,
    'application': False,
    'license': 'LGPL-3',
}
