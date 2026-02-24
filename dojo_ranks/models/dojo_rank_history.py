# -*- coding: utf-8 -*-
"""
dojo_rank_history.py
--------------------
Immutable log of every rank promotion.  Created automatically by the
existing belt-test workflow (disaster.belt.test.action_close) and can
also be created manually for historical data import.
"""

from odoo import api, fields, models, _
from odoo.exceptions import UserError


class DojoRankHistory(models.Model):
    _name = 'dojo.rank.history'
    _description = 'Member Rank Promotion History'
    _order = 'awarded_dt desc, id desc'

    member_id = fields.Many2one(
        'res.partner', string='Member',
        required=True, ondelete='cascade', index=True,
        domain="[('is_member','=',True)]",
    )
    belt_rank_id = fields.Many2one(
        'disaster.belt.rank.config', string='Rank Awarded',
        required=True, ondelete='restrict',
    )
    belt_rank_value = fields.Selection(
        related='belt_rank_id.rank', store=True, string='Belt',
    )
    previous_belt_rank_id = fields.Many2one(
        'disaster.belt.rank.config', string='From Rank',
        ondelete='set null',
    )
    awarded_dt = fields.Datetime(
        string='Awarded On', required=True, default=fields.Datetime.now,
    )
    awarded_by_id = fields.Many2one(
        'res.partner', string='Awarded By',
        domain="[('is_instructor','=',True)]",
        ondelete='set null',
    )
    belt_test_id = fields.Many2one(
        'disaster.belt.test', string='Belt Test',
        ondelete='set null',
        help='The belt test event that triggered this promotion.',
    )
    notes = fields.Text(string='Notes')
    company_id = fields.Many2one(
        'res.company', string='Dojo',
        default=lambda self: self.env.company,
    )

    @api.model_create_multi
    def create(self, vals_list):
        records = super().create(vals_list)
        for rec in records:
            # Keep partner's belt_rank in sync
            if rec.member_id and rec.belt_rank_value:
                rec.member_id.sudo().write({'belt_rank': rec.belt_rank_value})
                rec.member_id.sudo().attendance_count = 0  # reset attendance after promotion
                rec.member_id.message_post(
                    body=_('🥋 Promoted to <b>%s</b> belt.') % rec.belt_rank_id.rank_label
                )
        return records

    def unlink(self):
        raise UserError(_(
            'Promotion history records cannot be deleted to preserve audit integrity. '
            'Archive this record instead.'
        ))
