"""
Subscription demo seed — run AFTER demo_seed.py:
  DB_PASS=$(cat odoo_pg_pass)
  docker compose exec -T web odoo shell -d odoo19 --db_host db --db_port 5432 \
    --db_user odoo --db_password "$DB_PASS" < demo_seed_subscriptions.py
"""
from datetime import date, timedelta

today = date.today()

# ── Look up existing members by their portal user email ──────────────────
def get_member(email):
    user = env["res.users"].search([("login", "=", email)], limit=1)
    if not user:
        raise ValueError(f"User not found: {email}")
    member = env["dojo.member"].search([("partner_id", "=", user.partner_id.id)], limit=1)
    if not member:
        raise ValueError(f"dojo.member not found for: {email}")
    return member

p1 = get_member("parent1@demo.com")
p2 = get_member("parent2@demo.com")
s1 = get_member("student1@demo.com")
s2 = get_member("student2@demo.com")
s3 = get_member("student3@demo.com")
s4 = get_member("student4@demo.com")
s5 = get_member("student5@demo.com")

# ── Subscription plans ────────────────────────────────────────────────────
print("Creating subscription plans...")
currency = env.company.currency_id

plan_kids = env["dojo.subscription.plan"].create({
    "name": "Kids Monthly",
    "code": "KIDS-MTH",
    "billing_period": "monthly",
    "price": 80.00,
    "currency_id": currency.id,
    "unlimited_sessions": True,
    "description": "Unlimited monthly classes for members under 18.",
})

plan_adult = env["dojo.subscription.plan"].create({
    "name": "Adult Monthly",
    "code": "ADULT-MTH",
    "billing_period": "monthly",
    "price": 120.00,
    "currency_id": currency.id,
    "unlimited_sessions": True,
    "description": "Unlimited monthly classes for adult members.",
})

plan_family = env["dojo.subscription.plan"].create({
    "name": "Family Monthly",
    "code": "FAM-MTH",
    "billing_period": "monthly",
    "price": 200.00,
    "currency_id": currency.id,
    "unlimited_sessions": True,
    "description": "One subscription covering a full household.",
})

# ── Assign subscriptions ──────────────────────────────────────────────────
# Smith household: family plan for the guardian, kids plan for children
# Jones household: family plan for the guardian, kids plan for children
# Riley Lee: adult monthly (standalone)

print("Assigning subscriptions...")
start = today - timedelta(days=90)
next_bill = today + timedelta(days=today.day and (30 - today.day + 1) or 1)

subs = [
    # (member,  plan,         note)
    (p1, plan_family, "Smith household family plan"),
    (p2, plan_family, "Jones household family plan"),
    (s1, plan_kids,   "Jordan Smith — Beginner Fundamentals"),
    (s2, plan_kids,   "Casey Smith — Beginner Fundamentals"),
    (s3, plan_kids,   "Taylor Jones — Intermediate Techniques"),
    (s4, plan_kids,   "Morgan Jones — Intermediate Techniques"),
    (s5, plan_adult,  "Riley Lee — Advanced Sparring"),
]

for member, plan, note in subs:
    env["dojo.member.subscription"].create({
        "member_id":        member.id,
        "plan_id":          plan.id,
        "start_date":       start,
        "next_billing_date": next_bill,
        "state":            "active",
        "note":             note,
    })
    print(f"  {member.name} → {plan.name}")

env.cr.commit()
print("\nDone! Subscription demo data created.")
print("  Plans  : Kids Monthly ($80) | Adult Monthly ($120) | Family Monthly ($200)")
print("  Members: 7 active subscriptions assigned")
