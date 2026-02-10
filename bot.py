import os
import json
import time
import asyncio
from dataclasses import dataclass, field
from typing import Dict, Optional, Set, List
from aiohttp import web

import discord
from discord import app_commands
from discord.ext import commands
from dotenv import load_dotenv

# =========================
# Configuration
# =========================
ALLOW_ROLE_CREATION = True

DATA_DIR = "data"
USERS_PATH = os.path.join(DATA_DIR, "users.json")
SESSIONS_PATH = os.path.join(DATA_DIR, "sessions.json")
CONFIG_PATH = os.path.join(DATA_DIR, "config.json")

DEFAULT_CONFIG = {
    "checkin_interval_minutes": 120,
    "checkin_grace_minutes": 10,
    "announce_every_minutes": 10,
    "default_focus_minutes": 50,
    "default_break_minutes": 10,
    "tier_bronze": 100,
    "tier_silver": 300,
    "tier_gold": 700,
    "tier_elite": 1500,
    "weekly_days": 7,
    "roles": {
        "completed_today": "✅ Completed Today",
        "streak_1": "🔥 1 Day streak",
        "top_achiever": "💎 Topachiever",
        "weekly_top10": "🏆 Weekly Top 10",
        "tier_bronze": "🟩 Focus Bronze",
        "tier_silver": "🟦 Focus Silver",
        "tier_gold": "🟪 Focus Gold",
        "tier_elite": "🟥 Focus Elite"
    }
}

# =========================
# Data persistence
# =========================


def ensure_files():
    os.makedirs(DATA_DIR, exist_ok=True)
    for p in [USERS_PATH, SESSIONS_PATH]:
        if not os.path.exists(p):
            with open(p, "w", encoding="utf-8") as f:
                f.write("{}")
    if not os.path.exists(CONFIG_PATH):
        with open(CONFIG_PATH, "w", encoding="utf-8") as f:
            json.dump(DEFAULT_CONFIG, f, indent=2)


def load_json(path: str) -> dict:
    try:
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return {}


def save_json_atomic(path: str, data: dict):
    tmp = path + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
    os.replace(tmp, path)


def load_config() -> dict:
    cfg = load_json(CONFIG_PATH)
    merged = DEFAULT_CONFIG.copy()
    merged.update({k: v for k, v in cfg.items() if k != "roles"})
    roles = DEFAULT_CONFIG["roles"].copy()
    roles.update(cfg.get("roles", {}))
    merged["roles"] = roles
    return merged


def now_ts() -> int:
    return int(time.time())


def day_key(ts: Optional[int] = None) -> str:
    if ts is None:
        ts = now_ts()
    return time.strftime("%Y-%m-%d", time.localtime(ts))


def user_key(guild_id: int, user_id: int) -> str:
    return f"{guild_id}:{user_id}"


# =========================
# Scoring system
# =========================

SCORE_FINISH_SESSION = 10
SCORE_CHECKIN_OK = 5
SCORE_CHECKIN_MISSED = -15
SCORE_LEAVE_MID = -5
SCORE_GOAL_COMPLETE = 5


def clamp_nonneg(x: int) -> int:
    return x if x > 0 else 0


def add_focus_score(u: dict, delta: int):
    u["focus_score"] = clamp_nonneg(int(u.get("focus_score", 0)) + delta)


def add_minutes(u: dict, minutes: int):
    u["total_minutes"] = clamp_nonneg(int(u.get("total_minutes", 0)) + minutes)


def update_streak(u: dict, finished_day: str):
    last_day = u.get("last_study_day")
    if last_day is None:
        u["streak"] = 1
        u["last_study_day"] = finished_day
        return
    if last_day == finished_day:
        return

    try:
        t_last = time.strptime(last_day, "%Y-%m-%d")
        t_now = time.strptime(finished_day, "%Y-%m-%d")
        sec_last = int(time.mktime(t_last))
        sec_now = int(time.mktime(t_now))
        delta_days = (sec_now - sec_last) // 86400
    except Exception:
        delta_days = 999

    if delta_days == 1:
        u["streak"] = int(u.get("streak", 0)) + 1
    else:
        u["streak"] = 1
    u["last_study_day"] = finished_day


# =========================
# Active sessions
# =========================


@dataclass
class ActiveSession:
    guild_id: int
    vc_id: int
    text_channel_id: int
    mode: str
    started_at: int
    duration_minutes: int
    ends_at: int
    participants: Set[int] = field(default_factory=set)
    goals: Dict[int, str] = field(default_factory=dict)
    last_announce_at: int = 0
    stopped: bool = False


