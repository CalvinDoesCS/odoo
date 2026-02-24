# -*- coding: utf-8 -*-
"""
belt_rank_ext.py
----------------
Extends disaster.belt.rank.config with:
  - dojo_min_days_in_rank  – minimum days before testing
  - dojo_requirements      – JSON checklist of promotion requirements
  - dojo_curriculum_ids    – linked curriculum content items
  - dojo_history_ids       – linked promotion history
"""

from odoo import fields, models


class BeltRankConfigExt(models.Model):
    _inherit = 'disaster.belt.rank.config'

    dojo_min_days_in_rank = fields.Integer(
        string='Min Days at Rank',
        default=0,
        help='Minimum number of days a member must hold this rank before being eligible for promotion.',
    )
    dojo_requirements = fields.Json(
        string='Promotion Requirements',
        help='Structured JSON checklist of techniques, forms and criteria required for the next promotion.',
    )
    dojo_curriculum_ids = fields.One2many(
        'dojo.rank.curriculum', 'belt_rank_id', string='Curriculum',
    )
    dojo_history_ids = fields.One2many(
        'dojo.rank.history', 'belt_rank_id', string='Promotion History',
    )
    dojo_member_count = fields.Integer(
        string='Current Members',
        compute='_compute_dojo_member_count',
        help='Number of active members currently at this belt rank.',
    )

    def _compute_dojo_member_count(self):
        for rec in self:
            rec.dojo_member_count = self.env['res.partner'].search_count([
                ('belt_rank', '=', rec.rank),
                ('is_member', '=', True),
            ])
