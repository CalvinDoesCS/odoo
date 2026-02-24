# -*- coding: utf-8 -*-
"""
attendance_roster.py
--------------------
Live Attendance Roster Wizard.

Lets an instructor (or front-desk staff) open a visual roll-call page for any
class session.  Students are displayed as a grid of profile photo cards.
The teacher clicks each card to toggle the student between:
    ✅ Present  →  an attendance record is created for them
    ❌ Absent   →  an SMS and/or email notification is queued to the
                   student's registered parent/guardian

Fall-back enrolment discovery:
    1. Members enrolled in the session's attached Course
    2. Members already checked in (catches ad-hoc walk-ins)
    3. All active / trial members (last resort when no course is set)
"""

import logging
from odoo import api, fields, models

_logger = logging.getLogger(__name__)


class AttendanceRoster(models.TransientModel):
    _name = 'disaster.attendance.roster'
    _description = 'Attendance Roster Wizard'

    # ------------------------------------------------------------------
    # Header
    # ------------------------------------------------------------------
    session_id = fields.Many2one(
        comodel_name='disaster.class.session',
        string='Session',
        required=True,
        readonly=True,
    )
    session_date = fields.Datetime(
        related='session_id.date_start',
        string='Session Date',
        readonly=True,
    )
    instructor_id = fields.Many2one(
        related='session_id.instructor_id',
        string='Instructor',
        readonly=True,
    )
    class_type = fields.Selection(
        related='session_id.class_type',
        string='Class Type',
        readonly=True,
    )

    # ------------------------------------------------------------------
    # Lines
    # ------------------------------------------------------------------
    line_ids = fields.One2many(
        comodel_name='disaster.attendance.roster.line',
        inverse_name='roster_id',
        string='Students',
    )

    # ------------------------------------------------------------------
    # Counters
    # ------------------------------------------------------------------
    total_count = fields.Integer(
        string='Total',
        compute='_compute_counts',
    )
    present_count = fields.Integer(
        string='Present',
        compute='_compute_counts',
    )
    absent_count = fields.Integer(
        string='Absent',
        compute='_compute_counts',
    )

    # ------------------------------------------------------------------
    # State / result
    # ------------------------------------------------------------------
    state = fields.Selection(
        selection=[('draft', 'Taking Roll'), ('done', 'Saved')],
        default='draft',
        readonly=True,
    )
    result_message = fields.Text(
        string='Result',
        readonly=True,
    )
    roster_source = fields.Char(
        string='Student Source',
        readonly=True,
        help='Explains where the roster students were loaded from.',
    )

    # ------------------------------------------------------------------
    # Computed
    # ------------------------------------------------------------------
    @api.depends('line_ids', 'line_ids.status')
    def _compute_counts(self):
        for rec in self:
            lines = rec.line_ids
            rec.total_count = len(lines)
            rec.present_count = len(lines.filtered(lambda l: l.status == 'present'))
            rec.absent_count = len(lines.filtered(lambda l: l.status == 'absent'))

    # ------------------------------------------------------------------
    # Default_get – seed session from context
    # ------------------------------------------------------------------
    @api.model
    def default_get(self, fields_list):
        res = super().default_get(fields_list)
        session_id = self.env.context.get('default_session_id')
        if session_id:
            res['session_id'] = session_id
        return res

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------
    def _get_roster_members(self):
        """
        Return (partner_recordset, source_label).

        Sources (all merged together):
          1. Members in the session's dojo.session.roster (already synced from
             course enrollments + contracts)
          2. Members explicitly enrolled in the session's Course
          3. Members with an active contract linked to the session's course
          4. Members already checked in (walk-ins / kiosk)
          5. Fallback: all active/trial members (when no course is set)
        """
        self.ensure_one()
        session = self.session_id
        partners = self.env['res.partner'].browse()
        sources = []

        # 1. Members already in the session roster (booked / waitlisted / attended)
        try:
            roster_members = self.env['dojo.session.roster'].search([
                ('session_id', '=', session.id),
                ('state', 'not in', ['cancelled']),
            ]).mapped('member_id').filtered(lambda p: p.is_member)
            if roster_members:
                partners = partners | roster_members
                sources.append(f"{len(roster_members)} from session roster")
        except Exception:
            pass

        # 2. Course enrolments (enrolled_member_ids Many2many)
        if session.course_id and session.course_id.enrolled_member_ids:
            course_members = session.course_id.enrolled_member_ids.filtered(
                lambda p: p.is_member
            )
            if course_members:
                partners = partners | course_members
                sources.append(f"enrolled in course \u2018{session.course_id.name}\u2019")

        # 3. Active contracts linked to this course
        if session.course_id:
            try:
                contract_members = self.env['disaster.member.contract'].sudo().search([
                    ('course_id', '=', session.course_id.id),
                    ('state', 'in', ['active', 'trial']),
                ]).mapped('partner_id').filtered(lambda p: p.is_member)
                if contract_members:
                    partners = partners | contract_members
                    sources.append(f"{len(contract_members)} from active contracts")
            except Exception:
                pass

        # 4. Walk-ins already checked in to this session
        walkins = self.env['disaster.class.attendance'].search(
            [('session_id', '=', session.id)]
        ).mapped('partner_id').filtered(lambda p: p.is_member)
        if walkins:
            partners = partners | walkins
            sources.append(f"{len(walkins)} walk-in check-in(s)")

        # 5. Fallback: all active/trial members
        if not partners:
            partners = self.env['res.partner'].search([
                ('is_member', '=', True),
                ('member_stage', 'in', ['trial', 'active']),
            ])
            sources.append("all active/trial members (no course linked)")

        source = "; ".join(sources) if sources else "no students found"
        return partners.filtered(lambda p: p.is_member), source

    # ------------------------------------------------------------------
    # Actions
    # ------------------------------------------------------------------
    def action_load_students(self):
        """(Re)build the roster lines and stay on the wizard."""
        self.ensure_one()
        session = self.session_id
        # Query DB directly — avoids ORM cache returning stale attendance data
        checked_in_ids = set(
            self.env['disaster.class.attendance']
            .search([('session_id', '=', session.id)])
            .mapped('partner_id').ids
        )
        members, source = self._get_roster_members()

        # Wipe existing lines then rebuild
        self.line_ids.unlink()
        vals_list = []
        for partner in members.sorted(lambda p: (p.name or '')):
            vals_list.append({
                'roster_id': self.id,
                'partner_id': partner.id,
                'status': 'present' if partner.id in checked_in_ids else 'absent',
                'already_checked_in': partner.id in checked_in_ids,
            })
        if vals_list:
            self.env['disaster.attendance.roster.line'].create(vals_list)
        self.roster_source = source

        return {
            'type': 'ir.actions.act_window',
            'res_model': 'disaster.attendance.roster',
            'view_mode': 'form',
            'res_id': self.id,
            'target': 'new',
            'context': dict(self.env.context, dialog_size='extra-large'),
        }

    def action_save_roster(self):
        """
        Commit the roll-call:
          • Present students  → create disaster.class.attendance records
                                (skipped if they already have one)
          • Absent  students  → send SMS / email to guardian, post note on partner
        After saving, update the kanban lines in-place so green cards stay green.
        """
        self.ensure_one()
        session = self.session_id
        Attendance = self.env['disaster.class.attendance']

        # Re-query attendance from DB directly to avoid stale ORM cache
        existing_ids = set(
            Attendance.search([('session_id', '=', session.id)])
            .mapped('partner_id').ids
        )

        created = skipped = notified = 0
        result_lines = []
        notified_lines = self.env['disaster.attendance.roster.line']

        # Pass 1: create attendance records for all present students
        for line in self.line_ids:
            partner = line.partner_id
            if line.status == 'present':
                if partner.id not in existing_ids:
                    Attendance.create({
                        'session_id': session.id,
                        'partner_id': partner.id,
                        'check_in': session.date_start or fields.Datetime.now(),
                    })
                    existing_ids.add(partner.id)
                    created += 1
                else:
                    skipped += 1

        # Pass 2: send absence notifications
        for line in self.line_ids:
            if line.status == 'absent':
                sent = self._notify_absence(line.partner_id, session)
                if sent:
                    notified += 1
                    notified_lines |= line

        if notified_lines:
            notified_lines.write({'notification_sent': True})

        result_lines.append(f"{created} new attendance record(s) created.")
        if skipped:
            result_lines.append(f"{skipped} already checked in (skipped).")
        if notified:
            result_lines.append(f"{notified} absence notification(s) sent.")
        absent_no_notify = [
            l.partner_id.name for l in self.line_ids
            if l.status == 'absent' and not l.notification_sent
        ]
        if absent_no_notify:
            result_lines.append(
                "No notification configured for: "
                + ", ".join(absent_no_notify[:10])
                + ("..." if len(absent_no_notify) > 10 else "")
            )

        # Update lines in-place: present students get already_checked_in flag
        # This avoids a fresh DB query and any cache issues.
        for line in self.line_ids:
            if line.status == 'present':
                line.write({'already_checked_in': True})

        self.write({'result_message': '\n'.join(result_lines)})

        return {
            'type': 'ir.actions.act_window',
            'res_model': 'disaster.attendance.roster',
            'view_mode': 'form',
            'res_id': self.id,
            'target': 'new',
            'context': dict(self.env.context, dialog_size='extra-large'),
        }

    def action_save_roster_no_notify(self):
        """
        Commit the roll-call without sending any absence notifications:
          • Present students  → create disaster.class.attendance records
                                (skipped if they already have one)
          • Absent  students  → no SMS / email sent
        """
        self.ensure_one()
        session = self.session_id
        Attendance = self.env['disaster.class.attendance']

        existing_ids = set(
            Attendance.search([('session_id', '=', session.id)])
            .mapped('partner_id').ids
        )

        created = skipped = 0
        result_lines = []

        for line in self.line_ids:
            partner = line.partner_id
            if line.status == 'present':
                if partner.id not in existing_ids:
                    Attendance.create({
                        'session_id': session.id,
                        'partner_id': partner.id,
                        'check_in': session.date_start or fields.Datetime.now(),
                    })
                    existing_ids.add(partner.id)
                    created += 1
                else:
                    skipped += 1

        result_lines.append(f"{created} new attendance record(s) created.")
        if skipped:
            result_lines.append(f"{skipped} already checked in (skipped).")
        result_lines.append("No absence notifications were sent.")

        for line in self.line_ids:
            if line.status == 'present':
                line.write({'already_checked_in': True})

        self.write({'result_message': '\n'.join(result_lines)})

        return {
            'type': 'ir.actions.act_window',
            'res_model': 'disaster.attendance.roster',
            'view_mode': 'form',
            'res_id': self.id,
            'target': 'new',
            'context': dict(self.env.context, dialog_size='extra-large'),
        }

    # ------------------------------------------------------------------
    # Absence notification helper
    # ------------------------------------------------------------------
    def _notify_absence(self, partner, session):
        """
        Dispatch absence alert to the student's guardian via Twilio API.
        Email: sent via mail.mail.
        SMS: sent directly via Twilio Messages REST API.
        Returns True if at least one channel succeeded.
        """
        import requests as _req

        guardian = partner.guardian_id or partner
        student_name = partner.name or 'Your child'
        session_name = session.name or 'class'
        session_date = (
            fields.Datetime.to_string(session.date_start)[:10]
            if session.date_start else 'today'
        )
        dojo_name = session.location or 'the Dojo'

        subject = f"Missed Class - {student_name} - {session_date}"
        body_html = (
            f"<p>Hello,</p>"
            f"<p><strong>{student_name}</strong> was marked <strong>absent</strong> from "
            f"<em>{session_name}</em> on <strong>{session_date}</strong> at {dojo_name}.</p>"
            f"<p>If this is unexpected, please contact us directly.</p>"
            f"<p>Thank you,<br/>The Dojo Team</p>"
        )
        sms_body = (
            f"Dojo: {student_name} was absent from "
            f"'{session_name}' on {session_date}. "
            f"Contact us if unexpected."
        )
        company = self.env.company.sudo()
        twilio_sid = company.sms_twilio_account_sid
        twilio_token = company.sms_twilio_auth_token
        from_number = (
            company.sms_twilio_number_ids[0].number
            if company.sms_twilio_number_ids else None
        )
        sent = False

        # ── Email ─────────────────────────────────────────────────────
        if partner.notify_absence_email and guardian.email:
            try:
                self.env['mail.mail'].sudo().create({
                    'subject': subject,
                    'body_html': body_html,
                    'email_to': guardian.email,
                    'auto_delete': True,
                }).send()
                sent = True
            except Exception as exc:
                _logger.warning("Absence email failed for %s: %s", partner.name, exc)

        # ── SMS via Twilio REST API ────────────────────────────────────
        sms_number = guardian.phone
        if partner.notify_absence_sms and sms_number:
            if twilio_sid and twilio_token and from_number:
                try:
                    url = (
                        f'https://api.twilio.com/2010-04-01/Accounts/'
                        f'{twilio_sid}/Messages.json'
                    )
                    resp = _req.post(
                        url,
                        data={'To': sms_number, 'From': from_number, 'Body': sms_body},
                        auth=(twilio_sid, twilio_token),
                        timeout=10,
                    )
                    resp.raise_for_status()
                    _logger.info(
                        "Absence SMS sent via Twilio for %s -> %s",
                        partner.name, sms_number,
                    )
                    sent = True
                except Exception as exc:
                    _logger.warning(
                        "Twilio absence SMS failed for %s: %s", partner.name, exc
                    )
            else:
                _logger.warning(
                    "Twilio not configured — skipping SMS for %s. "
                    "Set up Twilio in General Settings -> SMS.",
                    partner.name,
                )

        # ── Chatter note on the partner record ────────────────────────
        try:
            note = (
                f"<p>Marked <strong>absent</strong> from "
                f"<strong>{session_name}</strong> on {session_date}.<br/>"
                + (
                    f"Notification sent to guardian <strong>{guardian.name}</strong>."
                    if sent else
                    "No guardian notification configured - manual follow-up may be needed."
                )
                + "</p>"
            )
            partner.sudo().message_post(
                body=note,
                message_type='note',
                subtype_xmlid='mail.mt_note',
            )
        except Exception:
            pass

        return sent