active_sessions: Dict[int, ActiveSession] = {}

# =========================
# Discord setup
# =========================

load_dotenv()
TOKEN = os.getenv("DISCORD_TOKEN")

intents = discord.Intents.default()
intents.guilds = True
intents.members = True

ensure_files()
CONFIG = load_config()

ROLE_CACHE: Dict[int, Dict[str, int]] = {}

# =========================
# Helper functions
# =========================


def make_embed(title: str, desc: str, color: int = 0x5865F2) -> discord.Embed:
    return discord.Embed(title=title, description=desc, color=color)


def get_or_create_user(users_db: dict, guild_id: int, user_id: int) -> dict:
    k = user_key(guild_id, user_id)
    if k not in users_db:
        users_db[k] = {
            "user_id": user_id,
            "guild_id": guild_id,
            "focus_score": 0,
            "total_minutes": 0,
            "sessions_completed": 0,
            "streak": 0,
            "last_study_day": None,
            "last_checkin_ts": 0,
            "pending_checkin_until": 0,
            "ghost_mode": False
        }
    return users_db[k]


async def get_user_vc(
        interaction: discord.Interaction) -> Optional[discord.VoiceChannel]:
    if not interaction.guild:
        return None
    member = interaction.guild.get_member(interaction.user.id)
    if not member or not member.voice or not member.voice.channel:
        return None
    ch = member.voice.channel
    if isinstance(ch, discord.VoiceChannel):
        return ch
    return None


def list_vc_members(vc: discord.VoiceChannel) -> List[discord.Member]:
    return [m for m in vc.members if not m.bot]


def human_mins(seconds: int) -> str:
    seconds = max(0, seconds)
    m = seconds // 60
    s = seconds % 60
    return f"{m}m {s}s"


# =========================
# Role management
# =========================


async def ensure_roles(guild: discord.Guild) -> Dict[str, discord.Role]:
    role_names = CONFIG["roles"]
    out: Dict[str, discord.Role] = {}
    by_name = {r.name: r for r in guild.roles}

    for key, name in role_names.items():
        role = by_name.get(name)
        if role is None:
            try:
                if ALLOW_ROLE_CREATION:
                    role = await guild.create_role(
                        name=name, reason="StudyHive auto-setup")
            except discord.Forbidden:
                continue
        if role:
            out[key] = role

    ROLE_CACHE[guild.id] = {k: v.id for k, v in out.items()}
    return out


async def add_role(member: discord.Member, role: discord.Role):
    if role not in member.roles:
        try:
            await member.add_roles(role, reason="StudyHive auto-roles")
        except discord.Forbidden:
            pass


async def remove_role(member: discord.Member, role: discord.Role):
    if role in member.roles:
        try:
            await member.remove_roles(role, reason="StudyHive auto-roles")
        except discord.Forbidden:
            pass


def focus_tier_key(score: int) -> str:
    if score >= int(CONFIG["tier_elite"]):
        return "tier_elite"
    if score >= int(CONFIG["tier_gold"]):
        return "tier_gold"
    if score >= int(CONFIG["tier_silver"]):
        return "tier_silver"
    if score >= int(CONFIG["tier_bronze"]):
        return "tier_bronze"
    return ""


async def apply_user_roles(guild: discord.Guild, member: discord.Member,
                           u: dict):
    roles_map = await ensure_roles(guild)
    score = int(u.get("focus_score", 0))
    streak = int(u.get("streak", 0))
    today = day_key()
    last_day = u.get("last_study_day")

    completed_role = roles_map.get("completed_today")
    if completed_role:
        if last_day == today:
            await add_role(member, completed_role)
        else:
            await remove_role(member, completed_role)

    streak_role = roles_map.get("streak_1")
    if streak_role:
        if streak >= 1:
            await add_role(member, streak_role)
        else:
            await remove_role(member, streak_role)

    tier_keys = ["tier_bronze", "tier_silver", "tier_gold", "tier_elite"]
    desired = focus_tier_key(score)

    for k in tier_keys:
        r = roles_map.get(k)
        if not r:
            continue
        if k == desired:
            await add_role(member, r)
        else:
            await remove_role(member, r)


