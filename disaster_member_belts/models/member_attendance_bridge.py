# -*- coding: utf-8 -*-
"""
member_attendance_bridge.py
---------------------------
Two responsibilities:

1.  res.partner (member) → hr.employee shadow record
    -------------------------------------------------
    Each student member can have a shadow hr.employee (department: Students)
    so they can clock in/out using the standard Odoo Attendance kiosk.

    Button on the member form creates / syncs the employee.
    Changes to name, email, phone, photo are kept in sync automatically.

2.  hr.attendance → disaster.class.attendance bridge
    -------------------------------------------------
    When a student's hr.attendance check-in is created:
      • Find the nearest active (or upcoming, within 45 min) class session
      • Auto-create a disaster.class.attendance record for that member+session

    When check_out is set on hr.attendance:
      • Propagate it to the linked disaster.class.attendance record
"""

import logging
from datetime import timedelta

from odoo import api, fields, models

_logger = logging.getLogger(__name__)


# ──────────────────────────────────────────────────────────────────────────────
# res.partner extension – member_employee_id + sync helpers
# ──────────────────────────────────────────────────────────────────────────────

class ResPartnerMemberBridge(models.Model):
    _inherit = 'res.partner'

    member_employee_id = fields.Many2one(
        comodel_name='hr.employee',
        string='Attendance Employee',
        copy=False,
        ondelete='set null',
        help='Shadow HR employee used for Odoo clock-in/clock-out. '
             'Created via the "Create Attendance Employee" button.',
    )

    # ------------------------------------------------------------------
    # Sync helpers
    # ------------------------------------------------------------------

    def _get_students_department(self):
        """Return (and lazily create) the Students hr.department."""
        dept = self.env.ref(
            'disaster_member_belts.hr_dept_students', raise_if_not_found=False
        )
        if not dept:
            dept = self.env['hr.department'].search(
                [('name', '=', 'Students')], limit=1
            )
        if not dept:
            dept = self.env['hr.department'].create({'name': 'Students'})
        return dept

    # ------------------------------------------------------------------
    # Button actions
    # ------------------------------------------------------------------

    def action_sync_member_employee(self):
        """Create or re-sync the shadow hr.employee for this member."""
        self.ensure_one()
        dept = self._get_students_department()

        if self.member_employee_id:
            self.member_employee_id.sudo().write({
                'name':             self.name,
                'work_contact_id':  self.id,
                'work_email':       self.email or '',
                'work_phone':       self.phone or '',
                'department_id':    dept.id,
                'image_1920':       self.image_1920,
            })
            return {
                'type': 'ir.actions.client',
                'tag': 'display_notification',
                'params': {
                    'title': '✅ Employee Synced',
                    'message': f'{self.name} — attendance employee profile updated.',
                    'type': 'success',
                },
            }

        emp = self.env['hr.employee'].sudo().create({
            'name':             self.name,
            'work_contact_id':  self.id,
            'work_email':       self.email or '',
            'work_phone':       self.phone or '',
            'job_title':        'Dojo Student',
            'department_id':    dept.id,
            'image_1920':       self.image_1920,
        })
        self.member_employee_id = emp
        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {
                'title': '✅ Employee Created',
                'message': f'{self.name} — attendance employee profile created.',
                'type': 'success',
            },
        }

    # ------------------------------------------------------------------
    # ORM – keep employee in sync when partner fields change
    # ------------------------------------------------------------------

    def write(self, vals):
        result = super().write(vals)
        sync_map = {
            'name':       'name',
            'email':      'work_email',
            'phone':      'work_phone',
            'image_1920': 'image_1920',
        }
        emp_vals = {
            emp_field: vals[partner_field]
            for partner_field, emp_field in sync_map.items()
            if partner_field in vals
        }
        if emp_vals:
            for partner in self:
                if partner.member_employee_id:
                    partner.member_employee_id.sudo().write(emp_vals)
        return result


