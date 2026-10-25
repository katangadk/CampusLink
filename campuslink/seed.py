"""Explicit, idempotent local fixtures. Never run against real student data."""
import argparse
import os
import sqlite3
import time
import uuid

from .security import password_hash

PASSWORD = 'CampusLink-local-2026!'
FIXTURES = [
    ('alice', 'Alice Banda', 'Computer Science', 2, 'Curious about code, good books, and the people behind both. Looking for a study partner for the next programming challenge.', ['Programming','Reading','Music','Design'], 'woman', ['man','nonbinary'], 'Algorithms, Python', 'Python, Design', 'Exam preparation'),
    ('brian', 'Brian Mwansa', 'Computer Science', 2, 'Building small things and learning as I go. Always happy to compare notes on cybersecurity or talk about a good game.', ['Cybersecurity','Programming','Gaming','Technology'], 'man', ['woman','nonbinary'], 'Algorithms, Cybersecurity', 'Python, Networking', 'Exam preparation'),
    ('chipo', 'Chipo Phiri', 'Business Administration', 3, 'Ideas, books, and a little creativity. Let’s trade reading recommendations or work through a business idea together.', ['Entrepreneurship','Reading','Art','Music'], 'woman', ['woman','man'], 'Marketing, Economics', 'Writing, Research', 'Project collaboration'),
    ('david', 'David Zulu', 'Information Technology', 1, 'A first-year finding my way. Into gaming, photography, and learning how things work.', ['Gaming','Technology','Photography'], 'man', ['woman','nonbinary'], 'Networking, Python', 'Photography', 'Practice exercises'),
    ('esther', 'Esther Tembo', 'Computer Science', 3, 'Turning sketches into interfaces. I enjoy design, science, and helping people get comfortable with programming.', ['Programming','Design','Science','Art'], 'woman', ['man','woman'], 'Algorithms, Web development', 'Design, Python', 'Project collaboration'),
    ('farai', 'Farai Sakala', 'Electrical Engineering', 2, 'Engineering student with a soft spot for music and weekend football. Looking to meet people beyond my lecture room.', ['Sports','Music','Science','Movies'], 'nonbinary', ['woman','man'], 'Mathematics, Circuits', 'Mathematics', 'Exam preparation'),
    ('grace', 'Grace Musonda', 'Business Administration', 1, 'Starting a new chapter. Here for good conversations, study sessions, and discovering new interests.', ['Travel','Music','Reading','Entrepreneurship'], 'woman', ['man'], 'Economics, Accounting', 'Research', 'Exam preparation'),
]

# Fictional adult fixtures explicitly opted into the dating demo. Existing
# accounts, including Alice and Brian, keep their own opt-in choices.
DATING_FIXTURES = [
    ('demo_daniel', 'Daniel Lungu', 'Information Technology', 2, 'Fictional dating demo profile. Into music, late-night coding, and finding a new favourite book.', ['Programming','Music','Reading'], 'man', ['woman','man','nonbinary'], 'Web development', 'Python', 'Project collaboration'),
    ('demo_naomi', 'Naomi Chanda', 'Business Administration', 2, 'Fictional dating demo profile. Big on creativity, good conversation, and making time for the little things.', ['Music','Design','Photography'], 'woman', ['woman','man','nonbinary'], 'Marketing', 'Design', 'Project collaboration'),
    ('demo_musa', 'Musa Nkhoma', 'Electrical Engineering', 2, 'Fictional dating demo profile. A curious mind, a growing playlist, and always another game to try.', ['Gaming','Technology','Music'], 'nonbinary', ['woman','man','nonbinary'], 'Mathematics', 'Research', 'Exam preparation'),
]


def seed(path=None, *, dating_only=False):
    if os.getenv('CAMPUSLINK_MODE','local')!='local':
        raise RuntimeError('Demo seeding is restricted to local mode. Create individual tester accounts in staging.')
    from .app import create_app
    app = create_app(path)
    con = sqlite3.connect(app.state.db_path)
    con.execute('PRAGMA foreign_keys=ON')
    hashed = password_hash(PASSWORD)
    fixtures = DATING_FIXTURES if dating_only else FIXTURES + DATING_FIXTURES
    for name,display,program,year,bio,interests,gender,preferences,subjects,skills,goals in fixtures:
        uid = str(uuid.uuid5(uuid.NAMESPACE_URL, 'campuslink-local:'+name))
        import json
        con.execute('INSERT OR IGNORE INTO users(id,email,username,display_name,password_hash,dob,bio,program,year,subjects,skills,study_goals,onboarding_step,local_test,adult_test,gender,dating_genders,created_at,dating_enabled) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,6,1,1,?,?,?,?)',
                    (uid,f'{name}@campuslink.test',name,display,hashed,'2003-06-15',bio,program,year,subjects,skills,goals,gender,json.dumps(preferences),int(time.time()),int(name.startswith('demo_'))))
        con.executemany('INSERT OR IGNORE INTO user_interests SELECT ?,id FROM interests WHERE name=?',[(uid,i) for i in interests])
    if not dating_only:
        uid = str(uuid.uuid5(uuid.NAMESPACE_URL,'campuslink-local:moderator'))
        con.execute('INSERT OR IGNORE INTO users(id,email,username,display_name,password_hash,role,local_test,discoverable,onboarding_step,created_at) VALUES (?,?,?,?,?,"moderator",1,0,6,?)',
                    (uid,'moderator@campuslink.test','moderator','Local Moderator',hashed,int(time.time())))
    con.commit()
    con.close()
    print('Local fixtures created. All are fictional, unverified test accounts.')
    if not dating_only:
        print('Accounts: alice, brian, chipo, david, esther, farai, grace, moderator @campuslink.test')
    print('Opted-in dating fixtures: demo_daniel, demo_naomi, demo_musa @campuslink.test')
    print('Password: '+PASSWORD)


if __name__=='__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--db',default=None)
    parser.add_argument('--dating-only',action='store_true',help='Add dating fixtures without updating existing general fixtures.')
    args=parser.parse_args()
    seed(args.db,dating_only=args.dating_only)