async def apply_weekly_roles(guild: discord.Guild):
    roles_map = await ensure_roles(guild)
    top_ach = roles_map.get("top_achiever")
    weekly_top10 = roles_map.get("weekly_top10")

    users_db = load_json(USERS_PATH)
    sessions_db = load_json(SESSIONS_PATH)

    users = [
        u for u in users_db.values() if int(u.get("guild_id", 0)) == guild.id
    ]
    if not users:
        return

    users_sorted = sorted(users,
                          key=lambda x: int(x.get("focus_score", 0)),
                          reverse=True)
    top_user_id = int(users_sorted[0]["user_id"])

    days = int(CONFIG.get("weekly_days", 7))
    cutoff = now_ts() - days * 86400
    minutes_by_user: Dict[int, int] = {}

    for rec in sessions_db.values():
        if not isinstance(rec, dict):
            continue
        if rec.get("type") == "checkin":
            continue
        if int(rec.get("guild_id", 0)) != guild.id:
            continue
        if rec.get("mode") != "focus":
            continue
        started = int(rec.get("started_at", 0))
        if started < cutoff:
            continue
        dur = int(rec.get("duration_minutes", 0))
        for uid in rec.get("participants", []):
            minutes_by_user[int(uid)] = minutes_by_user.get(int(uid), 0) + dur

    weekly_sorted = sorted(minutes_by_user.items(),
                           key=lambda kv: kv[1],
                           reverse=True)
    weekly_top_ids = [uid for uid, _mins in weekly_sorted[:10]]

    for member in guild.members:
        if member.bot:
            continue

        if top_ach:
            if member.id == top_user_id:
                await add_role(member, top_ach)
            else:
                await remove_role(member, top_ach)

        if weekly_top10:
            if member.id in weekly_top_ids and weekly_top_ids:
                await add_role(member, weekly_top10)
            else:
                await remove_role(member, weekly_top10)


# =========================
# Session management
# =========================


async def stop_session(vc_id: int, reason: str = "Stopped"):
    sess = active_sessions.get(vc_id)
    if not sess or sess.stopped:
        return
    sess.stopped = True

    sessions_db = load_json(SESSIONS_PATH)
    sid = f"{sess.guild_id}:{sess.vc_id}:{sess.started_at}"
    rec = sessions_db.get(sid, {})
    rec["ended_at"] = now_ts()
    rec["stop_reason"] = reason
    sessions_db[sid] = rec
    save_json_atomic(SESSIONS_PATH, sessions_db)

    del active_sessions[vc_id]


async def run_session_loop(guild: discord.Guild, vc: discord.VoiceChannel,
                           text_ch: discord.TextChannel, sess: ActiveSession):
    announce_every = int(CONFIG.get("announce_every_minutes", 10))

    sessions_db = load_json(SESSIONS_PATH)
    sid = f"{sess.guild_id}:{sess.vc_id}:{sess.started_at}"
    sessions_db[sid] = {
        "guild_id": sess.guild_id,
        "vc_id": sess.vc_id,
        "text_channel_id": sess.text_channel_id,
        "mode": sess.mode,
        "started_at": sess.started_at,
        "duration_minutes": sess.duration_minutes,
        "ends_at": sess.ends_at,
        "participants": list(sess.participants),
        "goals": sess.goals
    }
    save_json_atomic(SESSIONS_PATH, sessions_db)

    title = "📚 Focus started" if sess.mode == "focus" else "☕ Break started"
    await text_ch.send(embed=make_embed(
        title,
        f"VC: **{vc.name}**\nDuration: **{sess.duration_minutes} min**\nParticipants: **{len(sess.participants)}**"
    ))

    while not sess.stopped:
        now = now_ts()
        if now >= sess.ends_at:
            break

        current_ids = {m.id for m in list_vc_members(vc)}
        left = sess.participants - current_ids
        joined = current_ids - sess.participants

        if left:
            users_db = load_json(USERS_PATH)
            for uid in left:
                u = get_or_create_user(users_db, guild.id, uid)
                add_focus_score(u, SCORE_LEAVE_MID)
            save_json_atomic(USERS_PATH, users_db)
            sess.participants -= left

        if joined:
            sess.participants |= joined

        if sess.last_announce_at == 0 or (
                now - sess.last_announce_at) >= announce_every * 60:
            remaining = sess.ends_at - now
            await text_ch.send(
                f"⏳ **{sess.mode.upper()}** remaining: **{human_mins(remaining)}** | In VC: **{len(sess.participants)}**"
            )
            sess.last_announce_at = now

        await asyncio.sleep(15)

    if sess.stopped:
        return

    # Session completed - ping participants
    if sess.mode == "focus":
        users_db = load_json(USERS_PATH)
        finished_day = day_key(sess.ends_at)

        # Prepare mentions
        mentions = []
        for uid in list(sess.participants):
            u = get_or_create_user(users_db, guild.id, uid)
            add_minutes(u, sess.duration_minutes)
            u["sessions_completed"] = int(u.get("sessions_completed", 0)) + 1
            add_focus_score(u, SCORE_FINISH_SESSION)
            update_streak(u, finished_day)

            member = guild.get_member(uid)
            if member:
                mentions.append(member.mention)

        save_json_atomic(USERS_PATH, users_db)

        sessions_db = load_json(SESSIONS_PATH)
        rec = sessions_db.get(sid, {})
        rec["participants"] = list(sess.participants)
        rec["goals"] = sess.goals
        rec["ended_at"] = now_ts()
        sessions_db[sid] = rec
        save_json_atomic(SESSIONS_PATH, sessions_db)

        for uid in sess.participants:
            member = guild.get_member(uid)
            if member:
                u = get_or_create_user(users_db, guild.id, uid)
                await apply_user_roles(guild, member, u)

        await apply_weekly_roles(guild)

        # Ping all participants
        mention_str = " ".join(mentions) if mentions else ""
        await text_ch.send(
            f"🎉 **FOCUS SESSION COMPLETE!** {mention_str}\n"
            f"✅ You earned **+{SCORE_FINISH_SESSION} Focus Score**!\n"
            f"☕ Take a break with `/break 10`")
    else:
        await text_ch.send(
            "⏰ **BREAK ended!** 📚 Ready to focus? Use `/focus 50`")

    if vc.id in active_sessions:
        del active_sessions[vc_id]


