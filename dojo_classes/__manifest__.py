# -*- coding: utf-8 -*-
{
    'name': 'Dojo Classes',
    'version': '19.0.1.0.0',
    'summary': 'Class schedules, sessions, attendance, rosters and check-in for dojos',
    'description': """
Dojo Classes
============
Extracted from the core Dojo Manager module.

Features
--------
- Recurring class schedules (Mon–Sun template, daily cron generates live sessions)
- Class sessions with state machine: Scheduled → In Progress → Done / Cancelled
- Per-session check-in: barcode, PIN, or manual
- Class attendance records with belt-rank snapshot at time of check-in
- Attendance Roster wizard (visual roll-call with photo cards, SMS/email absence alerts)
- Quick Check-In wizard from the session form
- Session eligibility checks against Course belt-rank and enrolment rules
- Absent-student activity creation (cron, threshold per course)
- Instructor smart buttons: Sessions Taught count on partner form
- Member smart button: Attendance count on partner form
    """,
    'author': 'Custom Dev',
    'category': 'Membership',
    'license': 'LGPL-3',
    'depends': ['disaster_member_belts', 'dojo_courses'],
    'data': [
        'security/ir.model.access.csv',
        'data/cron_data.xml',
        'views/instructor_classes_ext_view.xml',
        'views/res_partner_classes_view.xml',
        'views/menus.xml',
    ],
    'installable': True,
    'application': True,
    'auto_install': False,
}
