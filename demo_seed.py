from datetime import date, datetime, timedelta

today = date.today()
PASSWORD = "dojo@2026"

group_instructor    = env.ref("dojo_base.group_dojo_instructor")
group_user          = env.ref("base.group_user")
group_portal        = env.ref("base.group_portal")
group_parent_student = env.ref("dojo_base.group_dojo_parent_student")

def make_user(name, login, groups):
    u = env["res.users"].create({
        "name": name, "login": login, "email": login,
        "group_ids": [(6, 0, [g.id for g in groups])],
    })
    u.password = PASSWORD
    return u

print("Creating instructors...")
instr1_user = make_user("Alex Johnson", "instructor1@demo.com", [group_instructor, group_user])
instr2_user = make_user("Sam Rivera",   "instructor2@demo.com", [group_instructor, group_user])
instr1 = env["dojo.instructor.profile"].create({"name": "Alex Johnson", "user_id": instr1_user.id, "partner_id": instr1_user.partner_id.id, "bio": "Head instructor with 15 years of experience."})
instr2 = env["dojo.instructor.profile"].create({"name": "Sam Rivera",   "user_id": instr2_user.id, "partner_id": instr2_user.partner_id.id, "bio": "Assistant instructor specialising in advanced sparring."})

print("Creating parents...")
p1_user = make_user("Mary Smith", "parent1@demo.com", [group_parent_student])
p2_user = make_user("Bob Jones",  "parent2@demo.com", [group_parent_student])
p1 = env["dojo.member"].create({"partner_id": p1_user.partner_id.id, "role": "parent", "membership_state": "active"})
p2 = env["dojo.member"].create({"partner_id": p2_user.partner_id.id, "role": "parent", "membership_state": "active"})

print("Creating students...")
students_raw = [
    ("Jordan Smith",  "student1@demo.com", "student", date(2010, 3, 15)),
    ("Casey Smith",   "student2@demo.com", "student", date(2012, 7, 22)),
    ("Taylor Jones",  "student3@demo.com", "student", date(2009, 11, 5)),
    ("Morgan Jones",  "student4@demo.com", "student", date(2011, 4, 18)),
    ("Riley Lee",     "student5@demo.com", "both",    date(2005, 8, 30)),
]
student_members = []
for name, login, role, dob in students_raw:
    u = make_user(name, login, [group_parent_student])
    m = env["dojo.member"].create({"partner_id": u.partner_id.id, "role": role, "date_of_birth": dob, "membership_state": "active"})
    student_members.append(m)
s1, s2, s3, s4, s5 = student_members

print("Creating households...")
smith_hh = env["dojo.household"].create({"name": "Smith Household"})
p1.household_id = smith_hh
s1.household_id = smith_hh
s2.household_id = smith_hh
smith_hh.primary_guardian_id = p1
env["dojo.guardian.link"].create({"household_id": smith_hh.id, "guardian_member_id": p1.id, "student_member_id": s1.id, "relation": "mother", "is_primary": True})
env["dojo.guardian.link"].create({"household_id": smith_hh.id, "guardian_member_id": p1.id, "student_member_id": s2.id, "relation": "mother", "is_primary": True})

jones_hh = env["dojo.household"].create({"name": "Jones Household"})
p2.household_id = jones_hh
s3.household_id = jones_hh
s4.household_id = jones_hh
jones_hh.primary_guardian_id = p2
env["dojo.guardian.link"].create({"household_id": jones_hh.id, "guardian_member_id": p2.id, "student_member_id": s3.id, "relation": "father", "is_primary": True})
env["dojo.guardian.link"].create({"household_id": jones_hh.id, "guardian_member_id": p2.id, "student_member_id": s4.id, "relation": "father", "is_primary": True})

print("Creating belt ranks...")
rank_defs = [
    ("White Belt",  10, "#FFFFFF"), ("Yellow Belt", 20, "#FFD700"),
    ("Orange Belt", 30, "#FF8C00"), ("Green Belt",  40, "#228B22"),
    ("Blue Belt",   50, "#1E90FF"), ("Purple Belt", 60, "#800080"),
    ("Red Belt",    70, "#DC143C"), ("Brown Belt",  80, "#8B4513"),
    ("Black Belt",  90, "#111111"),
]
ranks = {}
for rname, seq, color in rank_defs:
    ranks[rname] = env["dojo.belt.rank"].create({"name": rname, "sequence": seq, "color": color})

print("Assigning rank history...")
for m in [s1, s2]:
    env["dojo.member.rank"].create({"member_id": m.id, "rank_id": ranks["White Belt"].id,  "date_awarded": today - timedelta(days=90), "awarded_by": instr1.id})
for m in [s3, s4]:
    env["dojo.member.rank"].create({"member_id": m.id, "rank_id": ranks["Yellow Belt"].id, "date_awarded": today - timedelta(days=60), "awarded_by": instr1.id})
env["dojo.member.rank"].create({"member_id": s5.id, "rank_id": ranks["Green Belt"].id, "date_awarded": today - timedelta(days=30), "awarded_by": instr2.id})

print("Creating class templates...")
tmpl_beg = env["dojo.class.template"].create({"name": "Beginner Fundamentals",   "code": "BEG-001", "level": "beginner",     "duration_minutes": 60, "max_capacity": 15, "instructor_profile_ids": [(4, instr1.id)], "description": "Core stances, blocks and strikes for new students."})
tmpl_int = env["dojo.class.template"].create({"name": "Intermediate Techniques", "code": "INT-001", "level": "intermediate", "duration_minutes": 75, "max_capacity": 12, "instructor_profile_ids": [(4, instr1.id)], "description": "Combinations, kata and light sparring for intermediate students."})
tmpl_adv = env["dojo.class.template"].create({"name": "Advanced Sparring",       "code": "ADV-001", "level": "advanced",     "duration_minutes": 90, "max_capacity": 8,  "instructor_profile_ids": [(4, instr2.id)], "description": "Full contact sparring and black belt curriculum."})

print("Creating sessions and enrollments...")
def seed_sessions(template, instructor, members, hour):
    for offset, state in [(-14,"done"),(-10,"done"),(-5,"done"),(2,"open"),(7,"open"),(12,"open")]:
        day = today + timedelta(days=offset)
        start_dt = datetime(day.year, day.month, day.day, hour, 0)
        end_dt   = start_dt + timedelta(minutes=template.duration_minutes)
        session  = env["dojo.class.session"].create({"template_id": template.id, "instructor_profile_id": instructor.id, "start_datetime": start_dt, "end_datetime": end_dt, "capacity": template.max_capacity, "state": state})
        for m in members:
            env["dojo.class.enrollment"].create({"session_id": session.id, "member_id": m.id, "status": "registered", "attendance_state": "present" if state == "done" else "pending"})

seed_sessions(tmpl_beg, instr1, [s1, s2], hour=17)
seed_sessions(tmpl_int, instr1, [s3, s4], hour=18)
seed_sessions(tmpl_adv, instr2, [s5],     hour=19)

env.cr.commit()
print("\nDone! All demo data created.")
print("  instructor1/2@demo.com | parent1/2@demo.com | student1-5@demo.com  pw: dojo@2026")
print("  Smith HH: Mary Smith -> Jordan, Casey Smith")
print("  Jones HH: Bob Jones  -> Taylor, Morgan Jones")
print("  Standalone: Riley Lee (both, Green Belt)")
print("  3 past + 3 upcoming sessions per template | 18 sessions total | 9 belt ranks")
