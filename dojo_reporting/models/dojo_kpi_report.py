# -*- coding: utf-8 -*-
"""
dojo_kpi_report.py
------------------
Transient wizard that computes high-level KPIs and exposes them as fields
for a dashboard-style form view.
"""

from odoo import api, fields, models


class DojoKpiReport(models.TransientModel):
    _name = 'dojo.kpi.report'
    _description = 'Dojo KPI Dashboard'

    company_id = fields.Many2one(
        'res.company', string='Dojo', default=lambda self: self.env.company,
    )
    date_from = fields.Date(string='From', required=True,
                            default=lambda self: fields.Date.subtract(fields.Date.today(), days=30))
    date_to = fields.Date(string='To', required=True, default=fields.Date.today)

    # ── KPI output fields (computed on refresh) ───────────────────────────────
    total_active_members = fields.Integer(string='Active Members', readonly=True)
    total_trial_members = fields.Integer(string='Trial Members', readonly=True)
    total_inactive_members = fields.Integer(string='Inactive Members', readonly=True)
    new_members_period = fields.Integer(string='New Members (period)', readonly=True)
    churned_members_period = fields.Integer(string='Churned (period)', readonly=True)

    total_checkins_period = fields.Integer(string='Check-ins (period)', readonly=True)
    avg_checkins_per_member = fields.Float(string='Avg Check-ins / Member', readonly=True, digits=(10, 1))
    sessions_held_period = fields.Integer(string='Sessions Held (period)', readonly=True)

    contracts_on_hold = fields.Integer(string='Contracts On Hold', readonly=True)
    contracts_past_due = fields.Integer(string='Contracts Past Due', readonly=True)

    promotions_period = fields.Integer(string='Promotions (period)', readonly=True)

    @api.model
    def default_get(self, fields_list):
        res = super().default_get(fields_list)
        return res

    def action_refresh(self):
        """Recompute KPIs and reload the form."""
        self.ensure_one()
        Partner = self.env['res.partner']
        Roster = self.env['dojo.session.roster']
        Session = self.env['disaster.class.session']
        Contract = self.env['disaster.member.contract']
        RankHistory = self.env['dojo.rank.history']

        df = self.date_from
        dt = self.date_to

        # Member counts
        self.total_active_members = Partner.search_count(
            [('is_member', '=', True), ('member_stage', '=', 'active')]
        )
        self.total_trial_members = Partner.search_count(
            [('is_member', '=', True), ('member_stage', '=', 'trial')]
        )
        self.total_inactive_members = Partner.search_count(
            [('is_member', '=', True), ('member_stage', '=', 'inactive')]
        )

        # New / churned in period (uses write_date as proxy — ideal would be a state log)
        self.new_members_period = Partner.search_count([
            ('is_member', '=', True),
            ('member_stage', '=', 'active'),
            ('create_date', '>=', df),
            ('create_date', '<=', dt),
        ])

        # Check-ins in period
        self.total_checkins_period = Roster.search_count([
            ('state', '=', 'attended'),
            ('checkin_dt', '>=', str(df)),
            ('checkin_dt', '<=', str(dt) + ' 23:59:59'),
        ])

        self.sessions_held_period = Session.search_count([
            ('session_date', '>=', df),
            ('session_date', '<=', dt),
            ('state', '=', 'done'),
        ])

        active_members = self.total_active_members
        self.avg_checkins_per_member = (
            self.total_checkins_period / active_members if active_members else 0.0
        )

        # Contract health
        self.contracts_on_hold = Contract.search_count([('dojo_on_hold', '=', True)])
        self.contracts_past_due = Contract.search_count([('dojo_past_due', '=', True)])

        # Promotions
        self.promotions_period = RankHistory.search_count([
            ('awarded_dt', '>=', df),
            ('awarded_dt', '<=', dt),
        ])

        return {
            'type': 'ir.actions.act_window',
            'res_model': 'dojo.kpi.report',
            'res_id': self.id,
            'view_mode': 'form',
            'target': 'current',
        }