# =========================
# Accountability loop
# =========================


async def accountability_loop(bot_ref: commands.Bot):
    await bot_ref.wait_until_ready()

    while not bot_ref.is_closed():
        try:
            users_db = load_json(USERS_PATH)
            checkin_interval = int(CONFIG.get("checkin_interval_minutes", 120))
            grace = int(CONFIG.get("checkin_grace_minutes", 10))
            now = now_ts()
            changed = False

            for u in users_db.values():
                guild_id = int(u.get("guild_id", 0))
                user_id = int(u.get("user_id", 0))
                if bool(u.get("ghost_mode", False)):
                    continue

                pending_until = int(u.get("pending_checkin_until", 0))
                last_checkin = int(u.get("last_checkin_ts", 0))

                if pending_until and now > pending_until:
                    add_focus_score(u, SCORE_CHECKIN_MISSED)
                    u["pending_checkin_until"] = 0
                    changed = True
                    continue

                if pending_until == 0 and last_checkin and (
                        now - last_checkin) >= checkin_interval * 60:
                    for sess in active_sessions.values():
                        if sess.mode != "focus":
                            continue
                        if sess.guild_id != guild_id:
                            continue
                        if user_id not in sess.participants:
                            continue

                        text_ch = bot_ref.get_channel(sess.text_channel_id)
                        if isinstance(text_ch, discord.TextChannel):
                            member = text_ch.guild.get_member(
                                user_id) if text_ch.guild else None
                            mention = member.mention if member else f"<@{user_id}>"
                            u["pending_checkin_until"] = now + grace * 60
                            u["last_checkin_ts"] = now
                            changed = True
                            await text_ch.send(
                                f"🧠 Check-in {mention}: **What are you working on right now?**\n"
                                f"Reply with `/checkin <your update>` within **{grace} minutes**."
                            )
                        break

            if changed:
                save_json_atomic(USERS_PATH, users_db)

        except Exception as e:
            print("Accountability loop error:", e)

        await asyncio.sleep(60)


async def weekly_roles_loop(bot_ref: commands.Bot):
    await bot_ref.wait_until_ready()
    while not bot_ref.is_closed():
        try:
            for guild in bot_ref.guilds:
                await apply_weekly_roles(guild)
        except Exception as e:
            print("Weekly roles loop error:", e)
        await asyncio.sleep(3600)


# =========================
# Web dashboard
# =========================


