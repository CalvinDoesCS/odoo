"""
Subscription-only seed \u2014 run AFTER demo_seed.py to refresh plans + subscriptions.

IMPORTANT: demo_seed.py already creates plans and subscriptions.
This script is a standalone re-seed that deletes and recreates them so it can
also be used on a clean DB that has had demo_seed.py run first.

Run:
  DB_PASS=$(cat odoo_pg_pass)
  docker compose exec -T web odoo shell -d odoo19 --db_host db --db_port 5432 \\
    --db_user odoo --db_password \"$DB_PASS\" < demo_seed_subscriptions.py
"""
from datetime import date, timedelta

today = date.today()


def get_member(email):
    user = env[\"res.users\"].search([(\"login\", \"=\", email)], limit=1)
    if not user:
        raise ValueError(f\"User not found: {email}\")
    member = env[\"dojo.member\"].search([(\"partner_id\", \"=\", user.partner_id.id)], limit=1)
    if not member:
        raise ValueError(f\"dojo.member not found for: {email}\")
    return member


def get_program(code):
    prog = env[\"dojo.program\"].search([(\"code\", \"=\", code)], limit=1)
    if not prog:
        raise ValueError(f\"dojo.program not found with code: {code}\")
    return prog


# \u2500\u2500 Members \u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500
print(\"Looking up members...\")
s1 = get_member(\"student1@demo.com\")
s2 = get_member(\"student2@demo.com\")
s3 = get_member(\"student3@demo.com\")
s4 = get_member(\"student4@demo.com\")
s5 = get_member(\"student5@demo.com\")

# \u2500\u2500 Programs (created by demo_seed.py) \u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\nprint(\"Looking up programs...\")
prog_kids   = get_program(\"KIDS\")
prog_adults = get_program(\"BJJ\")

# \u2500\u2500 Tear down any existing plans & subscriptions \u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\nprint(\"Removing old subscriptions and plans...\")
env[\"dojo.member.subscription\"].search([]).unlink()
env[\"dojo.subscription.plan\"].search([]).unlink()

# \u2500\u2500 Subscription plans \u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\nprint(\"Creating subscription plans...\")
currency = env.company.currency_id

plan_kids = env[\"dojo.subscription.plan\"].create({
    \"name\": \"Kids BJJ Monthly\", \"code\": \"KIDS-MTH\",
    \"plan_type\": \"program\", \"program_id\": prog_kids.id,
    \"billing_period\": \"monthly\", \"price\": 80.00, \"initial_fee\": 50.00,
    \"currency_id\": currency.id, \"unlimited_sessions\": True, \"max_sessions_per_week\": 3,
    \"description\": \"Unlimited BJJ Kids classes, up to 3 sessions per week.\",
})
plan_adult = env[\"dojo.subscription.plan\"].create({
    \"name\": \"Adult BJJ Monthly\", \"code\": \"ADV-MTH\",
    \"plan_type\": \"program\", \"program_id\": prog_adults.id,
    \"billing_period\": \"monthly\", \"price\": 120.00, \"initial_fee\": 50.00,
    \"currency_id\": currency.id, \"unlimited_sessions\": True, \"max_sessions_per_week\": 5,
    \"description\": \"Unlimited adult BJJ classes, up to 5 sessions per week.\",
})

# Look up ADV-ADV template for the course-based plan
tmpl_adv = env[\"dojo.class.template\"].search([(\"code\", \"=\", \"ADV-ADV\")], limit=1)
env[\"dojo.subscription.plan\"].create({
    \"name\": \"Private Lessons\", \"code\": \"PRIV-MTH\",
    \"plan_type\": \"course\", \"billing_period\": \"monthly\",
    \"price\": 250.00, \"initial_fee\": 0.00,
    \"currency_id\": currency.id, \"unlimited_sessions\": False,
    \"sessions_per_period\": 4, \"max_sessions_per_week\": 1,
    \"allowed_template_ids\": [(4, tmpl_adv.id)] if tmpl_adv else [],
    \"description\": \"Four private advanced sparring sessions per month.\",
})

# \u2500\u2500 Member subscriptions \u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500
print(\"Assigning member subscriptions...\")
sub_start = today - timedelta(days=60)
sub_next  = today + timedelta(days=30 - today.day + 1)

assignments = [
    (s1, plan_kids,  \"Jordan Smith \u2014 Kids BJJ\"),
    (s2, plan_kids,  \"Casey Smith \u2014 Kids BJJ\"),
    (s3, plan_kids,  \"Taylor Jones \u2014 Kids BJJ\"),
    (s4, plan_kids,  \"Morgan Jones \u2014 Kids BJJ\"),
    (s5, plan_adult, \"Riley Lee \u2014 Adult BJJ\"),
]
for member, plan, note in assignments:
    env[\"dojo.member.subscription\"].create({
        \"member_id\": member.id, \"plan_id\": plan.id,
        \"start_date\": sub_start, \"next_billing_date\": sub_next,
        \"state\": \"active\", \"company_id\": env.company.id, \"note\": note,
    })
    print(f\"  {member.name} \u2192 {plan.name}\")

env.cr.commit()
print(\"\"\"\nDone! Subscription demo data (re-)created.

Plans:
  Kids BJJ Monthly  $80/mo + $50 setup   program-based (KIDS), max 3/week
  Adult BJJ Monthly $120/mo + $50 setup  program-based (BJJ),  max 5/week
  Private Lessons   $250/mo, no setup    course-based  (ADV-ADV template), 4/period

Subscriptions: s1\u2013s4 \u2192 Kids BJJ Monthly | s5 \u2192 Adult BJJ Monthly
\"\"\")
