# -*- coding: utf-8 -*-
{
    'name': 'Dojo Manager – Member & Belt System',
    'version': '19.0.2.0.0',
    'summary': 'Full membership management: belt ranks, class sessions, contracts – inspired by Spark Membership',
    'description': """
Dojo Manager
============
A Spark-Membership-style module built on Odoo 19.

Features
--------
- Member profiles with stage tracking (Lead → Trial → Active → Inactive)
- Belt rank progression: White → Yellow → Orange → Green → Blue → Purple → Brown → Red → Black
- Per-rank attendance thresholds (configurable)
- Class sessions: scheduling, capacity, instructor assignment
- Member check-in per session with automatic attendance count increment
- Belt promotion wizard with chatter logging
- "Ready for Test" auto-flag when threshold is reached
- Membership plans (billing cycle, price, duration)
- Member contracts (Draft → Trial → Active → Expired/Cancelled)
- Automated contract expiry check + 7-day renewal reminders (daily cron)
- Smart buttons: Attendances, Contracts on partner form
- Belt rank colour statusbar on partner header
- Kanban badge with belt colour
    """,
    'author': 'Custom Dev',
    'category': 'Membership',
    'license': 'LGPL-3',
    'depends': ['base', 'mail', 'web', 'portal', 'account', 'crm', 'product', 'sms', 'hr'],
    'data': [
        'security/groups.xml',
        'security/ir.model.access.csv',
        'data/belt_rank_config_data.xml',
        'data/cron_data.xml',
        'data/sample_data.xml',
        'views/belt_rank_config_views.xml',
        'views/promote_wizard_views.xml',
        'views/checkin_wizard_views.xml',
        'views/class_schedule_views.xml',
        'views/course_views.xml',
        'views/class_session_views.xml',
        'views/class_attendance_views.xml',
        'views/membership_plan_views.xml',
        'views/member_contract_views.xml',
        'views/instructor_views.xml',
        'views/res_partner_views.xml',
        'views/member_badge_report.xml',
        'views/lead_views.xml',
        'views/billing_invoice_views.xml',
        'views/belt_test_views.xml',
        'views/dojo_sale_views.xml',
        'views/broadcast_wizard_views.xml',
        'views/hr_instructor_views.xml',
        'views/menus.xml',
        'views/menu_visibility.xml',
        'views/portal_templates.xml',
        'views/kiosk_templates.xml',
        'views/kiosk_instructor_template.xml',
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