async def start_web_server():
    # Replit uses PORT env var, default to 8080 if not set
    port = int(os.getenv("PORT", "8080"))

    print(f"[web] Starting web server on port {port}...")

    async def dashboard(request):
        users_db = load_json(USERS_PATH)
        sessions_db = load_json(SESSIONS_PATH)

        # Get stats
        total_users = len(users_db)
        total_sessions = len([
            s for s in sessions_db.values()
            if isinstance(s, dict) and s.get("mode") == "focus"
        ])
        active_count = len(active_sessions)

        # Top users
        all_users = list(users_db.values())
        all_users.sort(key=lambda x: int(x.get("focus_score", 0)),
                       reverse=True)
        top_10 = all_users[:10]

        leaderboard_html = ""
        for i, u in enumerate(top_10, 1):
            leaderboard_html += f"""
            <tr>
                <td>{i}</td>
                <td>User {u.get('user_id')}</td>
                <td>{u.get('focus_score', 0)}</td>
                <td>{u.get('total_minutes', 0)}</td>
                <td>{u.get('streak', 0)}</td>
            </tr>
            """

        html = f"""
        <!DOCTYPE html>
        <html>
        <head>
            <title>StudyHive Dashboard</title>
            <meta name="viewport" content="width=device-width, initial-scale=1">
            <style>
                * {{ margin: 0; padding: 0; box-sizing: border-box; }}
                body {{
                    font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, Oxygen, Ubuntu, sans-serif;
                    background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
                    min-height: 100vh;
                    padding: 20px;
                }}
                .container {{
                    max-width: 1200px;
                    margin: 0 auto;
                }}
                .header {{
                    text-align: center;
                    color: white;
                    margin-bottom: 40px;
                }}
                .header h1 {{
                    font-size: 3em;
                    margin-bottom: 10px;
                    text-shadow: 2px 2px 4px rgba(0,0,0,0.2);
                }}
                .stats {{
                    display: grid;
                    grid-template-columns: repeat(auto-fit, minmax(250px, 1fr));
                    gap: 20px;
                    margin-bottom: 40px;
                }}
                .stat-card {{
                    background: white;
                    padding: 30px;
                    border-radius: 15px;
                    box-shadow: 0 10px 30px rgba(0,0,0,0.2);
                    text-align: center;
                }}
                .stat-card h3 {{
                    color: #667eea;
                    font-size: 2.5em;
                    margin-bottom: 10px;
                }}
                .stat-card p {{
                    color: #666;
                    font-size: 1.1em;
                }}
                .leaderboard {{
                    background: white;
                    padding: 30px;
                    border-radius: 15px;
                    box-shadow: 0 10px 30px rgba(0,0,0,0.2);
                }}
                .leaderboard h2 {{
                    color: #667eea;
                    margin-bottom: 20px;
                    font-size: 2em;
                }}
                table {{
                    width: 100%;
                    border-collapse: collapse;
                }}
                th {{
                    background: #667eea;
                    color: white;
                    padding: 15px;
                    text-align: left;
                }}
                td {{
                    padding: 15px;
                    border-bottom: 1px solid #eee;
                }}
                tr:hover {{
                    background: #f5f5f5;
                }}
                .status {{
                    display: inline-block;
                    padding: 5px 15px;
                    border-radius: 20px;
                    font-size: 0.9em;
                    font-weight: bold;
                }}
                .status.online {{
                    background: #4caf50;
                    color: white;
                }}
                @media (max-width: 768px) {{
                    .header h1 {{ font-size: 2em; }}
                    .stat-card h3 {{ font-size: 2em; }}
                }}
            </style>
        </head>
        <body>
            <div class="container">
                <div class="header">
                    <h1>📚 StudyHive Dashboard</h1>
                    <p style="font-size: 1.2em; opacity: 0.9;">Focus. Track. Achieve.</p>
                    <p style="margin-top: 10px;"><span class="status online">● ONLINE</span></p>
                </div>

                <div class="stats">
                    <div class="stat-card">
                        <h3>{total_users}</h3>
                        <p>Total Users</p>
                    </div>
                    <div class="stat-card">
                        <h3>{total_sessions}</h3>
                        <p>Sessions Completed</p>
                    </div>
                    <div class="stat-card">
                        <h3>{active_count}</h3>
                        <p>Active Sessions</p>
                    </div>
                </div>

                <div class="leaderboard">
                    <h2>🏆 Top 10 Focus Champions</h2>
                    <table>
                        <thead>
                            <tr>
                                <th>Rank</th>
                                <th>User</th>
                                <th>Focus Score</th>
                                <th>Minutes</th>
                                <th>Streak</th>
                            </tr>
                        </thead>
                        <tbody>
                            {leaderboard_html if leaderboard_html else '<tr><td colspan="5" style="text-align: center; padding: 40px; color: #999;">No data yet. Start your first focus session!</td></tr>'}
                        </tbody>
                    </table>
                </div>
            </div>
        </body>
        </html>
        """
        return web.Response(text=html, content_type='text/html')

    async def health(request):
        return web.Response(text="StudyHive bot is alive ✅")

    async def stats_api(request):
        users_db = load_json(USERS_PATH)
        sessions_db = load_json(SESSIONS_PATH)

        data = {
            "status":
            "online",
            "total_users":
            len(users_db),
            "total_sessions":
            len([s for s in sessions_db.values() if isinstance(s, dict)]),
            "active_sessions":
            len(active_sessions),
            "uptime":
            int(time.time() - bot_start_time)
        }
        return web.json_response(data)

    app = web.Application()
    app.router.add_get("/", dashboard)
    app.router.add_get("/health", health)
    app.router.add_get("/api/stats", stats_api)

    runner = web.AppRunner(app)
    await runner.setup()

    site = web.TCPSite(runner, "0.0.0.0", port)
    await site.start()

    print(f"[web] ✅ Dashboard live at http://0.0.0.0:{port}")
    print(f"[web] ✅ Health check at http://0.0.0.0:{port}/health")


