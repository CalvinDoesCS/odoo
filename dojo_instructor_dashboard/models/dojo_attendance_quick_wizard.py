import logging
from odoo import api, fields, models, _
from odoo.exceptions import UserError

_logger = logging.getLogger(__name__)


class DojoAttendanceQuickWizard(models.TransientModel):
    _name = 'dojo.attendance.quick.wizard'
    _description = 'Quick Attendance Marking Wizard'

    session_id = fields.Many2one(
        'dojo.class.session',
        string='Session',
        required=True,
        readonly=True,
    )
    line_ids = fields.One2many(
        'dojo.attendance.quick.line',
        'wizard_id',
        string='Attendance',
    )

    def write(self, vals):
        """Strip the one2many 'clear-all' command (5) that editable lists send
        via web_save before action_confirm fires.  This preserves the existing
        line records so action_confirm can process them; individual updates and
        new-record commands are kept so real user edits (status changes) apply."""
        if 'line_ids' in vals:
            # Keep all commands EXCEPT command-5 (unlink/clear all)
            filtered = [cmd for cmd in vals['line_ids'] if cmd[0] != 5]
            if filtered:
                vals = dict(vals, line_ids=filtered)
            else:
                # All commands were (5, ...) — nothing to write for line_ids
                vals = {k: v for k, v in vals.items() if k != 'line_ids'}
        return super().write(vals)

    @api.model
    def default_get(self, fields_list):
        res = super().default_get(fields_list)
        session_id = self.env.context.get('default_session_id')
        if not session_id:
            return res

        session = self.env['dojo.class.session'].browse(session_id)
        if not session.exists():
            return res

        lines = []
        existing_logs = {
            log.member_id.id: log
            for log in self.env['dojo.attendance.log'].search([
                ('session_id', '=', session.id),
            ])
        }

        for enrollment in session.enrollment_ids.filtered(
            lambda e: e.status == 'registered'
        ):
            log = existing_logs.get(enrollment.member_id.id)
            lines.append({
                'member_id': enrollment.member_id.id,
                'enrollment_id': enrollment.id,
                'status': log.status if log else 'present',
                'note': log.note if log else False,
            })

        res['line_ids'] = [(0, 0, line) for line in lines]
        return res

    def action_confirm(self):
        self.ensure_one()
        # Invalidate ORM cache so we get a fresh read from DB after web_save
        self.invalidate_recordset(['line_ids'])
        valid_lines = self.line_ids.filtered(lambda l: l.member_id)

        if not valid_lines:
            # web_save may have orphaned the transient lines — query directly
            valid_lines = self.env['dojo.attendance.quick.line'].sudo().search([
                ('wizard_id', '=', self.id),
                ('member_id', '!=', False),
            ])
            _logger.info(
                'action_confirm: line_ids empty for wizard %s, '
                'direct search found %d lines',
                self.id, len(valid_lines),
            )

        if not valid_lines:
            # Last resort: seed from current enrollments with default status
            _logger.warning(
                'action_confirm: no lines found for wizard %s, '
                'falling back to session enrollments',
                self.id,
            )
            session = self.session_id
            fallback_lines = []
            for enr in session.enrollment_ids.filtered(
                lambda e: e.status == 'registered'
            ):
                fallback_lines.append(
                    self.env['dojo.attendance.quick.line'].new({
                        'wizard_id': self.id,
                        'member_id': enr.member_id.id,
                        'enrollment_id': enr.id,
                        'status': 'present',
                    })
                )
            valid_lines = self.env['dojo.attendance.quick.line'].concat(
                *fallback_lines
            ) if fallback_lines else self.env['dojo.attendance.quick.line']

        if not valid_lines:
            raise UserError(_('No enrolled members found for this session.'))

        existing_logs = {
            log.member_id.id: log
            for log in self.env['dojo.attendance.log'].search([
                ('session_id', '=', self.session_id.id),
            ])
        }

        for line in valid_lines:
            vals = {
                'session_id': self.session_id.id,
                'member_id': line.member_id.id,
                'enrollment_id': line.enrollment_id.id or False,
                'status': line.status,
                'note': line.note or False,
                'checkin_datetime': fields.Datetime.now(),
            }
            existing = existing_logs.get(line.member_id.id)
            if existing:
                existing.write({
                    'status': line.status,
                    'note': line.note or False,
                })
            else:
                self.env['dojo.attendance.log'].create(vals)

            # Mirror status back to the enrollment record
            if line.enrollment_id:
                att_state_map = {
                    'present': 'present',
                    'late': 'present',
                    'absent': 'absent',
                    'excused': 'excused',
                }
                line.enrollment_id.attendance_state = att_state_map.get(
                    line.status, 'pending'
                )

        # Move session to done if it was open
        if self.session_id.state == 'open':
            self.session_id.state = 'done'

        # Auto-close any open attendance todos for this session
        self.session_id._close_attendance_todos()

        return {'type': 'ir.actions.act_window_close'}


class DojoAttendanceQuickLine(models.TransientModel):
    _name = 'dojo.attendance.quick.line'
    _description = 'Quick Attendance Line'
    _order = 'member_id'

    wizard_id = fields.Many2one(
        'dojo.attendance.quick.wizard',
        required=True,
        ondelete='cascade',
    )
    member_id = fields.Many2one('dojo.member', string='Member', readonly=True)
    enrollment_id = fields.Many2one('dojo.class.enrollment', readonly=True)
    status = fields.Selection(
        selection=[
            ('present', 'Present'),
            ('late', 'Late'),
            ('absent', 'Absent'),
            ('excused', 'Excused'),
        ],
        required=True,
        default='present',
        string='Status',
    )
    note = fields.Char('Note')
