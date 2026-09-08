# Telegram Friends FPL Bot

A private Telegram fantasy Premier League bot for you and your friends.

## What it includes
- Private league with an invite code
- 100.0m-style budget (stored as 1000 tenths)
- 15-player squad: 2 GK, 5 DEF, 5 MID, 3 FWD
- Max 3 players from one real club
- Starting XI + bench
- Captain and vice-captain
- Transfers
- Automatic gameweek points from the public Fantasy Premier League data endpoints
- Auto-substitution after a gameweek when a starter has 0 minutes
- League standings
- Player search
- SQLite database
- Admin commands to lock/unlock transfers and refresh data

## Important
This is a separate fantasy game for your Telegram group. It does not log into users' official FPL accounts.

The bot uses the public FPL endpoints for player prices and gameweek/live player statistics. Those endpoints are commonly used by FPL tools, but they are not a formal third-party developer API contract, so keep the data-provider code isolated in `fpl_api.py`.

## 1. Create the Telegram bot
In Telegram, open @BotFather and use `/newbot`.
Copy the token into `.env`.

Never publish your token.

## 2. Install
Python 3.11+ is recommended.

```bash
python -m venv .venv
# Linux/macOS:
source .venv/bin/activate
# Windows:
# .venv\Scripts\activate

pip install -r requirements.txt
cp .env.example .env
```

Edit `.env` and put your token.

## 3. Run
```bash
python bot.py
```

The database `fantasy.sqlite3` is created automatically.

## Main commands
- `/start`
- `/help`
- `/createleague`
- `/join CODE`
- `/myleague`
- `/players`
- `/player PLAYER_ID`
- `/pick PLAYER_ID`
- `/sell PLAYER_ID`
- `/lineup`
- `/captain PLAYER_ID`
- `/transfer OUT_ID IN_ID`
- `/team`
- `/standings`
- `/gw`
- `/refresh`

## Recommended first setup
1. Start the bot.
2. Send `/createleague`.
3. Share the generated code with friends.
4. Each friend sends `/join CODE`.
5. Everyone builds a 15-player squad.
6. Set a starting XI with `/lineup`.
7. Set captain with `/captain PLAYER_ID`.
8. Use `/standings` to see the private league.

## Hosting
For a small friends league, any always-on Python host/VPS is sufficient. Keep the SQLite file on persistent storage. For production, switch to PostgreSQL if you expect many leagues/users.

## Scoring
The bot imports FPL live `total_points` for each player. Captain gets 2x. If a starter plays 0 minutes, the bot tries to auto-substitute an eligible bench player while preserving a legal formation.

Because the source is the FPL data feed, scoring follows the current FPL points already calculated by that feed rather than duplicating the scoring formula in this bot.
