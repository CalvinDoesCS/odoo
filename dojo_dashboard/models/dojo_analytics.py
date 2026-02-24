# -*- coding: utf-8 -*-
"""
dojo_analytics.py
-----------------
Adds get_dojo_analytics() to res.partner so any logged-in user
(including Instructors) can call it via JSON-RPC.
All queries use sudo() so record-level rules don't block results.

IMPORTANT: Every optional query is wrapped in self.env.cr.savepoint() so that
a missing table / model does NOT abort the PostgreSQL transaction and poison
all subsequent queries in the same RPC call.
"""

import logging
from datetime import date, timedelta

from odoo import api, models

_logger = logging.getLogger(__name__)


class ResPartnerDojoAnalytics(models.Model):
    _inherit = 'res.partner'

    @api.model
    def get_dojo_analytics(self):
        """
        Returns dojo-specific KPIs for the analytics panel.
        Each optional query that may reference a non-existent model/table is
        isolated in a savepoint so a SQL error cannot abort the transaction.
        """
        today = date.today()
        month_start = today.replace(day=1)
        d30 = today - timedelta(days=30)
        d7 = today - timedelta(days=7)
        env = self.env

        # ── Member counts (core model — always present) ──────────────────
        active_members = env['res.partner'].sudo().search_count([
            ('is_member', '=', True), ('member_stage', '=', 'active'),
        ])
        trial_members = env['res.partner'].sudo().search_count([
            ('is_member', '=', True), ('member_stage', '=', 'trial'),
        ])
        inactive_members = env['res.partner'].sudo().search_count([
            ('is_member', '=', True), ('member_stage', '=', 'inactive'),
        ])

        # ── New contacts / web visits ────────────────────────────────────
        new_contacts_month = 0
        try:
            with env.cr.savepoint():
                new_contacts_month = env['crm.lead'].sudo().search_count([
                    ('create_date', '>=', str(month_start)),
                ])
        except Exception as e:
            _logger.debug("[dojo_analytics] crm.lead query skipped: %s", e)

        web_visits_month = new_contacts_month  # default proxy
        try:
            with env.cr.savepoint():
                web_visits_month = env['website.visitor'].sudo().search_count([
                    ('create_date', '>=', str(month_start)),
                ])
        except Exception as e:
            _logger.debug("[dojo_analytics] website.visitor query skipped: %s", e)

        # ── Session attendance ────────────────────────────────────────────
        attendance_30d = 0
        attendance_7d = 0
        try:
            with env.cr.savepoint():
                attendance_30d = env['dojo.session.roster'].sudo().search_count([
                    ('state', '=', 'attended'),
                    ('checkin_dt', '>=', str(d30)),
                ])
                attendance_7d = env['dojo.session.roster'].sudo().search_count([
                    ('state', '=', 'attended'),
                    ('checkin_dt', '>=', str(d7)),
                ])
        except Exception as e:
            _logger.debug("[dojo_analytics] dojo.session.roster query skipped: %s", e)

        if not attendance_30d:
            try:
                with env.cr.savepoint():
                    # disaster.class.attendance uses 'check_in' (datetime) field
                    attendance_30d = env['disaster.class.attendance'].sudo().search_count([
                        ('check_in', '>=', str(d30)),
                    ])
                    attendance_7d = env['disaster.class.attendance'].sudo().search_count([
                        ('check_in', '>=', str(d7)),
                    ])
            except Exception as e:
                _logger.debug("[dojo_analytics] disaster.class.attendance query skipped: %s", e)

        # ── Memberships ───────────────────────────────────────────────────
        new_memberships_month = 0
        updated_memberships_month = 0
        renewal_month = 0
        try:
            with env.cr.savepoint():
                new_memberships_month = env['disaster.member.contract'].sudo().search_count([
                    ('create_date', '>=', str(month_start)),
                ])
                updated_memberships_month = env['disaster.member.contract'].sudo().search_count([
                    ('state', 'in', ['active', 'trial']),
                    ('write_date', '>=', str(month_start)),
                    ('create_date', '<', str(month_start)),
                ])
                renewal_month = env['disaster.member.contract'].sudo().search_count([
                    ('state', '=', 'active'),
                    ('date_start', '>=', str(month_start)),
                    ('create_date', '<', str(month_start)),
                ])
        except Exception as e:
            _logger.debug("[dojo_analytics] disaster.member.contract query skipped: %s", e)

        # ── Billing ───────────────────────────────────────────────────────
        net_billing = 0.0
        month_income = 0.0
        expected_income = 0.0
        try:
            with env.cr.savepoint():
                posted = env['account.move'].sudo().search([
                    ('move_type', 'in', ['out_invoice', 'out_refund']),
                    ('invoice_date', '>=', str(month_start)),
                    ('state', '=', 'posted'),
                ])
                net_billing = sum(
                    (inv.amount_untaxed if inv.move_type == 'out_invoice'
                     else -inv.amount_untaxed)
                    for inv in posted
                )
                month_income = sum(
                    inv.amount_total for inv in posted
                    if inv.move_type == 'out_invoice'
                )
                all_inv = env['account.move'].sudo().search([
                    ('move_type', '=', 'out_invoice'),
                    ('invoice_date', '>=', str(month_start)),
                    ('state', 'in', ['draft', 'posted']),
                ])
                expected_income = sum(inv.amount_total for inv in all_inv)
        except Exception as e:
            _logger.debug("[dojo_analytics] account.move query skipped: %s", e)

        # ── Appointments ──────────────────────────────────────────────────
        trial_appts = 0
        update_appts = 0
        try:
            with env.cr.savepoint():
                trial_appts = env['crm.lead'].sudo().search_count([
                    ('type', '=', 'lead'),
                    ('active', '=', True),
                ])
        except Exception as e:
            _logger.debug("[dojo_analytics] crm.lead appts query skipped: %s", e)

        try:
            with env.cr.savepoint():
                update_appts = env['mail.activity'].sudo().search_count([
                    ('date_deadline', '<=', str(today)),
                    ('res_model', 'in', [
                        'res.partner',
                        'disaster.member.contract',
                        'crm.lead',
                    ]),
                ])
        except Exception as e:
            _logger.debug("[dojo_analytics] mail.activity query skipped: %s", e)

        # ── Payment gateway ───────────────────────────────────────────────
        has_payment_gateway = False
        try:
            with env.cr.savepoint():
                pg = env['payment.provider'].sudo().search(
                    [('state', '=', 'enabled')], limit=1
                )
                has_payment_gateway = bool(pg)
        except Exception as e:
            _logger.debug("[dojo_analytics] payment.provider query skipped: %s", e)

        currency_symbol = env.company.currency_id.symbol or '$'

        return {
            # Members
            'active_members': active_members,
            'trial_members': trial_members,
            'inactive_members': inactive_members,
            # Leads / web
            'new_contacts_month': new_contacts_month,
            'web_visits_month': web_visits_month,
            # Attendance
            'attendance_7d': attendance_7d,
            'attendance_30d': attendance_30d,
            # Memberships
            'new_memberships_month': new_memberships_month,
            'updated_memberships_month': updated_memberships_month,
            'renewal_month': renewal_month,
            # Billing
            'net_billing': round(net_billing, 2),
            'month_income': round(month_income, 2),
            'expected_income': round(expected_income, 2),
            # Appointments
            'trial_appts': trial_appts,
            'update_appts': update_appts,
            # Health
            'has_payment_gateway': has_payment_gateway,
            'currency_symbol': currency_symbol,
        }
