# -*- coding: utf-8 -*-
"""
class_session_ext.py
--------------------
Extends disaster.class.session with roster management fields.

Roster auto-population:
  1. Members enrolled in the session's Course (disaster.course.enrolled_member_ids)
  2. Members whose active contract references this session's course/schedule
  3. All active/trial members (last resort — session has no course)

Sync runs automatically on session creation and can be triggered manually
via the "Sync Roster" button on the session form.
"""

import logging
from odoo import api, fields, models, _

_logger = logging.getLogger(__name__)


class ClassSessionDojoExt(models.Model):
    _inherit = 'disaster.class.session'

    roster_ids = fields.One2many(
        'dojo.session.roster', 'session_id', string='Roster',
    )
    booked_count = fields.Integer(
        string='Booked', compute='_compute_roster_counts', store=True,
    )
    waitlist_count = fields.Integer(
        string='Waitlisted', compute='_compute_roster_counts', store=True,
    )
    attended_count = fields.Integer(
        string='Attended', compute='_compute_roster_counts', store=True,
    )
    capacity_remaining = fields.Integer(
        string='Spots Remaining', compute='_compute_capacity_remaining',
    )
    is_full = fields.Boolean(
        string='Session Full', compute='_compute_capacity_remaining',
    )

    @api.depends('roster_ids', 'roster_ids.state')
    def _compute_roster_counts(self):
        for rec in self:
            rec.booked_count = len(rec.roster_ids.filtered(lambda r: r.state == 'booked'))
            rec.waitlist_count = len(rec.roster_ids.filtered(lambda r: r.state == 'waitlisted'))
            rec.attended_count = len(rec.roster_ids.filtered(lambda r: r.state == 'attended'))

    @api.depends('capacity', 'booked_count')
    def _compute_capacity_remaining(self):
        for rec in self:
            if rec.capacity:
                remaining = rec.capacity - rec.booked_count
                rec.capacity_remaining = max(0, remaining)
                rec.is_full = remaining <= 0
            else:
                rec.capacity_remaining = 999
                rec.is_full = False

    # ── Roster population ────────────────────────────────────────────────────

    def _get_expected_members(self):
        """
        Return the recordset of res.partner who are expected at this session.

        Priority:
          1. Members enrolled in the session's Course
          2. Members with an active contract linked to this session's course
          3. All active/trial members (fallback when no course is set)
        """
        self.ensure_one()
        partners = self.env['res.partner'].browse()

        # 1. Course enrollments
        if self.course_id and self.course_id.enrolled_member_ids:
            partners = self.course_id.enrolled_member_ids.filtered(
                lambda p: p.is_member
            )

        # 2. Contracts linked to this course (top-up if not already covered)
        if self.course_id:
            contract_members = self.env['disaster.member.contract'].sudo().search([
                ('course_id', '=', self.course_id.id),
                ('state', 'in', ['active', 'trial']),
            ]).mapped('partner_id').filtered(lambda p: p.is_member)
            partners = partners | contract_members

        # 3. Fallback: all active/trial members
        if not partners:
            partners = self.env['res.partner'].search([
                ('is_member', '=', True),
                ('member_stage', 'in', ['active', 'trial']),
            ])

        return partners

    def action_sync_roster(self):
        """
        Ensure every expected member has a roster entry for this session.
        - Members NOT yet in the roster → add with state 'booked'
        - Members already in roster     → left unchanged (preserves check-in state)
        - Cancelled/no-show entries     → left unchanged
        Returns a client notification with a count of new entries added.
        """
        self.ensure_one()
        expected = self._get_expected_members()

        # Get IDs already in the roster (any state)
        existing_ids = set(self.roster_ids.mapped('member_id').ids)

        added = 0
        vals_list = []
        for partner in expected.filtered(lambda p: p.id not in existing_ids):
            vals_list.append({
                'session_id': self.id,
                'member_id': partner.id,
                'state': 'booked',
                'source': 'staff',
            })

        if vals_list:
            self.env['dojo.session.roster'].create(vals_list)
            added = len(vals_list)
            _logger.info(
                "[dojo_attendance] Synced %d member(s) into roster for session %s",
                added, self.display_name,
            )

        msg = _('%d member(s) added to roster.', added) if added else _('Roster already up to date.')
        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {
                'title': _('Roster Synced'),
                'message': msg,
                'type': 'success' if added else 'info',
                'sticky': False,
            },
        }

    @api.model_create_multi
    def create(self, vals_list):
        """Auto-populate roster from course enrollments on creation."""
        records = super().create(vals_list)
        for rec in records:
            if rec.course_id:
                try:
                    rec.action_sync_roster()
                except Exception as e:
                    _logger.warning(
                        "[dojo_attendance] Auto-sync roster failed for session %s: %s",
                        rec.id, e,
                    )
        return records

    def write(self, vals):
        """Re-sync roster when course changes on an existing session."""
        result = super().write(vals)
        if 'course_id' in vals:
            for rec in self:
                if rec.course_id:
                    try:
                        rec.action_sync_roster()
                    except Exception as e:
                        _logger.warning(
                            "[dojo_attendance] Auto-sync roster on course change failed: %s", e
                        )
        return result

    def action_view_roster(self):
        self.ensure_one()
        # Auto-sync before opening so the list is always current
        self.action_sync_roster()
        return {
            'type': 'ir.actions.act_window',
            'name': _('Roster – %s') % self.name,
            'res_model': 'dojo.session.roster',
            'view_mode': 'list,form',
            'domain': [('session_id', '=', self.id)],
            'context': {'default_session_id': self.id},
        }

    def action_book_member(self):
        """Staff-initiated booking for this session (opens new roster form)."""
        self.ensure_one()
        return {
            'type': 'ir.actions.act_window',
            'name': _('Book Member'),
            'res_model': 'dojo.session.roster',
            'view_mode': 'form',
            'target': 'new',
            'context': {
                'default_session_id': self.id,
                'default_source': 'staff',
            },
        }
