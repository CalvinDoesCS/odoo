# -*- coding: utf-8 -*-
"""
belt_rank_config.py
-------------------
Stores the minimum-attendance threshold required for each belt rank so that
the system can mark a member as "ready_for_test".  A menu item under
Configuration lets administrators adjust these thresholds without touching
source code.
"""

from odoo import api, fields, models

BELT_SELECTION = [
    ('white',  'White'),
    ('yellow', 'Yellow'),
    ('orange', 'Orange'),
    ('green',  'Green'),
    ('blue',   'Blue'),
    ('purple', 'Purple'),
    ('brown',  'Brown'),
    ('red',    'Red'),
    ('black',  'Black'),
]


class BeltRankConfig(models.Model):
    _name = 'disaster.belt.rank.config'
    _description = 'Belt Rank Attendance Threshold Configuration'
    _order = 'sequence asc'

    sequence = fields.Integer(
        string='Sequence',
        default=10,
        help='Display order – lower numbers appear first.',
    )
    rank = fields.Selection(
        selection=BELT_SELECTION,
        string='Belt Rank',
        required=True,
        index=True,
    )
    rank_label = fields.Char(
        string='Rank Label',
        compute='_compute_rank_label',
        store=True,
    )
    min_attendance = fields.Integer(
        string='Minimum Attendance',
        default=10,
        help='Number of attendances required before a member at this rank '
             'is flagged as Ready for Test.',
    )

    _sql_constraints = [
        ('unique_rank', 'UNIQUE(rank)',
         'Each belt rank may only have one configuration row.'),
    ]

    @api.depends('rank')
    def _compute_rank_label(self):
        label_map = dict(BELT_SELECTION)
        for rec in self:
            rec.rank_label = label_map.get(rec.rank, '')
