import secrets
import sqlite3
from pathlib import Path

DB = Path("fantasy.sqlite3")

def conn():
    c = sqlite3.connect(DB)
    c.row_factory = sqlite3.Row
    return c

def init():
    with conn() as c:
        c.executescript("""
        CREATE TABLE IF NOT EXISTS leagues(
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            code TEXT UNIQUE NOT NULL,
            admin_id INTEGER NOT NULL,
            transfers_locked INTEGER NOT NULL DEFAULT 0
        );
        CREATE TABLE IF NOT EXISTS managers(
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            telegram_id INTEGER UNIQUE NOT NULL,
            username TEXT,
            display_name TEXT NOT NULL,
            league_id INTEGER NOT NULL,
            bank INTEGER NOT NULL DEFAULT 1000,
            FOREIGN KEY(league_id) REFERENCES leagues(id)
        );
        CREATE TABLE IF NOT EXISTS squads(
            manager_id INTEGER NOT NULL,
            player_id INTEGER NOT NULL,
            PRIMARY KEY(manager_id, player_id),
            FOREIGN KEY(manager_id) REFERENCES managers(id)
        );
        CREATE TABLE IF NOT EXISTS lineups(
            manager_id INTEGER NOT NULL,
            gw INTEGER NOT NULL,
            player_id INTEGER NOT NULL,
            position INTEGER NOT NULL,
            is_starter INTEGER NOT NULL DEFAULT 1,
            PRIMARY KEY(manager_id, gw, player_id)
        );
        CREATE TABLE IF NOT EXISTS captains(
            manager_id INTEGER NOT NULL,
            gw INTEGER NOT NULL,
            captain_id INTEGER,
            vice_id INTEGER,
            PRIMARY KEY(manager_id, gw)
        );
        CREATE TABLE IF NOT EXISTS gw_scores(
            manager_id INTEGER NOT NULL,
            gw INTEGER NOT NULL,
            points INTEGER NOT NULL,
            PRIMARY KEY(manager_id, gw)
        );
        """)

def league_for_user(telegram_id):
    with conn() as c:
        return c.execute("SELECT m.*, l.name league_name, l.code, l.transfers_locked FROM managers m JOIN leagues l ON l.id=m.league_id WHERE m.telegram_id=?", (telegram_id,)).fetchone()

def create_league(name, admin_id):
    while True:
        code = secrets.token_hex(3).upper()
        try:
            with conn() as c:
                cur = c.execute("INSERT INTO leagues(name,code,admin_id) VALUES(?,?,?)",(name,code,admin_id))
                return cur.lastrowid, code
        except sqlite3.IntegrityError:
            pass

def join_league(telegram_id, username, display_name, code):
    with conn() as c:
        league = c.execute("SELECT * FROM leagues WHERE code=?", (code.upper(),)).fetchone()
        if not league: return None, "Invalid league code."
        if c.execute("SELECT 1 FROM managers WHERE telegram_id=?", (telegram_id,)).fetchone():
            return None, "You are already in a league."
        cur = c.execute("INSERT INTO managers(telegram_id,username,display_name,league_id) VALUES(?,?,?,?,?)",
                        (telegram_id,username,display_name,league["id"]))
        return cur.lastrowid, None

def managers(league_id):
    with conn() as c:
        return c.execute("SELECT * FROM managers WHERE league_id=? ORDER BY display_name",(league_id,)).fetchall()

def get_manager(mid):
    with conn() as c:
        return c.execute("SELECT * FROM managers WHERE id=?", (mid,)).fetchone()

def squad(mid):
    with conn() as c:
        return [r["player_id"] for r in c.execute("SELECT player_id FROM squads WHERE manager_id=?",(mid,)).fetchall()]

def add_player(mid,pid,cost):
    with conn() as c:
        c.execute("INSERT INTO squads(manager_id,player_id) VALUES(?,?)",(mid,pid))
        c.execute("UPDATE managers SET bank=bank-? WHERE id=?",(cost,mid))

def remove_player(mid,pid,cost):
    with conn() as c:
        c.execute("DELETE FROM squads WHERE manager_id=? AND player_id=?",(mid,pid))
        c.execute("UPDATE managers SET bank=bank+? WHERE id=?",(cost,mid))

def lineup(mid, gw):
    with conn() as c:
        return [dict(r) for r in c.execute("SELECT * FROM lineups WHERE manager_id=? AND gw=? ORDER BY position",(mid,gw)).fetchall()]

def save_lineup(mid,gw,players):
    with conn() as c:
        c.execute("DELETE FROM lineups WHERE manager_id=? AND gw=?",(mid,gw))
        for pos,pid,starter in players:
            c.execute("INSERT INTO lineups(manager_id,gw,player_id,position,is_starter) VALUES(?,?,?,?,?)",
                      (mid,gw,pid,pos,starter))

def save_captain(mid,gw,cap,vice):
    with conn() as c:
        c.execute("INSERT OR REPLACE INTO captains(manager_id,gw,captain_id,vice_id) VALUES(?,?,?,?)",(mid,gw,cap,vice))

def captain(mid,gw):
    with conn() as c:
        return c.execute("SELECT * FROM captains WHERE manager_id=? AND gw=?",(mid,gw)).fetchone()

def set_gw_score(mid,gw,points):
    with conn() as c:
        c.execute("INSERT OR REPLACE INTO gw_scores VALUES(?,?,?)",(mid,gw,points))

def standings(league_id):
    with conn() as c:
        return c.execute("""
        SELECT m.display_name,m.bank,COALESCE(SUM(s.points),0) total_points,
               COALESCE(SUM(CASE WHEN s.gw=(SELECT MAX(gw) FROM gw_scores WHERE manager_id=m.id) THEN s.points ELSE 0 END),0) last_points
        FROM managers m LEFT JOIN gw_scores s ON s.manager_id=m.id
        WHERE m.league_id=? GROUP BY m.id ORDER BY total_points DESC, m.display_name
        """,(league_id,)).fetchall()

def set_lock(league_id, locked):
    with conn() as c:
        c.execute("UPDATE leagues SET transfers_locked=? WHERE id=?",(int(locked),league_id))
