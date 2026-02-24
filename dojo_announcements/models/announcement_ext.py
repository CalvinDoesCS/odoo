# -*- coding: utf-8 -*-
"""
announcement_ext.py
-------------------
Extends disaster.announcement with multi-channel dispatch fields
and audience domain filtering.
"""

from odoo import api, fields, models, _


class AnnouncementExt(models.Model):
    _inherit = 'disaster.announcement'

    # ── Audience domain filter ───────────────────────────────────────
    dojo_audience_domain = fields.Char(
        string='Audience Domain Filter',
        help='Stored Odoo domain string to dynamically target recipients. '
             'E.g. [("belt_rank","=","blue"),("member_stage","=","active")]',
    )
    dojo_audience_preview_count = fields.Integer(
        string='Estimated Recipients',
        compute='_compute_audience_preview', store=False,
    )

    # ── Channels ────────────────────────────────────────────────────
    dojo_send_push = fields.Boolean(string='Push Notification', default=False)
    dojo_send_email = fields.Boolean(string='Email', default=False)
    dojo_send_sms = fields.Boolean(string='SMS', default=False)
    dojo_send_in_app = fields.Boolean(string='In-App (portal)', default=True)

    # ── Publish state ────────────────────────────────────────────────
    dojo_publish_dt = fields.Datetime(
        string='Schedule Publish At',
        help='If set, the announcement will be marked active at this time via cron.',
    )
    dojo_expire_dt = fields.Datetime(
        string='Expire At',
        help='Alias for date_end; auto-sets date_end.',
    )
    dojo_dispatched = fields.Boolean(
        string='Dispatched', default=False, readonly=True,
        help='True once push/email/SMS dispatch has been triggered.',
    )

    @api.depends('dojo_audience_domain', 'audience')
    def _compute_audience_preview(self):
        for rec in self:
            try:
                domain = [('is_member', '=', True)]
                if rec.audience == 'members_only':
                    domain.append(('member_stage', '=', 'active'))
                elif rec.audience == 'instructors_only':
                    domain.append(('is_instructor', '=', True))
                if rec.dojo_audience_domain:
                    import ast
                    extra = ast.literal_eval(rec.dojo_audience_domain)
                    domain += extra
                rec.dojo_audience_preview_count = self.env['res.partner'].search_count(domain)
            except Exception:
                rec.dojo_audience_preview_count = 0

    # ── Dispatch action ─────────────────────────────────────────────
    def action_dispatch(self):
        """Dispatch announcement to all configured channels."""
        for rec in self:
            if rec.dojo_dispatched:
                continue
            recipients = rec._get_recipients()
            partner_ids = recipients.ids
            if rec.dojo_send_push and partner_ids:
                self.env['dojo.push.device'].send_to_partners(
                    partner_ids,
                    title=rec.name,
                    body=rec.summary or '',
                    data={'announcement_id': rec.id},
                )
            if rec.dojo_send_sms and partner_ids:
                # SMS via Odoo sms module
                for partner in recipients.filtered(lambda p: p.mobile or p.phone):
                    self.env['sms.sms'].sudo().create({
                        'number': partner.mobile or partner.phone,
                        'body': rec.summary or rec.name,
                        'partner_id': partner.id,
                    }).send()
            if rec.dojo_send_email and partner_ids:
                for partner in recipients.filtered('email'):
                    self.env['mail.mail'].sudo().create({
                        'subject': rec.name,
                        'body_html': rec.body or '<p>%s</p>' % rec.name,
                        'email_to': partner.email,
                        'auto_delete': True,
                    }).send()
            rec.dojo_dispatched = True
            rec.message_post(body=_('Announcement dispatched to %d recipients.') % len(partner_ids))

    def _get_recipients(self):
        """Build the recipient partner set based on audience + domain filters."""
        self.ensure_one()
        domain = [('is_member', '=', True), ('member_stage', '=', 'active')]
        if self.audience == 'instructors_only':
            domain = [('is_instructor', '=', True)]
        elif self.audience == 'all':
            domain = [('active', '=', True)]
        if self.dojo_audience_domain:
            try:
                import ast
                domain += ast.literal_eval(self.dojo_audience_domain)
            except Exception:
                pass
        return self.env['res.partner'].search(domain)

    # ── Cron: scheduled publish ──────────────────────────────────────
    @api.model
    def cron_scheduled_dispatch(self):
        """Run every 15 min; publish and dispatch scheduled announcements."""
        now = fields.Datetime.now()
        to_dispatch = self.search([
            ('active', '=', True),
            ('dojo_dispatched', '=', False),
            ('dojo_publish_dt', '!=', False),
            ('dojo_publish_dt', '<=', now),
        ])
        to_dispatch.action_dispatch()
