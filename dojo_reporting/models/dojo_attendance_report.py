# -*- coding: utf-8 -*-
"""
dojo_attendance_report.py
--------------------------
Flattened attendance fact table (SQL view) for pivot / graph analysis.
Each row = one class session × one attended member.
"""

from odoo import fields, models, tools


class DojoAttendanceReport(models.Model):
    _name = 'dojo.attendance.report'
    _description = 'Attendance Analytics'
    _auto = False
    _rec_name = 'session_date'
    _order = 'session_date desc'

    session_date = fields.Date(string='Session Date', readonly=True)
    day_of_week = fields.Char(string='Day of Week', readonly=True)
    session_id = fields.Many2one('disaster.class.session', string='Session', readonly=True)
    member_id = fields.Many2one('res.partner', string='Member', readonly=True)
    belt_rank = fields.Char(string='Belt Rank', readonly=True)
    member_stage = fields.Char(string='Member Stage', readonly=True)
    checkin_dt = fields.Datetime(string='Check-in', readonly=True)
    checkout_dt = fields.Datetime(string='Check-out', readonly=True)
    duration_min = fields.Float(string='Duration (min)', readonly=True)
    source = fields.Char(string='Source', readonly=True)

    def init(self):
        tools.drop_view_if_exists(self.env.cr, self._table)
        self.env.cr.execute("""
            CREATE OR REPLACE VIEW dojo_attendance_report AS (
                SELECT
                    r.id                                           AS id,
                    s.session_date                                 AS session_date,
                    TO_CHAR(s.session_date, 'Day')                AS day_of_week,
                    r.session_id                                   AS session_id,
                    r.member_id                                    AS member_id,
                    p.belt_rank                                    AS belt_rank,
                    p.member_stage                                 AS member_stage,
                    r.checkin_dt                                   AS checkin_dt,
                    r.checkout_dt                                  AS checkout_dt,
                    ROUND(
                        EXTRACT(EPOCH FROM (r.checkout_dt - r.checkin_dt)) / 60.0, 1
                    )                                              AS duration_min,
                    r.source                                       AS source
                FROM dojo_session_roster r
                JOIN disaster_class_session s ON s.id = r.session_id
                JOIN res_partner p            ON p.id = r.member_id
                WHERE r.state = 'attended'
            )
        """)
