# -*- coding: utf-8 -*-
{
    'name': 'Dojo Courses',
    'version': '19.0.1.0.0',
    'summary': 'Course / Program management for dojos – enrolment, belt eligibility, instructor assignment',
    'description': """
Dojo Courses
============
Extracted from the core Dojo Manager module to keep concerns separated.

Features
--------
- Course / Program records (e.g. "Kids Karate – White to Yellow", "Adult BJJ Fundamentals")
- Belt-rank eligibility (min / max rank per course)
- Open vs closed enrolment
- Lead instructor + co-instructors
- Member enrolment many2many
- Absent-student alert threshold per course
- Smart buttons on partner form for enrolled courses and courses led
    """,
    'author': 'Custom Dev',
    'category': 'Membership',
    'license': 'LGPL-3',
    'depends': ['disaster_member_belts'],
    'data': [
        'security/ir.model.access.csv',
        'views/instructor_course_ext_view.xml',
        'views/res_partner_course_view.xml',
        'views/menus.xml',
    ],
    'installable': True,
    'application': True,
    'auto_install': False,
}