# ──────────────────────────────────────────────────────────────────────────
# Roster Line
# ──────────────────────────────────────────────────────────────────────────

class AttendanceRosterLine(models.TransientModel):
    _name = 'disaster.attendance.roster.line'
    _description = 'Attendance Roster Line'
    _order = 'partner_name asc'

    roster_id = fields.Many2one(
        comodel_name='disaster.attendance.roster',
        string='Roster',
        required=True,
        ondelete='cascade',
    )

    # ── Student details ───────────────────────────────────────────────
    partner_id = fields.Many2one(
        comodel_name='res.partner',
        string='Student',
        required=True,
    )
    partner_name = fields.Char(
        related='partner_id.name',
        string='Name',
        store=True,
    )
    partner_image_128 = fields.Binary(
        related='partner_id.image_128',
        string='Photo',
        readonly=True,
    )
    belt_rank = fields.Selection(
        related='partner_id.belt_rank',
        string='Belt Rank',
        readonly=True,
    )
    member_stage = fields.Selection(
        related='partner_id.member_stage',
        string='Stage',
        readonly=True,
    )
    guardian_name = fields.Char(
        related='partner_id.guardian_id.name',
        string='Guardian',
        readonly=True,
    )

    # ── Roll-call ─────────────────────────────────────────────────────
    status = fields.Selection(
        selection=[
            ('present', 'Present'),
            ('absent', 'Absent'),
        ],
        string='Status',
        default='absent',
        required=True,
    )
    already_checked_in = fields.Boolean(
        string='Already Checked In',
        default=False,
        readonly=True,
    )
    notification_sent = fields.Boolean(
        string='Notified',
        default=False,
        readonly=True,
    )

    # ------------------------------------------------------------------
    # Toggle action – called by the kanban card button
    # ------------------------------------------------------------------
    def action_mark_present(self):
        self.write({'status': 'present'})
        return self._reopen_roster()

    def action_mark_absent(self):
        self.write({'status': 'absent'})
        return self._reopen_roster()

    def action_toggle_status(self):
        for line in self:
            line.write({'status': 'absent' if line.status == 'present' else 'present'})
        return self._reopen_roster()

    def action_call_guardian(self):
        """Open the Twilio call wizard pre-filled with this student's guardian."""
        self.ensure_one()
        return {
            'type': 'ir.actions.act_window',
            'name': '\U0001f4de Call Guardian',
            'res_model': 'disaster.twilio.call.wizard',
            'view_mode': 'form',
            'target': 'new',
            'context': {
                'default_student_id': self.partner_id.id,
                'default_session_id': self.roster_id.session_id.id,
                'default_call_reason': 'absence',
            },
        }
        return self._reopen_roster()

    def _reopen_roster(self):
        """Return an action that keeps the parent roster dialog open."""
        roster = self.mapped('roster_id')[:1]
        if not roster:
            return {'type': 'ir.actions.act_window_close'}
        return {
            'type': 'ir.actions.act_window',
            'res_model': 'disaster.attendance.roster',
            'view_mode': 'form',
            'res_id': roster.id,
            'target': 'new',
            'context': {
                'dialog_size': 'extra-large',
                'default_session_id': roster.session_id.id,
            },
        }
