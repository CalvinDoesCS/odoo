# -*- coding: utf-8 -*-
"""
res_partner_members.py
----------------------
Extends res.partner (already extended by disaster_member_belts) with:
  - dojo_household_id   – links member to a dojo.household
  - dojo_member_number  – human-friendly unique member number (auto-sequenced)
  - dojo_gender         – gender field
  - dojo_minor          – computed: True when age < 18
  - dojo_consent_state  – waiver/consent lifecycle
  - dojo_consent_signed_at / _signed_by_id
  - dojo_medical_notes  – allergy / medical info (staff only)
  - dojo_internal_notes – private staff notes

Note: date_of_birth, emergency_contact, emergency_phone, guardian_id
      are already provided by disaster_member_belts.
"""

from odoo import api, fields, models
from odoo.exceptions import ValidationError


class ResPartnerDojo(models.Model):
    _inherit = 'res.partner'

    # ── Household ───────────────────────────────────────────────────────
    dojo_household_id = fields.Many2one(
        'dojo.household', string='Household',
        index=True, ondelete='set null', tracking=True,
    )

    # ── Member Number ───────────────────────────────────────────────────
    dojo_member_number = fields.Char(
        string='Member #', copy=False, index=True, tracking=True,
        help='Auto-assigned unique member identifier.',
    )

    # ── Demographics ────────────────────────────────────────────────────
    dojo_gender = fields.Selection([
        ('male', 'Male'), ('female', 'Female'),
        ('other', 'Other'), ('prefer_not', 'Prefer Not To Say'),
    ], string='Gender')

    dojo_minor = fields.Boolean(
        string='Minor', compute='_compute_dojo_minor', store=True,
    )

    # ── Consent / Waiver ────────────────────────────────────────────────
    dojo_consent_state = fields.Selection([
        ('pending',  'Pending'),
        ('accepted', 'Accepted'),
        ('revoked',  'Revoked'),
    ], string='Consent / Waiver', default='pending', tracking=True)

    dojo_consent_signed_at = fields.Datetime(
        string='Consent Signed At', readonly=True,
    )
    dojo_consent_signed_by_id = fields.Many2one(
        'res.partner', string='Consent Signed By', ondelete='set null',
    )

    # ── Notes ───────────────────────────────────────────────────────────
    dojo_medical_notes = fields.Text(
        string='Medical / Allergy Notes',
        help='Visible to staff only – allergies, medications, conditions.',
    )
    dojo_internal_notes = fields.Text(
        string='Internal Staff Notes',
        help='Private notes, not visible to the member.',
    )

    # ── Computed ────────────────────────────────────────────────────────
    @api.depends('date_of_birth')
    def _compute_dojo_minor(self):
        from datetime import date
        today = date.today()
        for rec in self:
            if rec.date_of_birth:
                bd = rec.date_of_birth
                age = (
                    today.year - bd.year
                    - ((today.month, today.day) < (bd.month, bd.day))
                )
                rec.dojo_minor = age < 18
            else:
                rec.dojo_minor = False

    # ── ORM overrides ───────────────────────────────────────────────────
    @api.model_create_multi
    def create(self, vals_list):
        seq = self.env['ir.sequence'].sudo()
        for vals in vals_list:
            if vals.get('is_member') and not vals.get('dojo_member_number'):
                vals['dojo_member_number'] = (
                    seq.next_by_code('dojo.member.number') or '/'
                )
        return super().create(vals_list)

    @api.constrains('dojo_member_number')
    def _check_member_number_unique(self):
        for rec in self:
            if rec.dojo_member_number and rec.dojo_member_number != '/':
                if self.search_count([
                    ('dojo_member_number', '=', rec.dojo_member_number),
                    ('id', '!=', rec.id),
                ]):
                    raise ValidationError(
                        'Member number %s is already in use.' % rec.dojo_member_number
                    )

    # ── Consent actions ─────────────────────────────────────────────────
    def action_accept_consent(self):
        self.write({
            'dojo_consent_state': 'accepted',
            'dojo_consent_signed_at': fields.Datetime.now(),
            'dojo_consent_signed_by_id': self.env.user.partner_id.id,
        })

    def action_revoke_consent(self):
        self.write({'dojo_consent_state': 'revoked'})
