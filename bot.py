import os
import asyncio
from dotenv import load_dotenv
from telegram import Update
from telegram.ext import Application, CommandHandler, ContextTypes

import db
import fpl_api

load_dotenv()
TOKEN = os.getenv("BOT_TOKEN")
START_BUDGET = int(os.getenv("START_BUDGET","1000"))
MAX_CLUB = int(os.getenv("MAX_PLAYERS_FROM_CLUB","3"))
ADMIN_IDS = {int(x) for x in os.getenv("ADMIN_IDS","").split(",") if x.strip().isdigit()}

POS = {1:"GK",2:"DEF",3:"MID",4:"FWD"}
MAX_POS = {1:2,2:5,3:5,4:3}

def money(x): return f"£{x/10:.1f}m"

async def data():
    b = await fpl_api.bootstrap()
    return b, fpl_api.player_map(b), fpl_api.team_map(b)

async def user_manager(update):
    m = db.league_for_user(update.effective_user.id)
    if not m:
        await update.message.reply_text("You are not in a league. Use /createleague or /join CODE.")
    return m

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "⚽ Friends FPL Bot\n\n"
        "Create a private fantasy league for your Telegram friends.\n"
        "Use /help to see all commands."
    )

async def help_cmd(update, context):
    await update.message.reply_text(
        "Commands:\n"
        "/createleague - create your private league\n"
        "/join CODE - join a league\n"
        "/myleague - league info\n"
        "/players [GK|DEF|MID|FWD] - search player pool\n"
        "/player ID - player details\n"
        "/pick ID - buy a player\n"
        "/sell ID - sell a player\n"
        "/team - your squad and bank\n"
        "/lineup - show/set current XI\n"
        "/captain ID - set captain\n"
        "/vice ID - set vice captain\n"
        "/transfer OUT IN - transfer two players\n"
        "/standings - private league table\n"
        "/gw - current gameweek\n"
        "/refresh - refresh FPL data"
    )

async def createleague(update, context):
    if db.league_for_user(update.effective_user.id):
        await update.message.reply_text("You are already in a league.")
        return
    name = " ".join(context.args).strip() or "Friends FPL"
    lid, code = db.create_league(name, update.effective_user.id)
    db.join_league(update.effective_user.id, update.effective_user.username,
                   update.effective_user.full_name, code)
    await update.message.reply_text(f"🏆 League created: {name}\nInvite code: `{code}`\nSend friends: /join {code}", parse_mode="Markdown")

async def join(update, context):
    if not context.args:
        await update.message.reply_text("Usage: /join ABC123")
        return
    if db.league_for_user(update.effective_user.id):
        await update.message.reply_text("You are already in a league.")
        return
    mid, err = db.join_league(update.effective_user.id, update.effective_user.username,
                              update.effective_user.full_name, context.args[0])
    await update.message.reply_text(err or "✅ Joined the league. Build your 15-player squad!")

async def myleague(update, context):
    m = await user_manager(update)
    if not m: return
    await update.message.reply_text(f"🏆 {m['league_name']}\nCode: {m['code']}\nManagers: {len(db.managers(m['league_id']))}")

async def players(update, context):
    b, pm, tm = await data()
    filt = context.args[0].upper() if context.args else ""
    allowed = {v:k for k,v in POS.items()}
    ps = [p for p in pm.values() if not filt or POS.get(p["element_type"])==filt]
    ps.sort(key=lambda p:(-p.get("total_points",0), p["web_name"]))
    lines = [f"Players ({filt or 'all'}) — use /pick ID"]
    for p in ps[:30]:
        club = tm[p["team"]]["short_name"]
        lines.append(f'{p["id"]}. {p["web_name"]} | {POS[p["element_type"]]} | {money(p["now_cost"])} | {p["total_points"]} pts | {club}')
    await update.message.reply_text("\n".join(lines))

async def player(update, context):
    if not context.args or not context.args[0].isdigit():
        await update.message.reply_text("Usage: /player PLAYER_ID")
        return
    _,pm,tm = await data()
    p=pm.get(int(context.args[0]))
    if not p:
        await update.message.reply_text("Player not found.")
        return
    await update.message.reply_text(
        f'⚽ {p["first_name"]} {p["second_name"]}\n'
        f'ID: {p["id"]}\nPosition: {POS[p["element_type"]]}\n'
        f'Club: {tm[p["team"]]["name"]}\nPrice: {money(p["now_cost"])}\n'
        f'Total points: {p["total_points"]}\nForm: {p.get("form","-")}\n'
        f'Availability: {p.get("status","-")}'
    )

