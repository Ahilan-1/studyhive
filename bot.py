import os
import json
import time
import asyncio
from dataclasses import dataclass, field
from typing import Dict, Optional, Set, List, Tuple

import discord
from discord import app_commands
from discord.ext import commands
from dotenv import load_dotenv

# =========================
# Files / JSON DB
# =========================
ALLOW_ROLE_CREATION = False

DATA_DIR = "data"
USERS_PATH = os.path.join(DATA_DIR, "users.json")
SESSIONS_PATH = os.path.join(DATA_DIR, "sessions.json")
CONTRACTS_PATH = os.path.join(DATA_DIR, "contracts.json")
CONFIG_PATH = os.path.join(DATA_DIR, "config.json")

DEFAULT_CONFIG = {
    "checkin_interval_minutes": 120,
    "checkin_grace_minutes": 10,
    "announce_every_minutes": 10,
    "default_focus_minutes": 50,
    "default_break_minutes": 10,

    # Focus tier thresholds (Focus Score)
    "tier_bronze": 100,
    "tier_silver": 300,
    "tier_gold": 700,
    "tier_elite": 1500,

    # Weekly window
    "weekly_days": 7,

    # Role names (exact)
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

def ensure_files():
    os.makedirs(DATA_DIR, exist_ok=True)
    for p in [USERS_PATH, SESSIONS_PATH, CONTRACTS_PATH]:
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
    # shallow merge defaults so missing keys don't crash
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
# Scoring
# =========================

SCORE_FINISH_SESSION = 10
SCORE_CHECKIN_OK = 5
SCORE_CHECKIN_MISSED = -15
SCORE_LEAVE_MID = -5
SCORE_CONTRACT_SUCCESS = 50
SCORE_CONTRACT_FAIL = -20
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

    # compare days by epoch midnight-ish
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
# Active sessions in memory
# =========================

@dataclass
class ActiveSession:
    guild_id: int
    vc_id: int
    text_channel_id: int
    mode: str  # "focus" or "break"
    started_at: int
    duration_minutes: int
    ends_at: int
    participants: Set[int] = field(default_factory=set)
    goals: Dict[int, str] = field(default_factory=dict)
    last_announce_at: int = 0
    stopped: bool = False

active_sessions: Dict[int, ActiveSession] = {}  # vc_id -> session

# =========================
# Discord bot
# =========================

load_dotenv()
TOKEN = os.getenv("DISCORD_TOKEN")

intents = discord.Intents.default()
intents.guilds = True
intents.members = True  # role assignment + member lookup

ensure_files()
CONFIG = load_config()

def make_embed(title: str, desc: str) -> discord.Embed:
    return discord.Embed(title=title, description=desc)

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

async def get_user_vc(interaction: discord.Interaction) -> Optional[discord.VoiceChannel]:
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
# Role system
# =========================

ROLE_CACHE: Dict[int, Dict[str, int]] = {}  # guild_id -> {role_key: role_id}

async def ensure_roles(guild: discord.Guild) -> Dict[str, discord.Role]:
    """Create missing roles (by name) and cache role IDs."""
    role_names = CONFIG["roles"]
    out: Dict[str, discord.Role] = {}

    # Build a name->role map
    by_name = {r.name: r for r in guild.roles}

    # Create or fetch
    for key, name in role_names.items():
        role = by_name.get(name)
        if role is None:
            try:
                if not ALLOW_ROLE_CREATION:
                    continue
                role = await guild.create_role(name=name, reason="StudyHive auto-setup")
            except discord.Forbidden:
                # Can't create roles; return what we can
                continue
        out[key] = role

    # Cache IDs
    ROLE_CACHE[guild.id] = {k: v.id for k, v in out.items()}
    return out

def role_ids(guild_id: int) -> Dict[str, int]:
    return ROLE_CACHE.get(guild_id, {})

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

async def apply_user_roles(guild: discord.Guild, member: discord.Member, u: dict):
    """Assign/remove roles for a single user based on current stats."""
    # Ensure cached role objects exist
    roles_map = await ensure_roles(guild)
    score = int(u.get("focus_score", 0))
    streak = int(u.get("streak", 0))
    today = day_key()
    last_day = u.get("last_study_day")

    # ✅ Completed Today
    completed_role = roles_map.get("completed_today")
    if completed_role:
        if last_day == today:
            await add_role(member, completed_role)
        else:
            await remove_role(member, completed_role)

    # 🔥 1 Day streak (means streak >= 1)
    streak_role = roles_map.get("streak_1")
    if streak_role:
        if streak >= 1:
            await add_role(member, streak_role)
        else:
            await remove_role(member, streak_role)

    # Focus tiers: keep exactly one tier role max
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

async def purge_studyhive_roles(guild: discord.Guild) -> tuple[list[str], list[str]]:
    """
    Deletes ONLY roles that match StudyHive-config names.
    Will NOT delete:
    - @everyone
    - managed roles (integration/bot-managed)
    - roles above the bot
    """
    actions, warnings = [], []
    desired_names = set(CONFIG.get("roles", {}).values())

    me = guild.me  # type: ignore
    bot_top_pos = max((r.position for r in me.roles), default=0) if me else 0

    for role in list(guild.roles):
        if role.name == "@everyone":
            continue
        if role.managed:
            continue
        if role.name not in desired_names:
            continue
        if role.position >= bot_top_pos:
            warnings.append(f"Can't delete {role.name} (role is above or equal to bot role). Move bot role higher.")
            continue

        try:
            await role.delete(reason="StudyHive rebuild: purge managed roles")
            actions.append(f"Deleted: {role.name}")
        except discord.Forbidden:
            warnings.append(f"Forbidden deleting: {role.name}")
        except Exception as e:
            warnings.append(f"Error deleting {role.name}: {e}")

    return actions, warnings


async def rebuild_studyhive_roles(guild: discord.Guild) -> tuple[list[str], list[str]]:
    actions, warnings = [], []
    desired = CONFIG.get("roles", {})

    # Purge existing StudyHive roles first
    a1, w1 = await purge_studyhive_roles(guild)
    actions += a1
    warnings += w1

    # Recreate roles clean
    for key, name in desired.items():
        # skip if role already exists
        if discord.utils.get(guild.roles, name=name):
            actions.append(f"Exists: {name}")
            continue
        try:
            await guild.create_role(name=name, reason="StudyHive rebuild: create role")
            actions.append(f"Created: {name}")
        except discord.Forbidden:
            warnings.append(f"Forbidden creating: {name}")
        except Exception as e:
            warnings.append(f"Error creating {name}: {e}")

    return actions, warnings



async def apply_weekly_roles(guild: discord.Guild):
    """
    Weekly roles:
    - 💎 Topachiever: highest Focus Score overall
    - 🏆 Weekly Top 10: top 10 by minutes studied in last N days
    """
    roles_map = await ensure_roles(guild)
    top_ach = roles_map.get("top_achiever")
    weekly_top10 = roles_map.get("weekly_top10")

    users_db = load_json(USERS_PATH)
    sessions_db = load_json(SESSIONS_PATH)

    # Collect users in guild
    users = []
    for u in users_db.values():
        if int(u.get("guild_id", 0)) == guild.id:
            users.append(u)

    if not users:
        return

    # Top achiever = max focus_score
    users_sorted = sorted(users, key=lambda x: int(x.get("focus_score", 0)), reverse=True)
    top_user_id = int(users_sorted[0]["user_id"])

    # Weekly Top 10 by minutes in last N days (derived from sessions)
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

    weekly_sorted = sorted(minutes_by_user.items(), key=lambda kv: kv[1], reverse=True)
    weekly_top_ids = [uid for uid, _mins in weekly_sorted[:10]]

    # Apply roles
    for member in guild.members:
        if member.bot:
            continue

        # 💎 Topachiever
        if top_ach:
            if member.id == top_user_id:
                await add_role(member, top_ach)
            else:
                await remove_role(member, top_ach)

        # 🏆 Weekly Top 10
        if weekly_top10:
            if member.id in weekly_top_ids and weekly_top_ids:
                await add_role(member, weekly_top10)
            else:
                await remove_role(member, weekly_top10)

# =========================
# Session engine
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

async def run_session_loop(guild: discord.Guild, vc: discord.VoiceChannel, text_ch: discord.TextChannel, sess: ActiveSession):
    announce_every = int(CONFIG.get("announce_every_minutes", 10))

    # record start
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

        # Track leavers (penalty)
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

        if sess.last_announce_at == 0 or (now - sess.last_announce_at) >= announce_every * 60:
            remaining = sess.ends_at - now
            await text_ch.send(f"⏳ **{sess.mode.upper()}** remaining: **{human_mins(remaining)}** | In VC: **{len(sess.participants)}**")
            sess.last_announce_at = now

        await asyncio.sleep(15)

    if sess.stopped:
        return

    await text_ch.send(f"⏰ **{sess.mode.upper()} ended!**")

    # session ended naturally: scoring + roles if focus
    if sess.mode == "focus":
        users_db = load_json(USERS_PATH)
        finished_day = day_key(sess.ends_at)

        # Update user stats
        for uid in list(sess.participants):
            u = get_or_create_user(users_db, guild.id, uid)
            add_minutes(u, sess.duration_minutes)
            u["sessions_completed"] = int(u.get("sessions_completed", 0)) + 1
            add_focus_score(u, SCORE_FINISH_SESSION)
            update_streak(u, finished_day)

        save_json_atomic(USERS_PATH, users_db)

        # Update session record with final participants/goals snapshot
        sessions_db = load_json(SESSIONS_PATH)
        rec = sessions_db.get(sid, {})
        rec["participants"] = list(sess.participants)
        rec["goals"] = sess.goals
        rec["ended_at"] = now_ts()
        sessions_db[sid] = rec
        save_json_atomic(SESSIONS_PATH, sessions_db)

        # Apply per-user roles
        for uid in sess.participants:
            member = guild.get_member(uid)
            if member:
                u = get_or_create_user(users_db, guild.id, uid)
                await apply_user_roles(guild, member, u)

        # Apply weekly roles (lightweight; runs periodic too)
        await apply_weekly_roles(guild)

        await text_ch.send("☕ Tip: start a break with `/break 10`")
    else:
        await text_ch.send("📚 Tip: start focus with `/focus 50`")

    # cleanup
    if vc.id in active_sessions:
        del active_sessions[vc.id]

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

                # missed checkin => penalty
                if pending_until and now > pending_until:
                    add_focus_score(u, SCORE_CHECKIN_MISSED)
                    u["pending_checkin_until"] = 0
                    changed = True
                    continue

                # time to ping?
                if pending_until == 0 and last_checkin and (now - last_checkin) >= checkin_interval * 60:
                    # only ping if user is in an active focus session
                    for sess in active_sessions.values():
                        if sess.mode != "focus":
                            continue
                        if sess.guild_id != guild_id:
                            continue
                        if user_id not in sess.participants:
                            continue

                        text_ch = bot_ref.get_channel(sess.text_channel_id)
                        if isinstance(text_ch, discord.TextChannel):
                            member = text_ch.guild.get_member(user_id) if text_ch.guild else None
                            mention = member.mention if member else f"<@{user_id}>"
                            u["pending_checkin_until"] = now + grace * 60
                            u["last_checkin_ts"] = now  # prevent rapid re-pings
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

# =========================
# Weekly role updater loop
# =========================

async def weekly_roles_loop(bot_ref: commands.Bot):
    await bot_ref.wait_until_ready()
    while not bot_ref.is_closed():
        try:
            for guild in bot_ref.guilds:
                await apply_weekly_roles(guild)
        except Exception as e:
            print("Weekly roles loop error:", e)
        await asyncio.sleep(3600)  # hourly

async def delete_duplicate_roles(guild: discord.Guild):
    """
    Keeps ONE role for each StudyHive role name.
    Deletes extra copies safely.
    """
    desired_names = set(CONFIG["roles"].values())

    actions = []
    warnings = []

    # Map name -> list of roles
    name_map = {}
    for role in guild.roles:
        name_map.setdefault(role.name, []).append(role)

    me = guild.me
    bot_top_position = max((r.position for r in me.roles), default=0)

    for name in desired_names:
        roles = name_map.get(name, [])

        if len(roles) <= 1:
            continue  # no duplicates

        # Keep highest role (highest position)
        roles_sorted = sorted(roles, key=lambda r: r.position, reverse=True)
        keep = roles_sorted[0]
        duplicates = roles_sorted[1:]

        for r in duplicates:
            if r.managed:
                continue
            if r.position >= bot_top_position:
                warnings.append(f"Move bot role higher to delete: {r.name}")
                continue
            try:
                await r.delete(reason="StudyHive duplicate cleanup")
                actions.append(f"Deleted duplicate role: {r.name}")
            except discord.Forbidden:
                warnings.append(f"No permission to delete: {r.name}")

    return actions, warnings


# =========================
# Bot class with safe startup
# =========================



class StudyHiveBot(commands.Bot):
    async def setup_hook(self):
        # start background tasks safely (discord.py 2.4+)
        self.loop.create_task(accountability_loop(self))
        self.loop.create_task(weekly_roles_loop(self))
        self.loop.create_task(motivation_loop(self))

        # sync slash commands
        try:
            await self.tree.sync()
        except Exception as e:
            print("Command sync error:", e)

bot = StudyHiveBot(command_prefix="!", intents=intents)

@bot.event
async def on_ready():
    print(f"StudyHive online as {bot.user}")
    # create roles on startup for each guild
    for guild in bot.guilds:
        try:
            await ensure_roles(guild)
        except Exception as e:
            print(f"Role ensure error in {guild.name}:", e)

# =========================
# Slash Commands
# =========================
@bot.tree.command(name="admin_delete_duplicates", description="Delete duplicate StudyHive roles.")
async def admin_delete_duplicates(interaction: discord.Interaction):
    await interaction.response.defer(ephemeral=True)

    if not interaction.user.guild_permissions.manage_roles:
        await interaction.followup.send("You need **Manage Roles** permission.", ephemeral=True)
        return

    actions, warnings = await delete_duplicate_roles(interaction.guild)

    msg = "🧹 Duplicate role cleanup finished.\n"

    if actions:
        msg += "\n**Deleted:**\n" + "\n".join(actions)
    else:
        msg += "\nNo duplicates found."

    if warnings:
        msg += "\n\n**Warnings:**\n" + "\n".join(warnings)

    await interaction.followup.send(msg, ephemeral=True)


@bot.tree.command(name="admin_rebuild_roles", description="DELETE StudyHive roles and recreate from config (safe).")
async def admin_rebuild_roles_cmd(interaction: discord.Interaction):
    await interaction.response.defer(ephemeral=True)

    if not interaction.guild:
        await interaction.followup.send("Run this inside a server.", ephemeral=True)
        return

    perms = interaction.user.guild_permissions
    if not (perms.administrator or perms.manage_roles):
        await interaction.followup.send("You need **Manage Roles** or **Administrator**.", ephemeral=True)
        return

    actions, warnings = await rebuild_studyhive_roles(interaction.guild)

    msg = "✅ StudyHive role rebuild complete.\n"
    if actions:
        msg += "\n**Actions:**\n" + "\n".join(f"- {x}" for x in actions[:25])
        if len(actions) > 25:
            msg += f"\n- ...and {len(actions)-25} more"
    if warnings:
        msg += "\n\n**Warnings:**\n" + "\n".join(f"- {x}" for x in warnings[:20])
        if len(warnings) > 20:
            msg += f"\n- ...and {len(warnings)-20} more"

    msg += "\n\nManual step: turn on **Display role members separately** for each role (Discord doesn’t allow bots to toggle it)."
    await interaction.followup.send(msg, ephemeral=True)

MOTIVATION_LINES = [
    "Small steps. Clean wins.",
    "Your future self is watching. Make them proud.",
    "One session is a vote for the person you want to become.",
    "Start ugly. Finish strong.",
    "Discipline beats mood. Every time.",
    "Do the next right thing. That's the whole game.",
    "Focus for 50. Rest for 10. Repeat.",
    "You don’t need more time. You need fewer distractions.",
    "Show up today. Momentum is real."
]

def get_motivation_channel(guild: discord.Guild) -> Optional[discord.TextChannel]:
    name = str(CONFIG.get("motivation_channel_name", "study-feed")).lower()
    for ch in guild.text_channels:
        if ch.name.lower() == name:
            return ch
    return None

async def motivation_loop(bot_ref: commands.Bot):
    await bot_ref.wait_until_ready()
    interval = int(CONFIG.get("motivation_interval_minutes", 60))

    i = 0
    while not bot_ref.is_closed():
        try:
            for guild in bot_ref.guilds:
                ch = get_motivation_channel(guild)
                if ch:
                    line = MOTIVATION_LINES[i % len(MOTIVATION_LINES)]
                    i += 1
                    await ch.send(f"🧠 **StudyHive reminder:** {line}")
        except Exception as e:
            print("Motivation loop error:", e)

        await asyncio.sleep(max(10, interval) * 60)


@bot.tree.command(name="focus", description="Start a focus session for your current voice channel.")
@app_commands.describe(minutes="Duration in minutes (default is 50).")
async def focus_cmd(interaction: discord.Interaction, minutes: Optional[int] = None):
    await interaction.response.defer(ephemeral=True)

    vc = await get_user_vc(interaction)
    if not vc:
        await interaction.followup.send("Join a **voice channel** first, then run `/focus`.", ephemeral=True)
        return

    if vc.id in active_sessions:
        await interaction.followup.send("A session is already running in this VC. Use `/stop` first.", ephemeral=True)
        return

    mins = int(minutes or CONFIG.get("default_focus_minutes", 50))
    mins = max(5, min(mins, 180))

    members = list_vc_members(vc)
    if not members:
        await interaction.followup.send("No human members found in the VC.", ephemeral=True)
        return

    # choose text channel where command is executed
    if not isinstance(interaction.channel, discord.TextChannel):
        await interaction.followup.send("Run this command in a **text channel**.", ephemeral=True)
        return
    text_ch = interaction.channel

    sess = ActiveSession(
        guild_id=interaction.guild_id,
        vc_id=vc.id,
        text_channel_id=text_ch.id,
        mode="focus",
        started_at=now_ts(),
        duration_minutes=mins,
        ends_at=now_ts() + mins * 60,
        participants={m.id for m in members}
    )

    # init checkin timestamp for participants
    users_db = load_json(USERS_PATH)
    for m in members:
        u = get_or_create_user(users_db, interaction.guild_id, m.id)
        if int(u.get("last_checkin_ts", 0)) == 0:
            u["last_checkin_ts"] = now_ts()
    save_json_atomic(USERS_PATH, users_db)

    active_sessions[vc.id] = sess
    bot.loop.create_task(run_session_loop(interaction.guild, vc, text_ch, sess))

    await interaction.followup.send(f"Started **FOCUS {mins} min** for VC **{vc.name}**. Updates in {text_ch.mention}.", ephemeral=True)

@bot.tree.command(name="break", description="Start a break session for your current voice channel.")
@app_commands.describe(minutes="Duration in minutes (default is 10).")
async def break_cmd(interaction: discord.Interaction, minutes: Optional[int] = None):
    await interaction.response.defer(ephemeral=True)

    vc = await get_user_vc(interaction)
    if not vc:
        await interaction.followup.send("Join a **voice channel** first, then run `/break`.", ephemeral=True)
        return

    if vc.id in active_sessions:
        await interaction.followup.send("A session is already running in this VC. Use `/stop` first.", ephemeral=True)
        return

    mins = int(minutes or CONFIG.get("default_break_minutes", 10))
    mins = max(3, min(mins, 60))

    if not isinstance(interaction.channel, discord.TextChannel):
        await interaction.followup.send("Run this command in a **text channel**.", ephemeral=True)
        return
    text_ch = interaction.channel

    members = list_vc_members(vc)

    sess = ActiveSession(
        guild_id=interaction.guild_id,
        vc_id=vc.id,
        text_channel_id=text_ch.id,
        mode="break",
        started_at=now_ts(),
        duration_minutes=mins,
        ends_at=now_ts() + mins * 60,
        participants={m.id for m in members}
    )

    active_sessions[vc.id] = sess
    bot.loop.create_task(run_session_loop(interaction.guild, vc, text_ch, sess))

    await interaction.followup.send(f"Started **BREAK {mins} min** for VC **{vc.name}**.", ephemeral=True)

@bot.tree.command(name="stop", description="Stop the running session in your voice channel.")
async def stop_cmd(interaction: discord.Interaction):
    await interaction.response.defer(ephemeral=True)

    vc = await get_user_vc(interaction)
    if not vc:
        await interaction.followup.send("Join the VC that has the session, then run `/stop`.", ephemeral=True)
        return

    if vc.id not in active_sessions:
        await interaction.followup.send("No active session in this VC.", ephemeral=True)
        return

    await stop_session(vc.id, reason=f"Stopped by {interaction.user.id}")
    await interaction.followup.send("Stopped the session.", ephemeral=True)

@bot.tree.command(name="goal", description="Set your goal for the current focus session.")
@app_commands.describe(text="What you will work on in this block.")
async def goal_cmd(interaction: discord.Interaction, text: str):
    await interaction.response.defer(ephemeral=True)

    vc = await get_user_vc(interaction)
    if not vc or vc.id not in active_sessions:
        await interaction.followup.send("You must be in a VC with an active session to set a goal.", ephemeral=True)
        return

    sess = active_sessions[vc.id]
    if sess.mode != "focus":
        await interaction.followup.send("Goals only work during **focus** sessions.", ephemeral=True)
        return

    if interaction.user.id not in sess.participants:
        await interaction.followup.send("Join the VC to be counted as a participant.", ephemeral=True)
        return

    sess.goals[interaction.user.id] = text[:200]
    await interaction.followup.send("Goal saved ✅", ephemeral=True)

@bot.tree.command(name="goal_done", description="Mark your goal as completed for bonus points.")
async def goal_done_cmd(interaction: discord.Interaction):
    await interaction.response.defer(ephemeral=True)

    vc = await get_user_vc(interaction)
    if not vc or vc.id not in active_sessions:
        await interaction.followup.send("No active session found in your VC.", ephemeral=True)
        return

    sess = active_sessions[vc.id]
    if sess.mode != "focus":
        await interaction.followup.send("Only for focus sessions.", ephemeral=True)
        return

    if interaction.user.id not in sess.participants:
        await interaction.followup.send("Join the VC to be a participant.", ephemeral=True)
        return

    users_db = load_json(USERS_PATH)
    u = get_or_create_user(users_db, interaction.guild_id, interaction.user.id)
    add_focus_score(u, SCORE_GOAL_COMPLETE)
    save_json_atomic(USERS_PATH, users_db)

    member = interaction.guild.get_member(interaction.user.id)
    if member:
        await apply_user_roles(interaction.guild, member, u)

    await interaction.followup.send(f"Marked as done ✅ (+{SCORE_GOAL_COMPLETE} Focus Score)", ephemeral=True)

@bot.tree.command(name="checkin", description="Reply to the accountability ping.")
@app_commands.describe(update="What you're working on right now.")
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

    # log check-in
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

    await interaction.followup.send(f"Check-in recorded ✅ (+{SCORE_CHECKIN_OK} Focus Score)", ephemeral=True)

@bot.tree.command(name="ghost", description="Toggle Ghost Mode (no check-in pings).")
@app_commands.describe(on="True=on, False=off.")
async def ghost_cmd(interaction: discord.Interaction, on: bool):
    await interaction.response.defer(ephemeral=True)
    users_db = load_json(USERS_PATH)
    u = get_or_create_user(users_db, interaction.guild_id, interaction.user.id)
    u["ghost_mode"] = bool(on)
    save_json_atomic(USERS_PATH, users_db)
    await interaction.followup.send("Ghost Mode enabled 👻" if on else "Ghost Mode disabled ✅", ephemeral=True)

@bot.tree.command(name="stats", description="Show your StudyHive stats.")
async def stats_cmd(interaction: discord.Interaction):
    await interaction.response.defer(ephemeral=True)
    users_db = load_json(USERS_PATH)
    u = get_or_create_user(users_db, interaction.guild_id, interaction.user.id)

    desc = (
        f"**Focus Score:** {u.get('focus_score', 0)}\n"
        f"**Total Minutes:** {u.get('total_minutes', 0)}\n"
        f"**Sessions Completed:** {u.get('sessions_completed', 0)}\n"
        f"**Streak:** {u.get('streak', 0)} days\n"
        f"**Completed Today:** {'YES' if u.get('last_study_day') == day_key() else 'NO'}\n"
        f"**Ghost Mode:** {'ON' if u.get('ghost_mode', False) else 'OFF'}"
    )
    await interaction.followup.send(embed=make_embed("📊 Your StudyHive Stats", desc), ephemeral=True)

@bot.tree.command(name="leaderboard", description="Show top Focus Scores in this server.")
@app_commands.describe(limit="How many users to show (max 15).")
async def leaderboard_cmd(interaction: discord.Interaction, limit: Optional[int] = 10):
    await interaction.response.defer(ephemeral=False)

    limit = max(3, min(int(limit or 10), 15))
    users_db = load_json(USERS_PATH)

    rows = [u for u in users_db.values() if int(u.get("guild_id", 0)) == interaction.guild_id]
    rows.sort(key=lambda x: int(x.get("focus_score", 0)), reverse=True)
    rows = rows[:limit]

    if not rows:
        await interaction.followup.send("No data yet. Start a `/focus` session first!")
        return

    lines = []
    for i, u in enumerate(rows, start=1):
        uid = int(u.get("user_id", 0))
        member = interaction.guild.get_member(uid)
        name = member.display_name if member else f"User {uid}"
        lines.append(f"**{i}. {name}** — {u.get('focus_score', 0)} FS | {u.get('streak', 0)}🔥 | {u.get('total_minutes', 0)} min")

    await interaction.followup.send(embed=make_embed("🏆 StudyHive Focus Leaderboard", "\n".join(lines)))

@bot.tree.command(name="admin_setup_roles", description="Force-create all StudyHive roles (admin).")
async def admin_setup_roles(interaction: discord.Interaction):
    await interaction.response.defer(ephemeral=True)
    if not interaction.guild:
        await interaction.followup.send("Run this inside a server.", ephemeral=True)
        return
    roles_map = await ensure_roles(interaction.guild)
    missing = [k for k in CONFIG["roles"].keys() if k not in roles_map]
    if missing:
        await interaction.followup.send(
            "Some roles could not be created. Check bot permissions / role hierarchy.\nMissing: " + ", ".join(missing),
            ephemeral=True
        )
    else:
        await interaction.followup.send("All roles are ready ✅", ephemeral=True)


# =========================
# RUN
# =========================

if __name__ == "__main__":
    if not TOKEN:
        raise RuntimeError("Missing DISCORD_TOKEN in .env")
    bot.run(TOKEN)