# =========================
# Bot class
# =========================

bot_start_time = time.time()


class StudyHiveBot(commands.Bot):

    async def setup_hook(self):
        print("[bot] Setting up bot...")

        # Start web server FIRST - this is critical for Replit
        await start_web_server()

        # Then start background tasks
        asyncio.create_task(accountability_loop(self))
        asyncio.create_task(weekly_roles_loop(self))

        try:
            synced = await self.tree.sync()
            print(f"[bot] ✅ Synced {len(synced)} commands")
        except Exception as e:
            print(f"[bot] ⚠️  Command sync error: {e}")


bot = StudyHiveBot(command_prefix="!", intents=intents)


@bot.event
async def on_ready():
    print(f"[bot] ✅ StudyHive online as {bot.user}")
    print(f"[bot] Connected to {len(bot.guilds)} server(s)")

    # Create roles on startup for each guild
    for guild in bot.guilds:
        try:
            await ensure_roles(guild)
            print(f"[bot] ✅ Roles ready for: {guild.name}")
        except Exception as e:
            print(f"[bot] ⚠️  Role setup error in {guild.name}: {e}")


@bot.event
async def on_voice_state_update(member: discord.Member,
                                before: discord.VoiceState,
                                after: discord.VoiceState):
    if member.bot or not member.guild:
        return

    if before.channel is None and after.channel is not None:
        for ch in member.guild.text_channels:
            if "commands" in ch.name.lower() or "bot" in ch.name.lower():
                try:
                    await ch.send(
                        f"👋 {member.mention} joined **{after.channel.name}**!\n"
                        f"Start strong: `/focus 50` and `/goal <what you'll do>` ✅"
                    )
                    break
                except discord.Forbidden:
                    pass


# =========================
# Commands
# =========================


@bot.tree.command(name="focus", description="Start a focus session")
@app_commands.describe(minutes="Duration in minutes (default 50)")
async def focus_cmd(interaction: discord.Interaction,
                    minutes: Optional[int] = None):
    await interaction.response.defer(ephemeral=True)

    vc = await get_user_vc(interaction)
    if not vc:
        await interaction.followup.send("Join a voice channel first!",
                                        ephemeral=True)
        return

    if vc.id in active_sessions:
        await interaction.followup.send(
            "Session already running. Use `/stop` first.", ephemeral=True)
        return

    mins = int(minutes or CONFIG.get("default_focus_minutes", 50))
    mins = max(5, min(mins, 180))

    members = list_vc_members(vc)
    if not members:
        await interaction.followup.send("No members in VC!", ephemeral=True)
        return

    if not isinstance(interaction.channel, discord.TextChannel):
        await interaction.followup.send("Run this in a text channel!",
                                        ephemeral=True)
        return

    text_ch = interaction.channel

    sess = ActiveSession(guild_id=interaction.guild_id,
                         vc_id=vc.id,
                         text_channel_id=text_ch.id,
                         mode="focus",
                         started_at=now_ts(),
                         duration_minutes=mins,
                         ends_at=now_ts() + mins * 60,
                         participants={m.id
                                       for m in members})

    users_db = load_json(USERS_PATH)
    for m in members:
        u = get_or_create_user(users_db, interaction.guild_id, m.id)
        if int(u.get("last_checkin_ts", 0)) == 0:
            u["last_checkin_ts"] = now_ts()
    save_json_atomic(USERS_PATH, users_db)

    active_sessions[vc.id] = sess
    asyncio.create_task(run_session_loop(interaction.guild, vc, text_ch, sess))

    await interaction.followup.send(
        f"✅ Started **FOCUS {mins} min** in {vc.name}", ephemeral=True)