# ──────────────────────────────────────────────────────────────────────────────
# hr.attendance extension – bridge to disaster.class.attendance
# ──────────────────────────────────────────────────────────────────────────────

class HrAttendanceDojoBridge(models.Model):
    _inherit = 'hr.attendance'

    dojo_attendance_id = fields.Many2one(
        comodel_name='disaster.class.attendance',
        string='Dojo Class Attendance',
        copy=False,
        ondelete='set null',
        readonly=True,
        help='Auto-linked disaster.class.attendance record created when this '
             'check-in was matched to an active class session.',
    )

    # ------------------------------------------------------------------
    # Session discovery
    # ------------------------------------------------------------------

    def _find_dojo_session(self, check_in_dt):
        """
        Return the best-match class session for check_in_dt.

        Priority:
          1. Sessions that are currently in-progress (date_start ≤ now ≤ date_end)
          2. Sessions starting within the next 45 minutes (early arrivals)
          3. Sessions that ended at most 15 minutes ago (late clock-ins)
        """
        Session = self.env['disaster.class.session']
        window_ahead = check_in_dt + timedelta(minutes=45)
        window_behind = check_in_dt - timedelta(minutes=15)

        # 1. Ongoing
        session = Session.search([
            ('date_start', '<=', check_in_dt),
            ('date_end',   '>=', check_in_dt),
            ('state',      'in', ['scheduled', 'in_progress']),
        ], limit=1, order='date_start desc')
        if session:
            return session

        # 2. Starting soon
        session = Session.search([
            ('date_start', '>=', check_in_dt),
            ('date_start', '<=', window_ahead),
            ('state',      'in', ['scheduled', 'in_progress']),
        ], limit=1, order='date_start asc')
        if session:
            return session

        # 3. Just ended
        session = Session.search([
            ('date_end',   '>=', window_behind),
            ('date_end',   '<=', check_in_dt),
            ('state',      'in', ['scheduled', 'in_progress', 'done']),
        ], limit=1, order='date_end desc')
        return session

    # ------------------------------------------------------------------
    # ORM overrides
    # ------------------------------------------------------------------

    @api.model_create_multi
    def create(self, vals_list):
        records = super().create(vals_list)
        for attendance in records:
            partner = attendance.employee_id.work_contact_id
            if not partner or not partner.is_member:
                continue

            session = self._find_dojo_session(attendance.check_in)
            if not session:
                _logger.debug(
                    'hr.attendance %s: no active dojo session found for %s',
                    attendance.id, attendance.check_in,
                )
                continue

            # Avoid duplicate attendance records
            existing = self.env['disaster.class.attendance'].search([
                ('session_id', '=', session.id),
                ('partner_id', '=', partner.id),
            ], limit=1)
            if existing:
                attendance.dojo_attendance_id = existing
                _logger.info(
                    'hr.attendance %s linked to existing dojo attendance %s',
                    attendance.id, existing.id,
                )
            else:
                dojo_att = self.env['disaster.class.attendance'].sudo().create({
                    'session_id': session.id,
                    'partner_id': partner.id,
                    'check_in':  attendance.check_in,
                })
                attendance.dojo_attendance_id = dojo_att
                _logger.info(
                    'hr.attendance %s → created dojo attendance %s '
                    '(session %s, member %s)',
                    attendance.id, dojo_att.id, session.id, partner.name,
                )

        return records

    def write(self, vals):
        result = super().write(vals)
        if 'check_out' in vals and vals['check_out']:
            for attendance in self:
                if attendance.dojo_attendance_id and not attendance.dojo_attendance_id.check_out:
                    try:
                        attendance.dojo_attendance_id.sudo().write({
                            'check_out': vals['check_out'],
                        })
                    except Exception as e:
                        _logger.warning(
                            'Could not sync check_out to dojo attendance %s: %s',
                            attendance.dojo_attendance_id.id, e,
                        )
        return result
