# -*- coding: utf-8 -*-
"""
class_attendance.py
-------------------
Records one member's attendance at one session.
On creation: increments partner.attendance_count.
On deletion:  decrements partner.attendance_count.
"""

from odoo import api, fields, models
from odoo.exceptions import ValidationError


class DisasterClassAttendance(models.Model):
    _name = 'disaster.class.attendance'
    _description = 'Class Attendance Record'
    _order = 'check_in desc'
    _rec_name = 'partner_id'

    session_id = fields.Many2one(
        comodel_name='disaster.class.session',
        string='Session',
        required=True,
        ondelete='cascade',
        index=True,
    )
    partner_id = fields.Many2one(
        comodel_name='res.partner',
        string='Member',
        required=True,
        index=True,
        domain="[('is_member', '=', True)]",
    )
    check_in = fields.Datetime(
        string='Check In',
        default=fields.Datetime.now,
        required=True,
    )
    check_out = fields.Datetime(
        string='Check Out',
    )
    belt_rank_at_checkin = fields.Selection(
        selection=[
            ('white', 'White'), ('yellow', 'Yellow'), ('orange', 'Orange'),
            ('green', 'Green'), ('blue', 'Blue'), ('purple', 'Purple'),
            ('brown', 'Brown'), ('red', 'Red'), ('black', 'Black'),
        ],
        string='Belt Rank at Check-in',
        readonly=True,
    )
    notes = fields.Char(string='Notes')

    # Denormalised for quick reporting
    session_date = fields.Datetime(
        related='session_id.date_start',
        store=True,
        string='Session Date',
    )
    class_type = fields.Selection(
        related='session_id.class_type',
        store=True,
        string='Class Type',
    )

    _sql_constraints = [
        ('unique_attendance',
         'UNIQUE(session_id, partner_id)',
         'This member is already checked in for this session.'),
    ]

    # ------------------------------------------------------------------
    # Constraints
    # ------------------------------------------------------------------
    @api.constrains('session_id', 'partner_id')
    def _check_session_not_cancelled(self):
        for rec in self:
            if rec.session_id.state == 'cancelled':
                raise ValidationError(
                    'Cannot check in a member to a cancelled session.'
                )

    # ------------------------------------------------------------------
    # ORM overrides — maintain partner.attendance_count
    # ------------------------------------------------------------------
    @api.model_create_multi
    def create(self, vals_list):
        records = super().create(vals_list)
        for rec in records:
            # Snapshot belt rank at time of check-in
            rec.belt_rank_at_checkin = rec.partner_id.belt_rank
            # Increment attendance on the partner
            rec.partner_id.sudo().attendance_count += 1
        return records

    def unlink(self):
        # Decrement attendance before deletion
        for rec in self:
            if rec.partner_id.attendance_count > 0:
                rec.partner_id.sudo().attendance_count -= 1
        return super().unlink()