@bot.tree.command(name="break", description="Start a break session")
@app_commands.describe(minutes="Duration in minutes (default 10)")
async def break_cmd(interaction: discord.Interaction,
                    minutes: Optional[int] = None):
    await interaction.response.defer(ephemeral=True)

    vc = await get_user_vc(interaction)
    if not vc:
        await interaction.followup.send("Join a voice channel first!",
                                        ephemeral=True)
        return

    if vc.id in active_sessions:
        await interaction.followup.send(
            "Session already running. Use `/stop` first.", ephemeral=True)
        return

    mins = int(minutes or CONFIG.get("default_break_minutes", 10))
    mins = max(3, min(mins, 60))

    if not isinstance(interaction.channel, discord.TextChannel):
        await interaction.followup.send("Run this in a text channel!",
                                        ephemeral=True)
        return

    text_ch = interaction.channel
    members = list_vc_members(vc)

    sess = ActiveSession(guild_id=interaction.guild_id,
                         vc_id=vc.id,
                         text_channel_id=text_ch.id,
                         mode="break",
                         started_at=now_ts(),
                         duration_minutes=mins,
                         ends_at=now_ts() + mins * 60,
                         participants={m.id
                                       for m in members})

    active_sessions[vc.id] = sess
    asyncio.create_task(run_session_loop(interaction.guild, vc, text_ch, sess))

    await interaction.followup.send(f"☕ Started **BREAK {mins} min**",
                                    ephemeral=True)


@bot.tree.command(name="stop", description="Stop the current session")
async def stop_cmd(interaction: discord.Interaction):
    await interaction.response.defer(ephemeral=True)

    vc = await get_user_vc(interaction)
    if not vc:
        await interaction.followup.send("Join the VC with the session first!",
                                        ephemeral=True)
        return

    if vc.id not in active_sessions:
        await interaction.followup.send("No active session in this VC.",
                                        ephemeral=True)
        return

    await stop_session(vc.id, reason=f"Stopped by {interaction.user.id}")
    await interaction.followup.send("✅ Session stopped.", ephemeral=True)


@bot.tree.command(name="time", description="Show remaining time")
async def time_cmd(interaction: discord.Interaction):
    await interaction.response.defer(ephemeral=True)

    vc = await get_user_vc(interaction)
    if not vc:
        await interaction.followup.send("Join a voice channel first!",
                                        ephemeral=True)
        return

    if vc.id not in active_sessions:
        await interaction.followup.send("No active session.", ephemeral=True)
        return

    sess = active_sessions[vc.id]
    remaining = sess.ends_at - now_ts()

    await interaction.followup.send(
        f"⏳ **{sess.mode.upper()} remaining:** {human_mins(remaining)}",
        ephemeral=True)


@bot.tree.command(name="goal", description="Set your goal for this session")
@app_commands.describe(text="What you will work on")
async def goal_cmd(interaction: discord.Interaction, text: str):
    await interaction.response.defer(ephemeral=True)

    vc = await get_user_vc(interaction)
    if not vc or vc.id not in active_sessions:
        await interaction.followup.send(
            "Join a VC with an active session first!", ephemeral=True)
        return

    sess = active_sessions[vc.id]
    if sess.mode != "focus":
        await interaction.followup.send(
            "Goals only work during focus sessions!", ephemeral=True)
        return

    if interaction.user.id not in sess.participants:
        await interaction.followup.send("Join the VC to participate!",
                                        ephemeral=True)
        return

    sess.goals[interaction.user.id] = text[:200]
    await interaction.followup.send("✅ Goal saved!", ephemeral=True)


@bot.tree.command(name="goal_done", description="Mark your goal as complete")
async def goal_done_cmd(interaction: discord.Interaction):
    await interaction.response.defer(ephemeral=True)

    vc = await get_user_vc(interaction)
    if not vc or vc.id not in active_sessions:
        await interaction.followup.send("No active session!", ephemeral=True)
        return

    sess = active_sessions[vc.id]
    if sess.mode != "focus":
        await interaction.followup.send("Only for focus sessions!",
                                        ephemeral=True)
        return

    if interaction.user.id not in sess.participants:
        await interaction.followup.send("Join the VC first!", ephemeral=True)
        return

    users_db = load_json(USERS_PATH)
    u = get_or_create_user(users_db, interaction.guild_id, interaction.user.id)
    add_focus_score(u, SCORE_GOAL_COMPLETE)
    save_json_atomic(USERS_PATH, users_db)

    member = interaction.guild.get_member(interaction.user.id)
    if member:
        await apply_user_roles(interaction.guild, member, u)

    await interaction.followup.send(
        f"✅ Goal complete! (+{SCORE_GOAL_COMPLETE} Focus Score)",
        ephemeral=True)