async def pick(update, context):
    m=await user_manager(update)
    if not m:return
    if not context.args or not context.args[0].isdigit():
        await update.message.reply_text("Usage: /pick PLAYER_ID"); return
    _,pm,tm=await data(); pid=int(context.args[0]); p=pm.get(pid)
    if not p: await update.message.reply_text("Player not found."); return
    s=db.squad(m["id"])
    if pid in s: await update.message.reply_text("You already own this player."); return
    if len(s)>=15: await update.message.reply_text("Squad full. Sell someone first."); return
    pos=p["element_type"]
    if sum(pm[x]["element_type"]==pos for x in s)>=MAX_POS[pos]:
        await update.message.reply_text(f"You already have the maximum number of {POS[pos]} players."); return
    if sum(pm[x]["team"]==p["team"] for x in s)>=MAX_CLUB:
        await update.message.reply_text("Maximum 3 players from one real club."); return
    cost=p["now_cost"]
    if m["bank"]<cost:
        await update.message.reply_text(f"Not enough budget. Bank: {money(m['bank'])}"); return
    db.add_player(m["id"],pid,cost)
    await update.message.reply_text(f"✅ Bought {p['web_name']} for {money(cost)}. Bank: {money(m['bank']-cost)}")

async def sell(update, context):
    m=await user_manager(update)
    if not m:return
    if not context.args or not context.args[0].isdigit():
        await update.message.reply_text("Usage: /sell PLAYER_ID"); return
    _,pm,_=await data(); pid=int(context.args[0])
    if pid not in db.squad(m["id"]): await update.message.reply_text("You don't own that player."); return
    p=pm[pid]; db.remove_player(m["id"],pid,p["now_cost"])
    await update.message.reply_text(f"✅ Sold {p['web_name']}. Bank: {money(m['bank']+p['now_cost'])}")

async def team(update, context):
    m=await user_manager(update)
    if not m:return
    _,pm,tm=await data(); s=db.squad(m["id"])
    lines=[f"👤 {m['display_name']} | Bank {money(m['bank'])}",f"Squad {len(s)}/15"]
    for pos in (1,2,3,4):
        arr=[pm[x] for x in s if pm[x]["element_type"]==pos]
        lines.append(f"\n{POS[pos]}")
        lines += [f'{p["id"]} {p["web_name"]} — {money(p["now_cost"])} ({tm[p["team"]]["short_name"]})' for p in arr]
    await update.message.reply_text("\n".join(lines))

def legal_formation(starters, pm):
    counts={p:sum(pm[x]["element_type"]==p for x in starters) for p in (1,2,3,4)}
    return counts[1]==1 and counts[2]>=3 and counts[3]>=2 and counts[4]>=1 and len(starters)==11

async def lineup(update, context):
    m=await user_manager(update,context)
    if not m:return
    b,pm,_=await data(); gw=fpl_api.current_event(b)["id"]; s=set(db.squad(m["id"]))
    if context.args:
        try: ids=[int(x) for x in context.args]
        except: ids=[]
        if len(ids)!=11 or not set(ids)<=s or len(set(ids))!=11:
            await update.message.reply_text("Usage: /lineup ID ID ... (exactly 11 players you own)"); return
        if not legal_formation(ids,pm):
            await update.message.reply_text("Illegal formation. Need 1 GK, at least 3 DEF, at least 2 MID and at least 1 FWD."); return
        rows=[]
        for i,pid in enumerate(ids):
            rows.append((i,pid,1))
        bench=[x for x in s if x not in ids]
        for j,pid in enumerate(bench, start=11):
            rows.append((j,pid,0))
        db.save_lineup(m["id"],gw,rows)
        await update.message.reply_text(f"✅ Starting XI saved for GW{gw}.")
        return
    rows=db.lineup(m["id"],gw)
    if not rows:
        await update.message.reply_text("No lineup saved for this GW. Set it with /lineup ID ID ...")
        return
    out=["📋 Starting XI"]
    for r in rows:
        if r["is_starter"]: out.append(f'{r["position"]+1}. {pm[r["player_id"]]["web_name"]}')
    await update.message.reply_text("\n".join(out))

async def captain_cmd(update, context):
    await set_cap(update, context, False)
async def vice(update, context):
    await set_cap(update, context, True)

async def set_cap(update, context, is_vice):
    m=await user_manager(update,context)
    if not m:return
    if not context.args or not context.args[0].isdigit():
        await update.message.reply_text("Usage: /captain PLAYER_ID"); return
    b,pm,_=await data(); gw=fpl_api.current_event(b)["id"]; pid=int(context.args[0])
    if pid not in db.squad(m["id"]):
        await update.message.reply_text("You don't own that player."); return
    c=db.captain(m["id"],gw)
    cap=c["captain_id"] if c else None; vc=c["vice_id"] if c else None
    if is_vice: vc=pid
    else: cap=pid
    db.save_captain(m["id"],gw,cap,vc)
    await update.message.reply_text(f"✅ {'Vice-captain' if is_vice else 'Captain'} set: {pm[pid]['web_name']}")

