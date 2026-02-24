# -*- coding: utf-8 -*-
{
    'name': 'Dojo Announcements',
    'summary': 'Announcements, audience segmentation, push device registry and push notification stubs',
    'description': """
Dojo Announcements
==================
Extends disaster_member_belts announcements with:
- Enhanced audience targeting (stored domain filter)
- Multi-channel dispatch: push / email / SMS / in-app
- Push device registry (dojo.push.device) for APNS/FCM tokens
- Publish-now / schedule for future / expire actions
    """,
    'version': '19.0.2.0.0',
    'category': 'Membership',
    'author': 'Dojo Manager',
    'license': 'LGPL-3',
    'application': True,
    'depends': ['disaster_member_belts', 'sms'],
    'data': [
        'security/ir.model.access.csv',
        'views/dojo_push_device_views.xml',
        'views/announcement_ext_views.xml',
        'views/menus.xml',
    ],
    'installable': True,
    'auto_install': False,
}