@bot.tree.command(name="checkin", description="Reply to accountability ping")
@app_commands.describe(update="What you're working on")
async def checkin_cmd(interaction: discord.Interaction, update: str):
    await interaction.response.defer(ephemeral=True)

    users_db = load_json(USERS_PATH)
    u = get_or_create_user(users_db, interaction.guild_id, interaction.user.id)

    u["last_checkin_ts"] = now_ts()
    u["pending_checkin_until"] = 0
    add_focus_score(u, SCORE_CHECKIN_OK)

    save_json_atomic(USERS_PATH, users_db)

    member = interaction.guild.get_member(interaction.user.id)
    if member:
        await apply_user_roles(interaction.guild, member, u)

    sessions_db = load_json(SESSIONS_PATH)
    log_id = f"checkin:{interaction.guild_id}:{interaction.user.id}:{now_ts()}"
    sessions_db[log_id] = {
        "type": "checkin",
        "guild_id": interaction.guild_id,
        "user_id": interaction.user.id,
        "ts": now_ts(),
        "text": update[:280]
    }
    save_json_atomic(SESSIONS_PATH, sessions_db)

    await interaction.followup.send(
        f"✅ Check-in recorded! (+{SCORE_CHECKIN_OK} Focus Score)",
        ephemeral=True)


@bot.tree.command(name="ghost", description="Toggle ghost mode (no pings)")
@app_commands.describe(on="True=on, False=off")
async def ghost_cmd(interaction: discord.Interaction, on: bool):
    await interaction.response.defer(ephemeral=True)
    users_db = load_json(USERS_PATH)
    u = get_or_create_user(users_db, interaction.guild_id, interaction.user.id)
    u["ghost_mode"] = bool(on)
    save_json_atomic(USERS_PATH, users_db)
    await interaction.followup.send(
        "👻 Ghost Mode ON" if on else "✅ Ghost Mode OFF", ephemeral=True)


@bot.tree.command(name="stats", description="Show your stats")
async def stats_cmd(interaction: discord.Interaction):
    await interaction.response.defer(ephemeral=True)
    users_db = load_json(USERS_PATH)
    u = get_or_create_user(users_db, interaction.guild_id, interaction.user.id)

    desc = (
        f"**Focus Score:** {u.get('focus_score', 0)}\n"
        f"**Total Minutes:** {u.get('total_minutes', 0)}\n"
        f"**Sessions Completed:** {u.get('sessions_completed', 0)}\n"
        f"**Streak:** {u.get('streak', 0)} days\n"
        f"**Completed Today:** {'YES ✅' if u.get('last_study_day') == day_key() else 'NO'}\n"
        f"**Ghost Mode:** {'ON 👻' if u.get('ghost_mode', False) else 'OFF'}")
    await interaction.followup.send(embed=make_embed("📊 Your Stats", desc),
                                    ephemeral=True)


@bot.tree.command(name="leaderboard", description="Show top scorers")
@app_commands.describe(limit="How many users to show (max 15)")
async def leaderboard_cmd(interaction: discord.Interaction,
                          limit: Optional[int] = 10):
    await interaction.response.defer(ephemeral=False)

    limit = max(3, min(int(limit or 10), 15))
    users_db = load_json(USERS_PATH)

    rows = [
        u for u in users_db.values()
        if int(u.get("guild_id", 0)) == interaction.guild_id
    ]
    rows.sort(key=lambda x: int(x.get("focus_score", 0)), reverse=True)
    rows = rows[:limit]

    if not rows:
        await interaction.followup.send("No data yet. Start a focus session!")
        return

    lines = []
    for i, u in enumerate(rows, start=1):
        uid = int(u.get("user_id", 0))
        member = interaction.guild.get_member(uid)
        name = member.display_name if member else f"User {uid}"
        lines.append(
            f"**{i}. {name}** — {u.get('focus_score', 0)} FS | {u.get('streak', 0)}🔥 | {u.get('total_minutes', 0)} min"
        )

    await interaction.followup.send(
        embed=make_embed("🏆 Leaderboard", "\n".join(lines)))


# =========================
# Run
# =========================

if __name__ == "__main__":
    if not TOKEN:
        raise RuntimeError("Missing DISCORD_TOKEN in .env")
    bot.run(TOKEN)