async def transfer(update, context):
    m=await user_manager(update,context)
    if not m:return
    if m["transfers_locked"]:
        await update.message.reply_text("Transfers are locked by the league admin."); return
    if len(context.args)!=2 or not all(x.isdigit() for x in context.args):
        await update.message.reply_text("Usage: /transfer OUT_ID IN_ID"); return
    _,pm,_=await data(); outp,inp=map(int,context.args)
    if outp not in db.squad(m["id"]): await update.message.reply_text("You don't own the outgoing player."); return
    if inp in db.squad(m["id"]): await update.message.reply_text("You already own the incoming player."); return
    p_in=pm.get(inp); p_out=pm.get(outp)
    if not p_in or not p_out: await update.message.reply_text("Player not found."); return
    # Remove outgoing temporarily, then validate incoming against remaining squad.
    s=[x for x in db.squad(m["id"]) if x!=outp]
    if len(s)>=15: pass
    if sum(pm[x]["element_type"]==p_in["element_type"] for x in s)>=MAX_POS[p_in["element_type"]]:
        await update.message.reply_text("Position limit would be exceeded."); return
    if sum(pm[x]["team"]==p_in["team"] for x in s)>=MAX_CLUB:
        await update.message.reply_text("Club limit would be exceeded."); return
    newbank=m["bank"]+p_out["now_cost"]-p_in["now_cost"]
    if newbank<0: await update.message.reply_text("Not enough budget."); return
    db.remove_player(m["id"],outp,p_out["now_cost"]); db.add_player(m["id"],inp,p_in["now_cost"])
    await update.message.reply_text(f"🔄 {p_out['web_name']} → {p_in['web_name']}")

async def standings_cmd(update, context):
    m=await user_manager(update)
    if not m:return
    rows=db.standings(m["league_id"])
    lines=["🏆 League standings"]
    for i,r in enumerate(rows,1):
        lines.append(f"{i}. {r['display_name']} — {r['total_points']} pts (GW {r['last_points']})")
    await update.message.reply_text("\n".join(lines))

async def gw(update, context):
    b,_,_=await data(); e=fpl_api.current_event(b)
    await update.message.reply_text(f"⚽ {e['name']}\nDeadline: {e.get('deadline_time','-')}\nFinished: {e.get('finished')}")

async def refresh(update, context):
    if ADMIN_IDS and update.effective_user.id not in ADMIN_IDS:
        await update.message.reply_text("Admin only."); return
    await fpl_api.refresh_cache()
    await update.message.reply_text("✅ FPL data cache refreshed.")

async def score_current_gw():
    b,pm,_=await data()
    e=fpl_api.current_event(b); gwid=e["id"]
    if not e.get("finished"): return
    live=await fpl_api.live(gwid)
    pts={x["id"]:x["stats"].get("total_points",0) for x in live.get("elements",[])}
    for manager in db.managers(1_000_000_000):  # no-op compatibility; league IDs are handled below
        pass
    # Score every manager in every league.
    import sqlite3
    with db.conn() as c:
        managers=c.execute("SELECT * FROM managers").fetchall()
    for m in managers:
        rows=db.lineup(m["id"],gwid)
        if not rows: continue
        starters=[r["player_id"] for r in rows if r["is_starter"]]
        caprow=db.captain(m["id"],gwid)
        cap=caprow["captain_id"] if caprow else None
        vice=caprow["vice_id"] if caprow else None
        total=0
        used=set()
        # Auto-sub zero-minute starters using bench in saved order, if formation remains legal.
        for pid in starters:
            if pts.get(pid,0) != 0:
                total += pts.get(pid,0) * (2 if pid==cap else 1)
                used.add(pid)
        bench=[r["player_id"] for r in rows if not r["is_starter"]]
        for pid in starters:
            if pts.get(pid,0)==0:
                for sub in bench:
                    if sub in used: continue
                    candidate=[x for x in starters if x!=pid and x in used] + [sub]
                    # Basic position-count validation.
                    poscounts={p:0 for p in (1,2,3,4)}
                    for x in candidate: poscounts[pm[x]["element_type"]]+=1
                    if poscounts[1]==1 and poscounts[2]>=3 and poscounts[3]>=2 and poscounts[4]>=1 and len(candidate)==11:
                        total += pts.get(sub,0) * (2 if pid==cap else 1)
                        used.add(sub); break
        db.set_gw_score(m["id"],gwid,total)

async def scheduled_scoring(context):
    try:
        await score_current_gw()
    except Exception:
        pass

def main():
    if not TOKEN:
        raise SystemExit("BOT_TOKEN is missing. Copy .env.example to .env and add your BotFather token.")
    db.init()
    app=Application.builder().token(TOKEN).build()
    handlers=[
        ("start",start),("help",help_cmd),("createleague",createleague),("join",join),
        ("myleague",myleague),("players",players),("player",player),("pick",pick),
        ("sell",sell),("team",team),("lineup",lineup),("captain",captain_cmd),
        ("vice",vice),("transfer",transfer),("standings",standings_cmd),("gw",gw),
        ("refresh",refresh)
    ]
    for name,fn in handlers: app.add_handler(CommandHandler(name,fn))
    if app.job_queue:
        app.job_queue.run_repeating(scheduled_scoring, interval=900, first=60)
    print("Friends FPL bot is running...")
    app.run_polling()

if __name__=="__main__":
    main()
