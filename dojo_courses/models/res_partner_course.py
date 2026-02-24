# -*- coding: utf-8 -*-
"""
res_partner_course.py
---------------------
Extends res.partner with Course-related fields:
  - led_course_ids / led_course_count   (instructor view)
  - enrolled_course_count               (member view)
  - action_view_led_courses
  - action_view_enrolled_courses

Module: dojo_courses
"""

from odoo import api, fields, models


class ResPartnerCourse(models.Model):
    _inherit = 'res.partner'

    # ------------------------------------------------------------------
    # Instructor – courses they lead
    # ------------------------------------------------------------------
    led_course_ids = fields.One2many(
        comodel_name='disaster.course',
        inverse_name='instructor_id',
        string='Courses Led',
    )
    led_course_count = fields.Integer(
        string='Courses Led',
        compute='_compute_led_course_count',
    )

    @api.depends('led_course_ids')
    def _compute_led_course_count(self):
        for p in self:
            p.led_course_count = len(p.led_course_ids)

    # ------------------------------------------------------------------
    # Member – courses they are enrolled in (computed via domain)
    # ------------------------------------------------------------------
    enrolled_course_count = fields.Integer(
        string='Courses',
        compute='_compute_enrolled_course_count',
    )

    def _compute_enrolled_course_count(self):
        Course = self.env['disaster.course']
        for partner in self:
            partner.enrolled_course_count = Course.search_count(
                [('enrolled_member_ids', 'in', [partner.id])]
            )

    # ------------------------------------------------------------------
    # Actions
    # ------------------------------------------------------------------
    def action_view_led_courses(self):
        """Instructor: open list of courses they lead."""
        self.ensure_one()
        return {
            'type': 'ir.actions.act_window',
            'name': f'Courses – {self.name}',
            'res_model': 'disaster.course',
            'view_mode': 'list,form',
            'domain': [('instructor_id', '=', self.id)],
            'context': {'default_instructor_id': self.id},
        }

    def action_view_enrolled_courses(self):
        """Member: open courses they are enrolled in."""
        self.ensure_one()
        return {
            'type': 'ir.actions.act_window',
            'name': f'Courses – {self.name}',
            'res_model': 'disaster.course',
            'view_mode': 'list,form',
            'domain': [('enrolled_member_ids', 'in', [self.id])],
        }
