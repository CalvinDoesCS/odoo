# -*- coding: utf-8 -*-
"""
dojo_cohort_report.py
---------------------
Cohort retention analysis: members grouped by join-month,
showing % still active at 30 / 60 / 90 / 180 days.

Exposed as a read-only reporting model (SQL view).
"""

from odoo import fields, models, tools


class DojoCohortReport(models.Model):
    _name = 'dojo.cohort.report'
    _description = 'Member Cohort Retention'
    _auto = False
    _rec_name = 'cohort_month'
    _order = 'cohort_month desc'

    cohort_month = fields.Char(string='Cohort Month', readonly=True)
    cohort_size = fields.Integer(string='Members Joined', readonly=True)
    active_30 = fields.Integer(string='Active @ 30 days', readonly=True)
    active_60 = fields.Integer(string='Active @ 60 days', readonly=True)
    active_90 = fields.Integer(string='Active @ 90 days', readonly=True)
    active_180 = fields.Integer(string='Active @ 180 days', readonly=True)
    retention_30 = fields.Float(string='Retention 30d %', readonly=True, digits=(5, 1))
    retention_90 = fields.Float(string='Retention 90d %', readonly=True, digits=(5, 1))
    retention_180 = fields.Float(string='Retention 180d %', readonly=True, digits=(5, 1))

    def init(self):
        tools.drop_view_if_exists(self.env.cr, self._table)
        self.env.cr.execute("""
            CREATE OR REPLACE VIEW dojo_cohort_report AS (
                SELECT
                    TO_CHAR(DATE_TRUNC('month', p.create_date), 'YYYY-MM') AS id,
                    TO_CHAR(DATE_TRUNC('month', p.create_date), 'YYYY-MM')  AS cohort_month,
                    COUNT(*)                                                  AS cohort_size,
                    COUNT(*) FILTER (WHERE
                        p.member_stage = 'active'
                        AND p.create_date <= NOW() - INTERVAL '30 days'
                    )                                                         AS active_30,
                    COUNT(*) FILTER (WHERE
                        p.member_stage = 'active'
                        AND p.create_date <= NOW() - INTERVAL '60 days'
                    )                                                         AS active_60,
                    COUNT(*) FILTER (WHERE
                        p.member_stage = 'active'
                        AND p.create_date <= NOW() - INTERVAL '90 days'
                    )                                                         AS active_90,
                    COUNT(*) FILTER (WHERE
                        p.member_stage = 'active'
                        AND p.create_date <= NOW() - INTERVAL '180 days'
                    )                                                         AS active_180,
                    ROUND(
                        100.0 * COUNT(*) FILTER (WHERE
                            p.member_stage = 'active'
                            AND p.create_date <= NOW() - INTERVAL '30 days'
                        ) / NULLIF(COUNT(*) FILTER (
                            WHERE p.create_date <= NOW() - INTERVAL '30 days'
                        ), 0), 1
                    )                                                         AS retention_30,
                    ROUND(
                        100.0 * COUNT(*) FILTER (WHERE
                            p.member_stage = 'active'
                            AND p.create_date <= NOW() - INTERVAL '90 days'
                        ) / NULLIF(COUNT(*) FILTER (
                            WHERE p.create_date <= NOW() - INTERVAL '90 days'
                        ), 0), 1
                    )                                                         AS retention_90,
                    ROUND(
                        100.0 * COUNT(*) FILTER (WHERE
                            p.member_stage = 'active'
                            AND p.create_date <= NOW() - INTERVAL '180 days'
                        ) / NULLIF(COUNT(*) FILTER (
                            WHERE p.create_date <= NOW() - INTERVAL '180 days'
                        ), 0), 1
                    )                                                         AS retention_180
                FROM res_partner p
                WHERE p.is_member = TRUE
                GROUP BY DATE_TRUNC('month', p.create_date)
            )
        """)
