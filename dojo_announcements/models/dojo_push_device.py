# -*- coding: utf-8 -*-
"""
dojo_push_device.py
-------------------
Stores APNS / FCM push notification device tokens for members.
One member can have multiple devices (phone + tablet + web).
"""

from odoo import fields, models, api


class DojoPushDevice(models.Model):
    _name = 'dojo.push.device'
    _description = 'Push Notification Device'
    _order = 'last_seen_dt desc'

    partner_id = fields.Many2one(
        'res.partner', string='Member / User',
        required=True, ondelete='cascade', index=True,
    )
    user_id = fields.Many2one(
        'res.users', string='Portal User',
        ondelete='set null', index=True,
    )
    platform = fields.Selection([
        ('ios',     'iOS (APNS)'),
        ('android', 'Android (FCM)'),
        ('web',     'Web Push'),
    ], string='Platform', required=True)
    token = fields.Char(
        string='Device Token', required=True, index=True,
        help='FCM registration token or APNS device token.',
    )
    app_version = fields.Char(string='App Version')
    last_seen_dt = fields.Datetime(
        string='Last Seen', default=fields.Datetime.now,
    )
    active = fields.Boolean(default=True)

    _sql_constraints = [
        ('unique_token', 'UNIQUE(token)', 'Device token must be unique.'),
    ]

    @api.model
    def register_device(self, partner_id, platform, token, user_id=None, app_version=None):
        """Upsert a device token. Called from the mobile API."""
        existing = self.search([('token', '=', token)], limit=1)
        vals = {
            'partner_id': partner_id,
            'platform': platform,
            'token': token,
            'last_seen_dt': fields.Datetime.now(),
        }
        if user_id:
            vals['user_id'] = user_id
        if app_version:
            vals['app_version'] = app_version
        if existing:
            existing.write(vals)
            return existing.id
        else:
            return self.create(vals).id

    def send_push_notification(self, title, body, data=None):
        """
        Stub: send a push notification to this device.
        Integrate your FCM / APNS provider here.
        """
        self.ensure_one()
        # TODO: call FCM/APNS HTTP API
        # Example: requests.post(FCM_URL, json={...})
        return {
            'platform': self.platform,
            'token': self.token,
            'title': title,
            'body': body,
            'data': data or {},
        }

    @api.model
    def send_to_partners(self, partner_ids, title, body, data=None):
        """Send push to all active devices for the given partner ids."""
        devices = self.search([
            ('partner_id', 'in', partner_ids),
            ('active', '=', True),
        ])
        results = []
        for device in devices:
            results.append(device.send_push_notification(title, body, data))
        return results
