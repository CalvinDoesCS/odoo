# -*- coding: utf-8 -*-
"""
checkin_wizard.py
-----------------
Quick check-in wizard: pick a member and immediately create a class attendance
record for the current (or a selected) session.
"""

from odoo import api, fields, models
from odoo.exceptions import UserError


class DisasterCheckinWizard(models.TransientModel):
    _name = 'disaster.checkin.wizard'
    _description = 'Quick Member Check-In'

    session_id = fields.Many2one(
        comodel_name='disaster.class.session',
        string='Session',
        required=True,
    )
    partner_ids = fields.Many2many(
        comodel_name='res.partner',
        string='Members',
        required=True,
        domain="[('is_member', '=', True)]",
    )

    @api.model
    def default_get(self, fields_list):
        res = super().default_get(fields_list)
        # If opened from a session form, pre-fill the session
        if self.env.context.get('default_session_id'):
            res['session_id'] = self.env.context['default_session_id']
        return res

    def action_checkin(self):
        """Create attendance records for all selected members."""
        self.ensure_one()
        if self.session_id.state == 'cancelled':
            raise UserError('Cannot check in to a cancelled session.')

        Attendance = self.env['disaster.class.attendance']
        already_in = Attendance.search([
            ('session_id', '=', self.session_id.id),
            ('partner_id', 'in', self.partner_ids.ids),
        ]).mapped('partner_id')

        checked_in = self.partner_ids - already_in
        for partner in checked_in:
            Attendance.create({
                'session_id': self.session_id.id,
                'partner_id': partner.id,
            })

        # Move session to in_progress if still scheduled
        if self.session_id.state == 'scheduled':
            self.session_id.state = 'in_progress'

        skipped = len(already_in)
        msg = f'{len(checked_in)} member(s) checked in.'
        if skipped:
            msg += f' {skipped} already checked in (skipped).'

        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {
                'title': 'Check-In Complete',
                'message': msg,
                'type': 'success',
                'sticky': False,
            },
        }
