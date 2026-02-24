{
    'name': 'Dojo Attendance',
    'summary': 'Session roster, booking/waitlist, check-in states and guardian notifications',
    'description': """
Dojo Attendance
===============
Extends dojo_classes with a full roster system:
- dojo.session.roster – per-member booking on a session with states:
  booked / waitlisted / attended / no_show / cancelled
- Capacity enforcement + waitlist auto-promotion
- Booking source tracking (member_app / kiosk / staff / manual)
- Guardian absence notification hooks
    """,
    'version': '19.0.2.0.0',
    'category': 'Membership',
    'author': 'Dojo Manager',
    'license': 'LGPL-3',
    'application': True,
    'depends': ['disaster_member_belts', 'dojo_classes'],
    'data': [
        'security/ir.model.access.csv',
        'views/dojo_session_roster_views.xml',
        'views/session_ext_views.xml',
        'views/menus.xml',
    ],
    'installable': True,
    'auto_install': False,
}
