# -*- coding: utf-8 -*-
"""
dojo_household.py
-----------------
Family / household grouping so guardians and multiple child-members share
one household record.  Mirrors the spec's qwr.household → dojo.household.
"""

from odoo import api, fields, models, _


class DojoHousehold(models.Model):
    _name = 'dojo.household'
    _description = 'Member Household / Family Unit'
    _inherit = ['mail.thread', 'mail.activity.mixin']
    _order = 'name'

    name = fields.Char(string='Household Name', required=True, tracking=True)
    company_id = fields.Many2one(
        'res.company', string='Dojo',
        required=True, default=lambda self: self.env.company,
    )
    primary_guardian_id = fields.Many2one(
        'res.partner', string='Primary Guardian',
        domain="[('is_member','=',True)]",
        tracking=True, ondelete='set null',
    )
    member_ids = fields.One2many(
        'res.partner', 'dojo_household_id', string='Members',
    )
    member_count = fields.Integer(
        string='Members', compute='_compute_member_count', store=True,
    )
    active = fields.Boolean(default=True)
    notes = fields.Text(string='Internal Notes')

    @api.depends('member_ids')
    def _compute_member_count(self):
        for rec in self:
            rec.member_count = len(rec.member_ids)

    def action_view_members(self):
        self.ensure_one()
        return {
            'type': 'ir.actions.act_window',
            'name': _('Household Members'),
            'res_model': 'res.partner',
            'view_mode': 'list,form',
            'domain': [('dojo_household_id', '=', self.id)],
            'context': {'default_dojo_household_id': self.id},
        }
