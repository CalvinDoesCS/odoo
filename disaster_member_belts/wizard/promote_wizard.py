# -*- coding: utf-8 -*-
"""
promote_wizard.py
-----------------
Transient model that asks the user to confirm a belt-rank promotion.
On confirmation it:
  1. Advances partner.belt_rank to the next rank in the sequence.
  2. Resets attendance_count to 0.
  3. Posts a formatted message in the partner's Chatter.
"""

from odoo import api, fields, models, _
from odoo.exceptions import UserError

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

BELT_ORDER = [r[0] for r in BELT_SELECTION]
BELT_LABEL = dict(BELT_SELECTION)


class DisasterPromoteWizard(models.TransientModel):
    _name = 'disaster.promote.wizard'
    _description = 'Belt Rank Promotion Wizard'

    partner_id = fields.Many2one(
        comodel_name='res.partner',
        string='Member',
        required=True,
        readonly=True,
    )
    current_rank = fields.Selection(
        selection=BELT_SELECTION,
        string='Current Rank',
        required=True,
        readonly=True,
    )
    new_rank = fields.Selection(
        selection=BELT_SELECTION,
        string='New Rank',
        compute='_compute_new_rank',
        store=True,
    )
    new_rank_label = fields.Char(
        string='New Rank (label)',
        compute='_compute_new_rank',
        store=True,
    )
    current_rank_label = fields.Char(
        string='Current Rank (label)',
        compute='_compute_current_rank_label',
    )
    notes = fields.Text(
        string='Promotion Notes',
        help='Optional remarks to include in the Chatter message.',
    )
    reset_attendance = fields.Boolean(
        string='Reset Attendance Count',
        default=True,
        help='Set attendance count back to zero after promotion.',
    )

    # ------------------------------------------------------------------
    # Compute
    # ------------------------------------------------------------------
    @api.depends('current_rank')
    def _compute_new_rank(self):
        for wiz in self:
            if wiz.current_rank and wiz.current_rank in BELT_ORDER:
                idx = BELT_ORDER.index(wiz.current_rank)
                if idx < len(BELT_ORDER) - 1:
                    wiz.new_rank = BELT_ORDER[idx + 1]
                    wiz.new_rank_label = BELT_LABEL.get(wiz.new_rank, '')
                else:
                    wiz.new_rank = wiz.current_rank
                    wiz.new_rank_label = BELT_LABEL.get(wiz.current_rank, '')
            else:
                wiz.new_rank = False
                wiz.new_rank_label = ''

    @api.depends('current_rank')
    def _compute_current_rank_label(self):
        for wiz in self:
            wiz.current_rank_label = BELT_LABEL.get(wiz.current_rank or '', '')

    # ------------------------------------------------------------------
    # Actions
    # ------------------------------------------------------------------
    def action_confirm_promotion(self):
        """Apply the promotion and post a Chatter message."""
        self.ensure_one()
        partner = self.partner_id

        if self.current_rank == BELT_ORDER[-1]:
            raise UserError(
                _('This member already holds the highest belt rank (Black). '
                  'No further promotion is possible.')
            )

        if not self.new_rank or self.new_rank == self.current_rank:
            raise UserError(_('Unable to determine the next rank. Please check '
                              'the belt rank configuration.'))

        old_label = BELT_LABEL.get(self.current_rank, self.current_rank)
        new_label = BELT_LABEL.get(self.new_rank, self.new_rank)

        # ---- Apply the promotion ----
        vals = {'belt_rank': self.new_rank}
        if self.reset_attendance:
            vals['attendance_count'] = 0
        partner.write(vals)

        # ---- Chatter message ----
        body_lines = [
            f'<p><strong>🥋 Belt Rank Promotion</strong></p>',
            f'<ul>',
            f'<li><b>From:</b> {old_label}</li>',
            f'<li><b>To:</b> {new_label}</li>',
        ]
        if self.reset_attendance:
            body_lines.append('<li><b>Attendance count reset to 0.</b></li>')
        if self.notes:
            body_lines.append(f'<li><b>Notes:</b> {self.notes}</li>')
        body_lines.append('</ul>')
        body = '\n'.join(body_lines)

        partner.message_post(
            body=body,
            subject=_('Belt Rank Promoted: %s → %s') % (old_label, new_label),
            message_type='comment',
            subtype_xmlid='mail.mt_note',
        )

        return {'type': 'ir.actions.act_window_close'}
