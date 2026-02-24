# -*- coding: utf-8 -*-
"""
dojo_api_token.py
-----------------
Per-partner API token model used by the mobile app for stateless auth.
"""

import secrets
from odoo import api, fields, models
from odoo.exceptions import AccessError, ValidationError


class DojoApiToken(models.Model):
    _name = 'dojo.api.token'
    _description = 'Dojo Mobile API Token'
    _order = 'create_date desc'

    name = fields.Char(
        string='Token Name',
        required=True,
        help='Device description, e.g. "iPhone 15 – John\'s phone"',
    )
    partner_id = fields.Many2one('res.partner', string='Member', required=True,
                                  index=True, ondelete='cascade')
    token = fields.Char(string='Token', readonly=True, index=True)
    active = fields.Boolean(default=True)
    last_used_dt = fields.Datetime(string='Last Used', readonly=True)
    expire_dt = fields.Datetime(string='Expires At')

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            if not vals.get('token'):
                vals['token'] = secrets.token_urlsafe(40)
        return super().create(vals_list)

    @api.model
    def authenticate_token(self, raw_token):
        """Return partner browse record or raise AccessError."""
        token = self.sudo().search([
            ('token', '=', raw_token),
            ('active', '=', True),
        ], limit=1)
        if not token:
            raise AccessError('Invalid or expired API token.')
        # Check expiry
        if token.expire_dt and token.expire_dt < fields.Datetime.now():
            token.active = False
            raise AccessError('API token has expired.')
        token.sudo().write({'last_used_dt': fields.Datetime.now()})
        return token.partner_id
