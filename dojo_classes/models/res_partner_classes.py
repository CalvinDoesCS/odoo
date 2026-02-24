# -*- coding: utf-8 -*-
"""
res_partner_classes.py
----------------------
Extends res.partner with Class-related fields:
  - attendance_ids           – One2many to disaster.class.attendance
  - session_instructor_ids   – One2many to disaster.class.session (for instructors)
  - sessions_taught_count    – computed count
  - action_view_attendance   – open attendance list
  - action_view_sessions_taught – open sessions taught

Module: dojo_classes
"""

from odoo import api, fields, models


class ResPartnerClasses(models.Model):
    _inherit = 'res.partner'

    # ------------------------------------------------------------------
    # Member – class attendance records
    # ------------------------------------------------------------------
    attendance_ids = fields.One2many(
        comodel_name='disaster.class.attendance',
        inverse_name='partner_id',
        string='Attendance Records',
    )

    # ------------------------------------------------------------------
    # Instructor – sessions they have taught
    # ------------------------------------------------------------------
    session_instructor_ids = fields.One2many(
        comodel_name='disaster.class.session',
        inverse_name='instructor_id',
        string='Sessions Taught',
    )
    sessions_taught_count = fields.Integer(
        string='Sessions Taught',
        compute='_compute_sessions_taught_count',
    )

    @api.depends('session_instructor_ids')
    def _compute_sessions_taught_count(self):
        for p in self:
            p.sessions_taught_count = len(p.session_instructor_ids)

    # ------------------------------------------------------------------
    # Actions
    # ------------------------------------------------------------------
    def action_view_attendance(self):
        """Open the list of class attendance records for this member."""
        self.ensure_one()
        return {
            'type': 'ir.actions.act_window',
            'name': f'Attendance – {self.name}',
            'res_model': 'disaster.class.attendance',
            'view_mode': 'list,form',
            'domain': [('partner_id', '=', self.id)],
            'context': {'default_partner_id': self.id},
        }

    def action_view_sessions_taught(self):
        """Instructor: open list of sessions where they were the instructor."""
        self.ensure_one()
        return {
            'type': 'ir.actions.act_window',
            'name': f'Sessions Taught – {self.name}',
            'res_model': 'disaster.class.session',
            'view_mode': 'list,form',
            'domain': [('instructor_id', '=', self.id)],
        }
