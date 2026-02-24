# -*- coding: utf-8 -*-
{
    'name': 'Dojo Manager – Member & Belt System',
    'version': '19.0.3.0.0',
    'summary': 'Core membership management: belt ranks, contracts, billing, leads – Spark Membership inspired',
    'description': """
Dojo Manager (Core)
===================
The base module for the Spark-Membership-style dojo management system, built on Odoo 19.

Features
--------
- Member profiles with stage tracking (Lead → Trial → Active → Inactive)
- Belt rank progression: White → Yellow → Orange → Green → Blue → Purple → Brown → Red → Black
- Per-rank attendance thresholds (configurable)
- Belt promotion wizard with chatter logging
- "Ready for Test" auto-flag when threshold is reached
- Membership plans (billing cycle, price, duration)
- Member contracts (Draft → Trial → Active → Expired/Cancelled)
- Automated contract expiry check + 7-day renewal reminders (daily cron)
- Leads / Trial pipeline (CRM-style prospect management)
- Front-desk sales (point-of-sale style)
- Belt tests management
- Billing invoices
- Broadcast messaging (SMS/email to all members)
- Announcements / Events (displayed on portal between check-ins)
- Guardian / parent safety notifications
- Portal access for members
- HR Attendance bridge (kiosk employee sync)
- Twilio VoIP integration
- Spark CSV data import wizard

Sub-modules (install separately as needed)
------------------------------------------
- dojo_courses  – Course / Program management with enrolment
- dojo_classes  – Class schedules, sessions, attendance, roster
    """,
    'author': 'Custom Dev',
    'category': 'Membership',
    'license': 'LGPL-3',
    'depends': ['base', 'mail', 'web', 'portal', 'account', 'crm', 'product', 'sms', 'hr', 'hr_attendance', 'sms_twilio'],
    'data': [
        'security/groups.xml',
        'security/ir.model.access.csv',
        'data/belt_rank_config_data.xml',
        'data/hr_departments.xml',
        'data/cron_data.xml',
        # 'data/sample_data.xml',  # skip: users may already exist in DB
        'views/belt_rank_config_views.xml',
        'views/promote_wizard_views.xml',
        'views/membership_plan_views.xml',
        'views/member_contract_views.xml',
        'views/res_partner_views.xml',
        'views/instructor_views.xml',
        'views/course_views.xml',
        'views/class_schedule_views.xml',
        'views/class_session_views.xml',
        'views/class_attendance_views.xml',
        'views/attendance_roster_views.xml',
        'views/checkin_wizard_views.xml',
        'views/member_badge_report.xml',
        'views/lead_views.xml',
        'views/billing_invoice_views.xml',
        'views/belt_test_views.xml',
        'views/dojo_sale_views.xml',
        'views/broadcast_wizard_views.xml',
        'views/hr_instructor_views.xml',
        'views/twilio_config_views.xml',
        'views/spark_migration_wizard_views.xml',
        'views/announcement_views.xml',
        'views/menus.xml',
        'views/menu_visibility.xml',
        'views/portal_templates.xml',
    ],
    'assets': {
        'web.assets_backend': [
            'disaster_member_belts/static/src/css/belt_rank.css',
        ],
        'web.assets_frontend': [
            'disaster_member_belts/static/src/css/portal_member.css',
        ],
    },
    'installable': True,
    'application': True,
    'auto_install': False,
}
