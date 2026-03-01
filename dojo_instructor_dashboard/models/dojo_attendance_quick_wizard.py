from odoo import api, fields, models, _
from odoo.exceptions import UserError


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
        if not self.line_ids:
            raise UserError(_('No attendance lines to save.'))

        existing_logs = {
            log.member_id.id: log
            for log in self.env['dojo.attendance.log'].search([
                ('session_id', '=', self.session_id.id),
            ])
        }

        for line in self.line_ids:
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
    member_id = fields.Many2one('dojo.member', string='Member', required=True, readonly=True)
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
