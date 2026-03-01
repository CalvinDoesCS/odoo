from datetime import timedelta

from odoo import _, api, models
from odoo.exceptions import ValidationError


class DojoClassEnrollment(models.Model):
    _inherit = 'dojo.class.enrollment'

    @api.constrains('session_id', 'member_id', 'status')
    def _check_subscription_constraints(self):
        for rec in self:
            if rec.status != 'registered':
                continue

            member = rec.member_id
            template = rec.session_id.template_id
            session_dt = rec.session_id.start_datetime

            # ── Rule 1: an active subscription is required ─────────────────
            active_subs = self.env['dojo.member.subscription'].search([
                ('member_id', '=', member.id),
                ('state', '=', 'active'),
            ])
            if not active_subs:
                raise ValidationError(_(
                    'A subscription is required to enrol in sessions. '
                    'Please set up a subscription for %s before enrolling.',
                    member.name,
                ))

            # ── Rule 2: at least one plan must permit this course ──────────
            # A plan permits the course when its allowed_template_ids is empty
            # (= no restriction) OR the template is explicitly listed.
            permitting_subs = [
                sub for sub in active_subs
                if not sub.plan_id.allowed_template_ids
                or template in sub.plan_id.allowed_template_ids
            ]
            if not permitting_subs:
                plan_names = ', '.join(s.plan_id.name for s in active_subs)
                raise ValidationError(_(
                    'The course "%s" is not included in the current subscription plan(s): %s.',
                    template.name, plan_names,
                ))

            # ── Rules 3 & 4: cap checks — enrollment is OK if ANY permitting
            #    plan does not exceed its caps. ──────────────────────────────
            cap_errors = []

            for sub in permitting_subs:
                plan = sub.plan_id
                plan_ok = True  # assume this plan is fine until a cap fires

                # ── Weekly cap ────────────────────────────────────────────
                if plan.max_sessions_per_week > 0 and session_dt:
                    session_date = session_dt.date()
                    week_start = session_date - timedelta(days=session_date.weekday())
                    week_end = week_start + timedelta(days=6)

                    domain = [
                        ('member_id', '=', member.id),
                        ('status', '=', 'registered'),
                        ('session_id.start_datetime', '>=',
                         '%s 00:00:00' % week_start),
                        ('session_id.start_datetime', '<=',
                         '%s 23:59:59' % week_end),
                        ('id', '!=', rec.id),
                    ]
                    # Scope the count to templates this plan allows
                    if plan.allowed_template_ids:
                        domain.append(
                            ('session_id.template_id', 'in',
                             plan.allowed_template_ids.ids)
                        )
                    weekly_count = self.env['dojo.class.enrollment'].search_count(domain)
                    if weekly_count >= plan.max_sessions_per_week:
                        cap_errors.append(_(
                            'Weekly limit reached: the "%s" plan allows %d session(s) per week '
                            'and %s already has %d enrolled this week.',
                            plan.name, plan.max_sessions_per_week,
                            member.name, weekly_count,
                        ))
                        plan_ok = False

                # ── Billing-period cap ────────────────────────────────────
                if (plan_ok
                        and not plan.unlimited_sessions
                        and plan.sessions_per_period > 0
                        and sub.start_date and sub.next_billing_date):
                    domain = [
                        ('member_id', '=', member.id),
                        ('status', '=', 'registered'),
                        ('session_id.start_datetime', '>=',
                         '%s 00:00:00' % sub.start_date),
                        ('session_id.start_datetime', '<',
                         '%s 00:00:00' % sub.next_billing_date),
                        ('id', '!=', rec.id),
                    ]
                    if plan.allowed_template_ids:
                        domain.append(
                            ('session_id.template_id', 'in',
                             plan.allowed_template_ids.ids)
                        )
                    period_count = self.env['dojo.class.enrollment'].search_count(domain)
                    if period_count >= plan.sessions_per_period:
                        cap_errors.append(_(
                            'Period limit reached: the "%s" plan allows %d session(s) per %s '
                            'and %s already has %d enrolled this period.',
                            plan.name, plan.sessions_per_period,
                            plan.billing_period, member.name, period_count,
                        ))
                        plan_ok = False

                # If this plan passes all caps, enrollment is allowed — done.
                if plan_ok:
                    return

            # Every permitting plan hit at least one cap — raise with the first error.
            if cap_errors:
                raise ValidationError(cap_errors[0])
