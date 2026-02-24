{
    'name': 'Dojo Audit Log',
    'summary': 'Immutable audit trail for member data changes, logins, and data exports',
    'version': '19.0.1.0.0',
    'category': 'Hidden',
    'author': 'Dojo',
    'depends': ['disaster_member_belts'],
    'data': [
        'security/ir.model.access.csv',
        'security/audit_security_groups.xml',
        'views/dojo_audit_log_views.xml',
        'views/menus.xml',
        'data/audit_retention_cron.xml',
    ],
    'installable': True,
    'application': False,
    'license': 'LGPL-3',
}
