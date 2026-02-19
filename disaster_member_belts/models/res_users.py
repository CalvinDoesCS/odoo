# -*- coding: utf-8 -*-
"""
res_users.py
------------
Extends res.users so that belt_rank, attendance_count, and ready_for_test
are directly accessible on the user object (proxied from the linked partner).

This means:
  env['res.users'].browse(uid).belt_rank        → works
  env['res.users'].browse(uid).attendance_count → works
  env['res.users'].browse(uid).ready_for_test   → works

Because res.users inherits res.partner, these related fields resolve through
the partner_id link automatically.
"""

from odoo import fields, models


class ResUsers(models.Model):
    _inherit = 'res.users'

    belt_rank = fields.Selection(
        related='partner_id.belt_rank',
        string='Belt Rank',
        readonly=False,
        store=True,
    )

    attendance_count = fields.Integer(
        related='partner_id.attendance_count',
        string='Attendance Count',
        readonly=False,
        store=True,
    )

    ready_for_test = fields.Boolean(
        related='partner_id.ready_for_test',
        string='Ready for Test',
        readonly=True,
        store=True,
    )

    next_belt_rank = fields.Char(
        related='partner_id.next_belt_rank',
        string='Next Belt Rank',
        readonly=True,
    )
