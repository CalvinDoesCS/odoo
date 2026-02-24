{
    'name': 'Dojo Automations',
    'summary': 'Automation rule builder: triggers, sequences, webhooks and tag actions',
    'description': """
Dojo Automations
================
Visual automation rule builder tightly integrated with Odoo activities:
- Triggers: membership events, check-in, belt test, custom
- Actions: tag, email, SMS, push notification, webhook, create activity
- Domain filters for targeted execution
- Webhook action with configurable URL, headers and payload template
    """,
    'version': '19.0.1.0.0',
    'category': 'Membership',
    'author': 'Dojo Manager',
    'license': 'LGPL-3',
    'application': True,
    'depends': ['disaster_member_belts', 'dojo_announcements'],
    'data': [
        'security/ir.model.access.csv',
        'views/dojo_automation_rule_views.xml',
        'views/menus.xml',
    ],
    'installable': True,
    'auto_install': False,
}
