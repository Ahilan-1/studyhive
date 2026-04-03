import discord
from discord.ext import commands, tasks
from discord import app_commands
import json
import os
import asyncio
import shutil
from datetime import datetime, timezone, timedelta
import time

# ─────────────────────────────────────────────
#  CONFIG
# ─────────────────────────────────────────────
TOKEN = os.getenv("MAIN_BOT_TOKEN", "nil")
GUILD_ID = 1469292867955589153

PUBLIC_VC_CATEGORY_ID  = 1469292869113352454
PRIVATE_VC_CATEGORY_ID = 1472520456979480637

CREATE_ROOM_CHANNEL_ID = 1476210817442643999
STATS_CHANNEL_ID       = 1469299204177530943
LOG_CHANNEL_ID         = 1475523026497048586

# ── Set this to the ID of your "📚 X studying" voice channel name trick ──
# Create a VC in Discord, lock it so nobody can join, copy its ID here
STUDYING_COUNT_CHANNEL_ID = 1476295380793561339   
ADMIN_ROLE_ID = 1469300951335567401
MOD_ROLE_ID   = 1469300951335567401

DATA_FILE   = "data.json"
BACKUP_DIR  = "backups"
MAX_BACKUPS = 48

# ─────────────────────────────────────────────
#  DATA & BACKUP HELPERS
# ─────────────────────────────────────────────
def ensure_dirs():
    os.makedirs(BACKUP_DIR, exist_ok=True)

def load_data() -> dict:
    if not os.path.exists(DATA_FILE):
        return {}
    with open(DATA_FILE, "r") as f:
        return json.load(f)

def save_data(data: dict):
    tmp = DATA_FILE + ".tmp"
    with open(tmp, "w") as f:
        json.dump(data, f, indent=2)
    os.replace(tmp, DATA_FILE)

def do_backup(label: str = ""):
    if not os.path.exists(DATA_FILE):
        return
    ensure_dirs()
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    name = f"data_{timestamp}{'_' + label if label else ''}.json"
    shutil.copy2(DATA_FILE, os.path.join(BACKUP_DIR, name))
    backups = sorted([f for f in os.listdir(BACKUP_DIR) if f.endswith(".json")], reverse=True)
    for old in backups[MAX_BACKUPS:]:
        try: os.remove(os.path.join(BACKUP_DIR, old))
        except: pass

def get_user(data: dict, uid: int) -> dict:
    key = str(uid)
    if key not in data:
        data[key] = {
            "username": "",
            "hours": {"alltime": 0.0, "monthly": {}, "daily": {}},
            "sessions": [],
            "streak": {"current": 0, "longest": 0, "last_study_date": ""},
            "warnings": [],
            "awards": [],
            "goals": {"daily_hours": 0.0, "updated_at": None},
            "onboarding": {
                "completed": False,
                "exam": "",
                "timezone": "UTC",
                "intro_goal": "",
                "started_at": time.time(),
                "completed_at": None
            },
            "vc_join_time": None,
            "pomodoro": None
        }
    u = data[key]
    u.setdefault("awards", [])
    u.setdefault("goals", {"daily_hours": 0.0, "updated_at": None})
    u.setdefault("onboarding", {
        "completed": False,
        "exam": "",
        "timezone": "UTC",
        "intro_goal": "",
        "started_at": time.time(),
        "completed_at": None
    })
    return u

def today_key() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%d")

def month_key() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m")

def add_hours(data: dict, uid: int, hours: float):
    u = get_user(data, uid)
    u["hours"]["alltime"] = round(u["hours"]["alltime"] + hours, 4)
    mk, dk = month_key(), today_key()
    u["hours"]["monthly"][mk] = round(u["hours"]["monthly"].get(mk, 0) + hours, 4)
    u["hours"]["daily"][dk]   = round(u["hours"]["daily"].get(dk, 0) + hours, 4)
    streak = u["streak"]
    if streak["last_study_date"] != dk:
        yesterday = (datetime.now(timezone.utc) - timedelta(days=1)).strftime("%Y-%m-%d")
        streak["current"] = streak["current"] + 1 if streak["last_study_date"] == yesterday else 1
        streak["last_study_date"] = dk
        streak["longest"] = max(streak["longest"], streak["current"])

def rank_on(data: dict, uid: int, field: str) -> int:
    scores = []
    for k, v in data.items():
        if field == "alltime":
            scores.append((k, v["hours"]["alltime"]))
        elif field == "monthly":
            scores.append((k, v["hours"]["monthly"].get(month_key(), 0)))
        elif field == "weekly":
            total = sum(v["hours"]["daily"].get(
                (datetime.now(timezone.utc) - timedelta(days=i)).strftime("%Y-%m-%d"), 0
            ) for i in range(7))
            scores.append((k, total))
        elif field == "daily":
            scores.append((k, v["hours"]["daily"].get(today_key(), 0)))
    scores.sort(key=lambda x: x[1], reverse=True)
    for i, (k, _) in enumerate(scores):
        if k == str(uid):
            return i + 1
    return len(scores) + 1

def weekly_hours(data: dict, uid: int) -> float:
    u = get_user(data, uid)
    return round(sum(u["hours"]["daily"].get(
        (datetime.now(timezone.utc) - timedelta(days=i)).strftime("%Y-%m-%d"), 0
    ) for i in range(7)), 2)

def weekly_hours_window(data: dict, uid: int, days_back_start: int = 0, days: int = 7) -> float:
    u = get_user(data, uid)
    total = 0.0
    for i in range(days_back_start, days_back_start + days):
        key = (datetime.now(timezone.utc) - timedelta(days=i)).strftime("%Y-%m-%d")
        total += u["hours"]["daily"].get(key, 0)
    return round(total, 2)

def get_daily_goal(data: dict, uid: int) -> float:
    return float(get_user(data, uid)["goals"].get("daily_hours", 0.0) or 0.0)

def goal_progress(data: dict, uid: int) -> tuple[float, float, float]:
    u = get_user(data, uid)
    current = float(u["hours"]["daily"].get(today_key(), 0))
    goal = get_daily_goal(data, uid)
    pct = 0.0 if goal <= 0 else min(100.0, (current / goal) * 100)
    return current, goal, pct

def fmt_hours_short(hours: float) -> str:
    return f"{hours:.1f}h"

def fmt_datetime_utc(ts: float | None) -> str:
    if not ts:
        return "Unknown"
    return datetime.fromtimestamp(ts, tz=timezone.utc).strftime("%Y-%m-%d %H:%M UTC")

def onboarding_completion_count(u: dict) -> tuple[int, int]:
    onboarding = u.get("onboarding", {})
    checks = [
        bool(onboarding.get("exam")),
        bool(onboarding.get("timezone")),
        bool(onboarding.get("intro_goal")),
        bool(float(u.get("goals", {}).get("daily_hours", 0.0) or 0.0) > 0),
    ]
    return sum(checks), len(checks)

def build_onboarding_embed(member: discord.Member, u: dict) -> discord.Embed:
    onboarding = u["onboarding"]
    goal = float(u["goals"].get("daily_hours", 0.0) or 0.0)
    done, total = onboarding_completion_count(u)
    embed = discord.Embed(
        title="🎓 StudyHive Onboarding",
        description=(
            "Set up your student profile so the server feels tailored from the start.\n\n"
            "Use the buttons below to define your exam, daily goal, timezone, and study intention."
        ),
        color=0x5865F2
    )
    embed.set_author(name=member.display_name, icon_url=member.display_avatar.url)
    embed.add_field(name="Exam / Track", value=onboarding.get("exam") or "Not set", inline=True)
    embed.add_field(name="Timezone", value=onboarding.get("timezone") or "UTC", inline=True)
    embed.add_field(name="Daily Goal", value=fmt_hours_short(goal) if goal > 0 else "Not set", inline=True)
    embed.add_field(name="Primary Goal", value=onboarding.get("intro_goal") or "Not set", inline=False)
    embed.add_field(name="Progress", value=f"{done}/{total} complete", inline=True)
    embed.add_field(name="Status", value="✅ Completed" if onboarding.get("completed") else "🛠️ In progress", inline=True)
    embed.set_footer(text="Elite students set a standard early.")
    return embed


class ExamModal(discord.ui.Modal, title="Set Your Exam / Track"):
    exam = discord.ui.TextInput(
        label="Exam, course, or track",
        placeholder="JEE / NEET / UPSC / CA / Semester Finals / Coding Interview",
        max_length=80
    )

    async def on_submit(self, interaction: discord.Interaction):
        data = load_data()
        u = get_user(data, interaction.user.id)
        u["username"] = interaction.user.name
        u["onboarding"]["exam"] = str(self.exam).strip()
        save_data(data)
        await interaction.response.edit_message(embed=build_onboarding_embed(interaction.user, u), view=OnboardingView(interaction.user.id))


class GoalModal(discord.ui.Modal, title="Set Your Daily Goal"):
    hours = discord.ui.TextInput(
        label="Daily study goal in hours",
        placeholder="2.5",
        max_length=5
    )
    focus = discord.ui.TextInput(
        label="Your main study focus right now",
        placeholder="Finish organic chemistry revision this week",
        max_length=120
    )

    async def on_submit(self, interaction: discord.Interaction):
        try:
            hours = float(str(self.hours).strip())
        except ValueError:
            await interaction.response.send_message("❌ Enter a valid number like `2` or `2.5`.", ephemeral=True)
            return
        if hours <= 0 or hours > 24:
            await interaction.response.send_message("❌ Goal must be between 0 and 24 hours.", ephemeral=True)
            return

        data = load_data()
        u = get_user(data, interaction.user.id)
        u["username"] = interaction.user.name
        u["goals"]["daily_hours"] = round(hours, 2)
        u["goals"]["updated_at"] = time.time()
        u["onboarding"]["intro_goal"] = str(self.focus).strip()
        save_data(data)
        await interaction.response.edit_message(embed=build_onboarding_embed(interaction.user, u), view=OnboardingView(interaction.user.id))


class TimezoneModal(discord.ui.Modal, title="Set Your Timezone"):
    timezone_name = discord.ui.TextInput(
        label="Timezone",
        placeholder="Asia/Kolkata / UTC / Europe/London / America/New_York",
        max_length=60
    )

    async def on_submit(self, interaction: discord.Interaction):
        tz = str(self.timezone_name).strip() or "UTC"
        data = load_data()
        u = get_user(data, interaction.user.id)
        u["username"] = interaction.user.name
        u["onboarding"]["timezone"] = tz
        save_data(data)
        await interaction.response.edit_message(embed=build_onboarding_embed(interaction.user, u), view=OnboardingView(interaction.user.id))


class OnboardingView(discord.ui.View):
    def __init__(self, owner_id: int):
        super().__init__(timeout=900)
        self.owner_id = owner_id

    async def interaction_check(self, interaction: discord.Interaction) -> bool:
        if interaction.user.id != self.owner_id:
            await interaction.response.send_message("❌ This onboarding panel belongs to another member.", ephemeral=True)
            return False
        return True

    @discord.ui.button(label="Set Exam", style=discord.ButtonStyle.primary)
    async def set_exam(self, interaction: discord.Interaction, _: discord.ui.Button):
        await interaction.response.send_modal(ExamModal())

    @discord.ui.button(label="Set Goal", style=discord.ButtonStyle.success)
    async def set_goal(self, interaction: discord.Interaction, _: discord.ui.Button):
        await interaction.response.send_modal(GoalModal())

    @discord.ui.button(label="Set Timezone", style=discord.ButtonStyle.secondary)
    async def set_timezone(self, interaction: discord.Interaction, _: discord.ui.Button):
        await interaction.response.send_modal(TimezoneModal())

    @discord.ui.button(label="Complete", style=discord.ButtonStyle.primary)
    async def complete(self, interaction: discord.Interaction, _: discord.ui.Button):
        data = load_data()
        u = get_user(data, interaction.user.id)
        done, total = onboarding_completion_count(u)
        if done < total:
            await interaction.response.send_message(f"❌ Finish setup first. Progress: {done}/{total}.", ephemeral=True)
            return
        u["onboarding"]["completed"] = True
        u["onboarding"]["completed_at"] = time.time()
        save_data(data)
        embed = build_onboarding_embed(interaction.user, u)
        embed.color = 0x2ECC71
        embed.description = "Your student profile is now set. You're ready to join VC, stack hours, and compete."
        await interaction.response.edit_message(embed=embed, view=None)

def is_admin_check(interaction: discord.Interaction) -> bool:
    return any(r.id == ADMIN_ROLE_ID for r in interaction.user.roles)

def build_weekly_awards(data: dict, guild: discord.Guild, previous_week: bool = False) -> list[tuple[int, float]]:
    scores = []
    days_back_start = 7 if previous_week else 0
    for uid_str in data.keys():
        uid = int(uid_str)
        hours = weekly_hours_window(data, uid, days_back_start=days_back_start, days=7)
        if hours > 0:
            scores.append((uid, hours))
    scores.sort(key=lambda item: item[1], reverse=True)
    return scores[:3]

def record_award(data: dict, uid: int, title: str, details: str):
    u = get_user(data, uid)
    u["awards"].append({
        "title": title,
        "details": details,
        "time": time.time()
    })
    u["awards"] = u["awards"][-20:]

def get_current_voice_members(guild: discord.Guild, scope: str = "all") -> list[tuple[discord.Member, discord.VoiceChannel, float]]:
    active = []
    data = load_data()
    now = time.time()
    for vc in guild.voice_channels:
        if scope == "study" and vc.category_id not in (PUBLIC_VC_CATEGORY_ID, PRIVATE_VC_CATEGORY_ID):
            continue
        for member in vc.members:
            if member.bot:
                continue
            u = get_user(data, member.id)
            join_time = u.get("vc_join_time") or now
            active.append((member, vc, max(0.0, (now - join_time) / 3600)))
    active.sort(key=lambda item: item[2], reverse=True)
    return active

def progress_bar(current_sec: int, total_sec: int, length: int = 20) -> str:
    if total_sec == 0:
        return f"`[{'░' * length}]` 0%"
    filled = int((current_sec / total_sec) * length)
    return f"`[{'█' * filled}{'░' * (length - filled)}]` {int((current_sec / total_sec) * 100)}%"

def fmt_time(seconds: int) -> str:
    m, s = divmod(max(seconds, 0), 60)
    return f"{m:02d}:{s:02d}"

def is_public_vc(channel) -> bool:
    return getattr(channel, 'category_id', None) == PUBLIC_VC_CATEGORY_ID

def is_private_vc(channel) -> bool:
    return getattr(channel, 'category_id', None) == PRIVATE_VC_CATEGORY_ID

def get_badges(alltime_h: float, streak_current: int) -> str:
    badges = ""
    if alltime_h >= 1000:   badges += "💎 "
    elif alltime_h >= 500:  badges += "🥇 "
    elif alltime_h >= 100:  badges += "🥈 "
    elif alltime_h >= 10:   badges += "🥉 "
    if streak_current >= 30:  badges += "🔥30d "
    elif streak_current >= 7: badges += "🔥7d "
    return badges.strip()

def count_studying(guild: discord.Guild) -> int:
    """Count unique humans currently in any study VC."""
    seen = set()
    for vc in guild.voice_channels:
        if vc.category_id in (PUBLIC_VC_CATEGORY_ID, PRIVATE_VC_CATEGORY_ID):
            for m in vc.members:
                if not m.bot:
                    seen.add(m.id)
    return len(seen)

# ─────────────────────────────────────────────
#  BOT SETUP
# ─────────────────────────────────────────────
intents = discord.Intents.default()
intents.members = True
intents.voice_states = True
intents.message_content = True

bot = commands.Bot(command_prefix="!", intents=intents)
tree = bot.tree

active_pomodoros: dict[int, asyncio.Task] = {}
room_owners: dict[int, int] = {}
vc_sessions: dict[int, "VCPomodoroSession"] = {}

# ─────────────────────────────────────────────
#  VC POMODORO SESSION
# ─────────────────────────────────────────────
class VCPomodoroSession:
    def __init__(self, channel_id, focus, brk, rounds, mute_on_focus):
        self.channel_id = channel_id
        self.focus = focus
        self.brk = brk
        self.rounds = rounds
        self.mute_on_focus = mute_on_focus   # only allowed for private VCs
        self.current_round = 0
        self.phase = "focus"
        self.phase_start = time.time()
        self.phase_duration = focus * 60
        self.member_join_times: dict[int, float] = {}
        self.live_message: discord.Message = None
        self.task: asyncio.Task = None

    def member_joined(self, uid: int):
        if uid not in self.member_join_times:
            self.member_join_times[uid] = time.time()

    def member_left(self, uid: int):
        self.member_join_times.pop(uid, None)

    def elapsed_in_phase(self) -> int:
        return int(time.time() - self.phase_start)

    def remaining_in_phase(self) -> int:
        return max(0, self.phase_duration - self.elapsed_in_phase())

    def hours_studied_in_focus(self, uid: int) -> float:
        if self.phase != "focus":
            return 0.0
        join_t = self.member_join_times.get(uid)
        if not join_t:
            return 0.0
        return (time.time() - join_t) / 3600

# ─────────────────────────────────────────────
#  EVENTS
# ─────────────────────────────────────────────
@bot.event
async def on_ready():
    ensure_dirs()
    print(f"✅ Logged in as {bot.user} — recovering sessions...")

    data = load_data()
    guild = bot.get_guild(GUILD_ID)
    recovered = 0
    if guild:
        for vc in guild.voice_channels:
            for member in vc.members:
                if member.bot:
                    continue
                u = get_user(data, member.id)
                u["username"] = member.name
                existing = u.get("vc_join_time")
                if existing is None or (time.time() - existing) > 43200:
                    u["vc_join_time"] = time.time()
                    recovered += 1
    save_data(data)
    print(f"♻️  Recovered {recovered} active VC session(s)")

    await tree.sync(guild=discord.Object(id=GUILD_ID))
    checkpoint_sessions.start()
    backup_data.start()
    update_studying_status.start()
    print("✅ Bot fully ready")

@bot.event
async def on_voice_state_update(member: discord.Member, before: discord.VoiceState, after: discord.VoiceState):
    data = load_data()
    uid = member.id
    u = get_user(data, uid)
    u["username"] = member.name

    # ── Regular session tracking ───────────────────────────────────
    if before.channel is None and after.channel is not None:
        u["vc_join_time"] = time.time()

    elif before.channel is not None and after.channel is None:
        if u["vc_join_time"]:
            duration_min = (time.time() - u["vc_join_time"]) / 60
            u["sessions"].append({
                "start": u["vc_join_time"],
                "end": time.time(),
                "duration_min": round(duration_min, 2)
            })
            if before.channel and before.channel.id not in vc_sessions:
                add_hours(data, uid, duration_min / 60)
            u["vc_join_time"] = None

    # ── Pomodoro: late joiners / early leavers ─────────────────────
    if after.channel and after.channel.id in vc_sessions:
        vc_sessions[after.channel.id].member_joined(uid)

    if before.channel and before.channel.id in vc_sessions:
        sess = vc_sessions[before.channel.id]
        if sess.phase == "focus":
            hours = sess.hours_studied_in_focus(uid)
            if hours > 0:
                add_hours(data, uid, hours)
        sess.member_left(uid)

    # ── Private room creation ──────────────────────────────────────
    guild = member.guild
    if after.channel and after.channel.id == CREATE_ROOM_CHANNEL_ID:
        category = guild.get_channel(PRIVATE_VC_CATEGORY_ID)
        new_ch = await guild.create_voice_channel(
            name=f"🔒 {member.display_name}'s Room",
            category=category,
            overwrites={
                guild.default_role: discord.PermissionOverwrite(connect=False),
                member: discord.PermissionOverwrite(connect=True, manage_channels=True, move_members=True),
            }
        )
        room_owners[new_ch.id] = uid
        await member.move_to(new_ch)
        try:
            invite = await new_ch.create_invite(max_age=86400, max_uses=10, reason="Room creation invite")
            await member.send(
                f"🏠 Your private study room has been created!\n"
                f"**Room:** {new_ch.name}\n"
                f"**Invite link** (valid 24h, 10 uses): {invite.url}\n"
                f"Share this with your friends to invite them in."
            )
        except Exception:
            pass

    # ── Auto-delete empty private rooms ───────────────────────────
    if before.channel and before.channel.category_id == PRIVATE_VC_CATEGORY_ID:
        ch = before.channel
        if ch.id != CREATE_ROOM_CHANNEL_ID and len(ch.members) == 0:
            room_owners.pop(ch.id, None)
            sess = vc_sessions.pop(ch.id, None)
            if sess and sess.task:
                sess.task.cancel()
            await ch.delete(reason="Private study room empty")

    save_data(data)

@bot.event
async def on_member_join(member: discord.Member):
    data = load_data()
    u = get_user(data, member.id)
    u["username"] = member.name
    save_data(data)
    embed = discord.Embed(
        title=f"👋 Welcome to {member.guild.name}",
        description=(
            "This server is built for serious students.\n\n"
            "Start with `/onboarding` to set your exam, daily study target, timezone, and focus goal."
        ),
        color=0x5865F2
    )
    embed.add_field(
        name="First steps",
        value="1. Run `/onboarding`\n2. Join a study VC\n3. Use `/stats` and `/goal_status`\n4. Compete in sprints and weekly awards",
        inline=False
    )
    try:
        await member.send(embed=embed)
    except Exception:
        pass

# ─────────────────────────────────────────────
#  BACKGROUND TASKS
# ─────────────────────────────────────────────
@tasks.loop(minutes=5)
async def checkpoint_sessions():
    data = load_data()
    now = time.time()
    guild = bot.get_guild(GUILD_ID)
    if not guild:
        return
    updated = False
    for vc in guild.voice_channels:
        for member in vc.members:
            if member.bot:
                continue
            u = get_user(data, member.id)
            u["username"] = member.name
            if u["vc_join_time"] is None:
                u["vc_join_time"] = now
                updated = True
    if updated:
        save_data(data)

@tasks.loop(hours=6)
async def backup_data():
    do_backup()
    print(f"💾 Auto-backup done at {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")

@tasks.loop(minutes=3)
async def update_studying_status():
    """Update the locked VC channel name to show live studying count.
    Also updates bot's own presence."""
    guild = bot.get_guild(GUILD_ID)
    if not guild:
        return

    count = count_studying(guild)

    # Update bot presence
    await bot.change_presence(
        activity=discord.Activity(
            type=discord.ActivityType.watching,
            name=f"{count} people studying 📚"
        )
    )

    # Update the dedicated "counter" voice channel name
    if STUDYING_COUNT_CHANNEL_ID:
        ch = guild.get_channel(STUDYING_COUNT_CHANNEL_ID)
        if ch:
            new_name = f"📚 Studying: {count}"
            if ch.name != new_name:
                try:
                    await ch.edit(name=new_name)
                except Exception:
                    pass  # Discord rate-limits channel renames to 2/10min — silently skip

# ─────────────────────────────────────────────
#  POMO EMBED BUILDER
# ─────────────────────────────────────────────
async def build_pomo_embed(sess: VCPomodoroSession, channel: discord.VoiceChannel) -> discord.Embed:
    elapsed   = sess.elapsed_in_phase()
    total     = sess.phase_duration
    remaining = sess.remaining_in_phase()

    phase_label = "🍅 FOCUS" if sess.phase == "focus" else "☕ BREAK"
    color = 0xFF4444 if sess.phase == "focus" else 0x44BBFF

    embed = discord.Embed(title=f"{phase_label} — Round {sess.current_round}/{sess.rounds}", color=color)
    embed.add_field(
        name="Progress",
        value=f"{progress_bar(elapsed, total)}\n⏱️ `{fmt_time(elapsed)}` elapsed  •  `{fmt_time(remaining)}` remaining",
        inline=False
    )

    humans = [m for m in channel.members if not m.bot]
    if humans:
        embed.add_field(
            name=f"👥 Studying ({len(humans)})",
            value=", ".join(m.display_name for m in humans),
            inline=False
        )

    next_phase = f"Break in `{fmt_time(remaining)}`" if sess.phase == "focus" else f"Focus in `{fmt_time(remaining)}`"
    embed.set_footer(text=f"{next_phase}  •  Updates every 2 min  •  /vcpomo_stop to end")
    return embed

# ─────────────────────────────────────────────
#  VC POMO RUNNER
# ─────────────────────────────────────────────
async def run_pomodoro_vc(sess: VCPomodoroSession, channel: discord.VoiceChannel, text_channel):
    ch_id = channel.id

    for r in range(1, sess.rounds + 1):
        if ch_id not in vc_sessions:
            return

        # ── FOCUS ──────────────────────────────────────────────────
        sess.current_round = r
        sess.phase = "focus"
        sess.phase_start = time.time()
        sess.phase_duration = sess.focus * 60
        sess.member_join_times = {m.id: time.time() for m in channel.members if not m.bot}

        # Mute only allowed in private VCs
        if sess.mute_on_focus and is_private_vc(channel):
            for m in channel.members:
                if not m.bot:
                    try: await m.edit(mute=True)
                    except: pass

        # Ping all studiers: focus starting
        mentions = " ".join(m.mention for m in channel.members if not m.bot)
        embed = await build_pomo_embed(sess, channel)
        sess.live_message = await text_channel.send(
            f"🍅 **Round {r}/{sess.rounds} — FOCUS!** ({sess.focus} min)\n"
            f"{mentions}\nGet to work! 💪",
            embed=embed
        )

        focus_end = time.time() + sess.focus * 60
        while time.time() < focus_end:
            await asyncio.sleep(120)
            if ch_id not in vc_sessions:
                return
            try:
                embed = await build_pomo_embed(sess, channel)
                await sess.live_message.edit(embed=embed)
            except Exception:
                pass

        if ch_id not in vc_sessions:
            return

        # Credit hours
        data = load_data()
        for m in channel.members:
            if not m.bot:
                join_t = sess.member_join_times.get(m.id)
                if join_t:
                    actual_hours = (time.time() - join_t) / 3600
                    add_hours(data, m.id, min(actual_hours, sess.focus / 60))
        save_data(data)

        # Unmute
        if sess.mute_on_focus and is_private_vc(channel):
            for m in channel.members:
                if not m.bot:
                    try: await m.edit(mute=False)
                    except: pass

        if r == sess.rounds:
            embed = discord.Embed(
                title="✅ Pomodoro Complete!",
                description=f"All **{sess.rounds}** rounds finished. Amazing work everyone! 🎉",
                color=0x00FF88
            )
            embed.add_field(name="Total focus time", value=f"{sess.focus * sess.rounds} min")
            await text_channel.send(embed=embed)
            vc_sessions.pop(ch_id, None)
            return

        # ── BREAK ──────────────────────────────────────────────────
        sess.phase = "break"
        sess.phase_start = time.time()
        sess.phase_duration = sess.brk * 60
        sess.member_join_times = {}

        # Ping all studiers: break starting
        mentions = " ".join(m.mention for m in channel.members if not m.bot)
        embed = await build_pomo_embed(sess, channel)
        sess.live_message = await text_channel.send(
            f"☕ **Break time!** ({sess.brk} min) — Relax!\n"
            f"{mentions}\nNext focus starts in {sess.brk} min.",
            embed=embed
        )

        brk_end = time.time() + sess.brk * 60
        while time.time() < brk_end:
            await asyncio.sleep(120)
            if ch_id not in vc_sessions:
                return
            try:
                embed = await build_pomo_embed(sess, channel)
                await sess.live_message.edit(embed=embed)
            except Exception:
                pass

    vc_sessions.pop(ch_id, None)

# ─────────────────────────────────────────────
#  SLASH – STATS
# ─────────────────────────────────────────────
@tree.command(name="stats", description="View your study stats", guild=discord.Object(id=GUILD_ID))
@app_commands.describe(user="User to look up (leave empty for yourself)")
async def stats_cmd(interaction: discord.Interaction, user: discord.Member = None):
    target = user or interaction.user
    data = load_data()
    u = get_user(data, target.id)

    daily_h   = u["hours"]["daily"].get(today_key(), 0)
    weekly_h  = weekly_hours(data, target.id)
    monthly_h = u["hours"]["monthly"].get(month_key(), 0)
    alltime_h = u["hours"]["alltime"]

    # Live session bonus — show in-progress VC time
    live_h = 0.0
    if u["vc_join_time"]:
        live_h = round((time.time() - u["vc_join_time"]) / 3600, 2)

    embed = discord.Embed(title="📊 Personal Study Statistics", color=0x5865F2)
    embed.set_author(name=target.display_name, icon_url=target.display_avatar.url)

    hours_val = f"{daily_h:.1f}h\n{weekly_h:.1f}h\n{monthly_h:.1f}h\n{alltime_h:.1f}h"
    if live_h > 0:
        hours_val += f"\n*(+{live_h:.1f}h live)*"

    embed.add_field(name="Timeframe", value="Daily:\nWeekly:\nMonthly:\nAll-time:", inline=True)
    embed.add_field(name="Hours", value=hours_val, inline=True)
    embed.add_field(name="Rank", value=(
        f"#{rank_on(data, target.id, 'daily')}\n"
        f"#{rank_on(data, target.id, 'weekly')}\n"
        f"#{rank_on(data, target.id, 'monthly')}\n"
        f"#{rank_on(data, target.id, 'alltime')}"
    ), inline=True)

    avg = monthly_h / max(datetime.now(timezone.utc).day, 1)
    embed.add_field(name=f"Average/day ({datetime.now(timezone.utc).strftime('%B')})", value=f"{avg:.1f}h", inline=False)

    streak = u["streak"]
    embed.add_field(name="🔥 Current streak", value=f"{streak['current']} day(s)", inline=True)
    embed.add_field(name="🏆 Longest streak", value=f"{streak['longest']} day(s)", inline=True)

    badges = get_badges(alltime_h, streak["current"])
    if badges:
        embed.add_field(name="Badges", value=badges, inline=False)

    await interaction.response.send_message(embed=embed)


@tree.command(name="streak", description="Check your study streak", guild=discord.Object(id=GUILD_ID))
@app_commands.describe(user="User to check (leave empty for yourself)")
async def streak_cmd(interaction: discord.Interaction, user: discord.Member = None):
    target = user or interaction.user
    data = load_data()
    u = get_user(data, target.id)
    streak = u["streak"]
    current = streak["current"]
    longest = streak["longest"]

    # Flame visual — one flame per day, max 30 shown
    flames = min(current, 30)
    flame_bar = "🔥" * flames + ("  *(+" + str(current - 30) + " more)*" if current > 30 else "")

    embed = discord.Embed(title=f"🔥 Study Streak — {target.display_name}", color=0xFF6600)
    embed.add_field(name="Current Streak", value=f"**{current}** day(s)\n{flame_bar or '*(no active streak)*'}", inline=False)
    embed.add_field(name="🏆 Longest Streak", value=f"**{longest}** day(s)", inline=True)
    embed.add_field(name="Last Study Date", value=streak["last_study_date"] or "Never", inline=True)

    if current >= 30:
        embed.set_footer(text="💎 Legendary streak! Keep it going!")
    elif current >= 14:
        embed.set_footer(text="🔥 On fire! Two weeks strong!")
    elif current >= 7:
        embed.set_footer(text="⚡ One week streak! Keep pushing!")
    elif current >= 3:
        embed.set_footer(text="📈 Building momentum!")
    elif current == 0:
        embed.set_footer(text="Study today to start your streak!")

    await interaction.response.send_message(embed=embed)


@tree.command(name="compare", description="Compare your stats side by side with another user", guild=discord.Object(id=GUILD_ID))
@app_commands.describe(user="User to compare against")
async def compare_cmd(interaction: discord.Interaction, user: discord.Member):
    if user.id == interaction.user.id:
        await interaction.response.send_message("❌ Pick someone else to compare with!", ephemeral=True)
        return

    data = load_data()
    a = get_user(data, interaction.user.id)
    b = get_user(data, user.id)

    def fmt(u_data, uid):
        daily   = u_data["hours"]["daily"].get(today_key(), 0)
        weekly  = weekly_hours(data, uid)
        monthly = u_data["hours"]["monthly"].get(month_key(), 0)
        alltime = u_data["hours"]["alltime"]
        streak  = u_data["streak"]["current"]
        return daily, weekly, monthly, alltime, streak

    a_d, a_w, a_m, a_at, a_s = fmt(a, interaction.user.id)
    b_d, b_w, b_m, b_at, b_s = fmt(b, user.id)

    def winner(av, bv):
        if av > bv:   return "⬆️", "⬇️"
        elif av < bv: return "⬇️", "⬆️"
        else:         return "➡️", "➡️"

    wd = winner(a_d, b_d)
    ww = winner(a_w, b_w)
    wm = winner(a_m, b_m)
    wat = winner(a_at, b_at)
    ws = winner(a_s, b_s)

    embed = discord.Embed(title="⚔️ Study Comparison", color=0x9B59B6)
    embed.add_field(
        name=f"📊 {interaction.user.display_name}",
        value=(
            f"Daily: **{a_d:.1f}h** {wd[0]}\n"
            f"Weekly: **{a_w:.1f}h** {ww[0]}\n"
            f"Monthly: **{a_m:.1f}h** {wm[0]}\n"
            f"All-time: **{a_at:.1f}h** {wat[0]}\n"
            f"Streak: **{a_s}d** {ws[0]}"
        ),
        inline=True
    )
    embed.add_field(
        name=f"📊 {user.display_name}",
        value=(
            f"Daily: **{b_d:.1f}h** {wd[1]}\n"
            f"Weekly: **{b_w:.1f}h** {ww[1]}\n"
            f"Monthly: **{b_m:.1f}h** {wm[1]}\n"
            f"All-time: **{b_at:.1f}h** {wat[1]}\n"
            f"Streak: **{b_s}d** {ws[1]}"
        ),
        inline=True
    )

    # Overall winner by alltime
    if a_at > b_at:
        embed.set_footer(text=f"🏆 {interaction.user.display_name} is ahead overall!")
    elif b_at > a_at:
        embed.set_footer(text=f"🏆 {user.display_name} is ahead overall!")
    else:
        embed.set_footer(text="🤝 Dead even!")

    await interaction.response.send_message(embed=embed)


@tree.command(name="leaderboard", description="Show server leaderboard", guild=discord.Object(id=GUILD_ID))
@app_commands.choices(period=[
    app_commands.Choice(name="Daily",    value="daily"),
    app_commands.Choice(name="Weekly",   value="weekly"),
    app_commands.Choice(name="Monthly",  value="monthly"),
    app_commands.Choice(name="All-time", value="alltime"),
])
async def leaderboard_cmd(interaction: discord.Interaction, period: str = "alltime"):
    data = load_data()
    guild = interaction.guild
    scores = []

    for uid_str, u in data.items():
        if period == "alltime":   h = u["hours"]["alltime"]
        elif period == "monthly": h = u["hours"]["monthly"].get(month_key(), 0)
        elif period == "daily":   h = u["hours"]["daily"].get(today_key(), 0)
        elif period == "weekly":  h = weekly_hours(data, int(uid_str))
        else: h = 0
        if h > 0:
            scores.append((int(uid_str), h))

    scores.sort(key=lambda x: x[1], reverse=True)
    top = scores[:10]
    max_h = top[0][1] if top else 1

    medals = ["🥇", "🥈", "🥉"]
    lines = []
    for i, (uid, h) in enumerate(top):
        member = guild.get_member(uid)
        name = member.display_name if member else f"User {uid}"
        medal = medals[i] if i < 3 else f"`#{i+1}`"
        bar = progress_bar(int(h * 10), int(max_h * 10), 10)
        lines.append(f"{medal} **{name}** — {h:.1f}h\n{bar}")

    embed = discord.Embed(
        title=f"🏆 Leaderboard — {period.capitalize()}",
        description="\n".join(lines) if lines else "No data yet.",
        color=0xFFD700
    )
    await interaction.response.send_message(embed=embed)


@tree.command(name="sessions", description="View your recent tracked study sessions", guild=discord.Object(id=GUILD_ID))
@app_commands.describe(user="User to look up (leave empty for yourself)")
async def sessions_cmd(interaction: discord.Interaction, user: discord.Member = None):
    target = user or interaction.user
    data = load_data()
    u = get_user(data, target.id)
    sessions = list(reversed(u["sessions"][-7:]))

    if not sessions:
        await interaction.response.send_message("No tracked sessions yet.", ephemeral=True)
        return

    lines = []
    for i, sess in enumerate(sessions, 1):
        duration = fmt_hours_short((sess.get("duration_min", 0) or 0) / 60)
        start = fmt_datetime_utc(sess.get("start"))
        end = fmt_datetime_utc(sess.get("end"))
        lines.append(f"**{i}.** {duration}\nStart: {start}\nEnd: {end}")

    embed = discord.Embed(
        title=f"🗂️ Recent Sessions — {target.display_name}",
        description="\n\n".join(lines),
        color=0x4CAF50
    )
    embed.set_footer(text="Showing the 7 most recent completed VC sessions tracked by main.py")
    await interaction.response.send_message(embed=embed, ephemeral=(target == interaction.user))


@tree.command(name="goal_set", description="Set your daily study goal in hours", guild=discord.Object(id=GUILD_ID))
@app_commands.describe(hours="Daily target in hours, e.g. 2.5")
async def goal_set_cmd(interaction: discord.Interaction, hours: float):
    if hours < 0 or hours > 24:
        await interaction.response.send_message("❌ Goal must be between 0 and 24 hours.", ephemeral=True)
        return

    data = load_data()
    u = get_user(data, interaction.user.id)
    u["username"] = interaction.user.name
    u["goals"]["daily_hours"] = round(hours, 2)
    u["goals"]["updated_at"] = time.time()
    save_data(data)

    if hours == 0:
        await interaction.response.send_message("✅ Your daily study goal has been cleared.", ephemeral=True)
        return

    current, goal, pct = goal_progress(data, interaction.user.id)
    embed = discord.Embed(title="🎯 Daily Goal Updated", color=0x2ECC71)
    embed.add_field(name="Goal", value=fmt_hours_short(goal), inline=True)
    embed.add_field(name="Today", value=fmt_hours_short(current), inline=True)
    embed.add_field(name="Progress", value=f"{pct:.0f}%", inline=True)
    await interaction.response.send_message(embed=embed, ephemeral=True)


@tree.command(name="goal_status", description="Check daily goal progress", guild=discord.Object(id=GUILD_ID))
@app_commands.describe(user="User to check (leave empty for yourself)")
async def goal_status_cmd(interaction: discord.Interaction, user: discord.Member = None):
    target = user or interaction.user
    data = load_data()
    u = get_user(data, target.id)
    current, goal, pct = goal_progress(data, target.id)

    if goal <= 0:
        msg = "No daily goal set yet." if target == interaction.user else f"{target.display_name} has not set a daily goal yet."
        await interaction.response.send_message(msg, ephemeral=(target == interaction.user))
        return

    remaining = max(0.0, goal - current)
    embed = discord.Embed(title=f"🎯 Daily Goal — {target.display_name}", color=0xF1C40F)
    embed.add_field(name="Goal", value=fmt_hours_short(goal), inline=True)
    embed.add_field(name="Done Today", value=fmt_hours_short(current), inline=True)
    embed.add_field(name="Remaining", value=fmt_hours_short(remaining), inline=True)
    embed.add_field(name="Progress", value=f"{progress_bar(int(current * 60), int(goal * 60), 12)}", inline=False)
    embed.set_footer(text=f"Goal last updated: {fmt_datetime_utc(u['goals'].get('updated_at'))}")
    await interaction.response.send_message(embed=embed, ephemeral=(target == interaction.user))


@tree.command(name="active_studiers", description="See who is active in VC and for how long", guild=discord.Object(id=GUILD_ID))
@app_commands.choices(scope=[
    app_commands.Choice(name="Anyone in Voice", value="all"),
    app_commands.Choice(name="Study Channels Only", value="study"),
])
async def active_studiers_cmd(interaction: discord.Interaction, scope: str = "all"):
    guild = interaction.guild
    active = get_current_voice_members(guild, scope)

    if not active:
        if scope == "study":
            await interaction.response.send_message("No one is currently active in the tracked study VC categories.", ephemeral=True)
        else:
            await interaction.response.send_message("No one is currently active in voice channels right now.", ephemeral=True)
        return

    lines = []
    for member, vc, hours in active[:12]:
        pomo = vc_sessions.get(vc.id)
        suffix = ""
        if pomo:
            suffix = f" • {pomo.phase.upper()} R{pomo.current_round}/{pomo.rounds}"
        lines.append(f"**{member.display_name}** — {fmt_hours_short(hours)} in {vc.mention}{suffix}")

    embed = discord.Embed(
        title=f"{'📚 Active Studiers' if scope == 'study' else '🎙️ Server Voice Activity'} ({len(active)})",
        description="\n".join(lines),
        color=0x5865F2
    )
    footer = "Tracked using current VC presence and elapsed join time from main.py"
    if scope == "study":
        footer += " • filtered to study categories"
    embed.set_footer(text=footer)
    await interaction.response.send_message(embed=embed)


@tree.command(name="onboarding", description="Set up your student profile and study preferences", guild=discord.Object(id=GUILD_ID))
async def onboarding_cmd(interaction: discord.Interaction):
    data = load_data()
    u = get_user(data, interaction.user.id)
    u["username"] = interaction.user.name
    save_data(data)
    embed = build_onboarding_embed(interaction.user, u)
    await interaction.response.send_message(embed=embed, view=OnboardingView(interaction.user.id), ephemeral=True)

# ─────────────────────────────────────────────
#  SLASH – POMODORO (INDIVIDUAL)
# ─────────────────────────────────────────────
async def run_pomodoro_individual(interaction: discord.Interaction, focus: int, brk: int, rounds: int):
    uid = interaction.user.id

    for r in range(1, rounds + 1):
        if uid not in active_pomodoros:
            return

        total_sec = focus * 60
        start_t = time.time()
        msg = await interaction.followup.send(
            f"🍅 **Round {r}/{rounds} — FOCUS** ({focus} min) — {interaction.user.mention} get to work! 💪\n"
            f"{progress_bar(0, total_sec)}\n⏱️ `{fmt_time(total_sec)}` remaining"
        )

        focus_end = time.time() + total_sec
        while time.time() < focus_end:
            await asyncio.sleep(120)
            if uid not in active_pomodoros:
                return
            elapsed = int(time.time() - start_t)
            remaining = max(0, total_sec - elapsed)
            try:
                await msg.edit(content=(
                    f"🍅 **Round {r}/{rounds} — FOCUS** ({focus} min) — {interaction.user.mention} keep going! 💪\n"
                    f"{progress_bar(elapsed, total_sec)}\n⏱️ `{fmt_time(remaining)}` remaining"
                ))
            except Exception:
                pass

        if uid not in active_pomodoros:
            return

        data = load_data()
        add_hours(data, uid, focus / 60)
        save_data(data)

        if r == rounds:
            await interaction.followup.send(
                f"✅ {interaction.user.mention} **Pomodoro complete!** All {rounds} round(s) done. Great work! 🎉"
            )
            active_pomodoros.pop(uid, None)
            return

        brk_sec = brk * 60
        brk_start = time.time()
        msg = await interaction.followup.send(
            f"☕ **Round {r}/{rounds} — BREAK** ({brk} min). Relax!\n"
            f"{progress_bar(0, brk_sec)}\n⏱️ `{fmt_time(brk_sec)}` remaining"
        )
        brk_end = time.time() + brk_sec
        while time.time() < brk_end:
            await asyncio.sleep(120)
            if uid not in active_pomodoros:
                return
            elapsed = int(time.time() - brk_start)
            remaining = max(0, brk_sec - elapsed)
            try:
                await msg.edit(content=(
                    f"☕ **Round {r}/{rounds} — BREAK** ({brk} min). Relax!\n"
                    f"{progress_bar(elapsed, brk_sec)}\n⏱️ `{fmt_time(remaining)}` remaining"
                ))
            except Exception:
                pass

    active_pomodoros.pop(uid, None)


@tree.command(name="pomodoro", description="Start a personal pomodoro timer", guild=discord.Object(id=GUILD_ID))
@app_commands.describe(focus="Focus minutes (default 25)", break_time="Break minutes (default 5)", rounds="Number of rounds (default 4)")
async def pomodoro_cmd(interaction: discord.Interaction, focus: int = 25, break_time: int = 5, rounds: int = 4):
    uid = interaction.user.id
    if uid in active_pomodoros:
        await interaction.response.send_message("❌ You already have a pomodoro running! Use `/pomodoro_stop` first.", ephemeral=True)
        return
    await interaction.response.send_message(
        f"🍅 Starting **{rounds} round(s)** of {focus}/{break_time} min for {interaction.user.mention}!"
    )
    task = asyncio.create_task(run_pomodoro_individual(interaction, focus, break_time, rounds))
    active_pomodoros[uid] = task


@tree.command(name="pomodoro_stop", description="Stop your personal pomodoro", guild=discord.Object(id=GUILD_ID))
async def pomodoro_stop_cmd(interaction: discord.Interaction):
    uid = interaction.user.id
    task = active_pomodoros.pop(uid, None)
    if task:
        task.cancel()
        await interaction.response.send_message("⏹️ Your pomodoro has been stopped.", ephemeral=True)
    else:
        await interaction.response.send_message("You don't have an active pomodoro.", ephemeral=True)

# ─────────────────────────────────────────────
#  SLASH – VC POMODORO
# ─────────────────────────────────────────────
@tree.command(name="vcpomo", description="Start a VC-wide pomodoro. Timer posts in THIS channel.", guild=discord.Object(id=GUILD_ID))
@app_commands.describe(
    focus="Focus minutes (default 25)",
    break_time="Break minutes (default 5)",
    rounds="Rounds (default 4)",
    mute_during_focus="Server-mute during focus? Only works in private rooms."
)
async def vcpomo_cmd(interaction: discord.Interaction, focus: int = 25, break_time: int = 5,
                      rounds: int = 4, mute_during_focus: bool = False):
    if not interaction.user.voice or not interaction.user.voice.channel:
        await interaction.response.send_message("❌ You must be in a voice channel!", ephemeral=True)
        return

    vc = interaction.user.voice.channel

    if vc.category_id not in (PUBLIC_VC_CATEGORY_ID, PRIVATE_VC_CATEGORY_ID):
        await interaction.response.send_message("❌ This VC isn't in a study category.", ephemeral=True)
        return

    if vc.id in vc_sessions:
        await interaction.response.send_message("❌ A pomodoro is already running in this VC.", ephemeral=True)
        return

    # ── BUG FIX: block muting in public VCs entirely ───────────────
    if is_public_vc(vc) and mute_during_focus:
        mute_during_focus = False
        await interaction.response.send_message(
            "⚠️ Muting is not allowed in public VCs. Starting without mute.",
            ephemeral=True
        )
        # Can't send another response, so we continue below without deferring
        # Send the start message as a followup instead
        await interaction.followup.send(
            f"🍅 **VC Pomodoro starting** in {vc.mention}!\n"
            f"**{rounds} round(s)** — {focus} min focus / {break_time} min break\n"
            f"🔇 Mute during focus: ❌ No (disabled in public VCs)\n"
            f"Timer + pings in this channel."
        )
    else:
        await interaction.response.send_message(
            f"🍅 **VC Pomodoro starting** in {vc.mention}!\n"
            f"**{rounds} round(s)** — {focus} min focus / {break_time} min break\n"
            f"🔇 Mute during focus: {'✅ Yes' if mute_during_focus else '❌ No'}\n"
            f"Timer + pings in this channel."
        )

    sess = VCPomodoroSession(vc.id, focus, break_time, rounds, mute_during_focus)
    vc_sessions[vc.id] = sess
    task = asyncio.create_task(run_pomodoro_vc(sess, vc, interaction.channel))
    sess.task = task


@tree.command(name="vcpomo_stop", description="Stop the VC pomodoro (mods or room owner only)", guild=discord.Object(id=GUILD_ID))
async def vcpomo_stop_cmd(interaction: discord.Interaction):
    if not interaction.user.voice or not interaction.user.voice.channel:
        await interaction.response.send_message("❌ Join the voice channel first.", ephemeral=True)
        return
    vc = interaction.user.voice.channel
    uid = interaction.user.id
    mod = any(r.id in (ADMIN_ROLE_ID, MOD_ROLE_ID) for r in interaction.user.roles)
    owner = room_owners.get(vc.id) == uid

    if not (mod or owner) and not is_public_vc(vc):
        await interaction.response.send_message("❌ Only mods or the room owner can stop this.", ephemeral=True)
        return

    sess = vc_sessions.pop(vc.id, None)
    if sess:
        if sess.task:
            sess.task.cancel()
        for m in vc.members:
            if not m.bot:
                try: await m.edit(mute=False)
                except: pass
        await interaction.response.send_message("⏹️ VC pomodoro stopped. Everyone unmuted.")
    else:
        await interaction.response.send_message("No pomodoro running in your VC.", ephemeral=True)


@tree.command(name="vcpomo_status", description="Check current VC pomodoro status (live, updates every 30s)", guild=discord.Object(id=GUILD_ID))
async def vcpomo_status_cmd(interaction: discord.Interaction):
    if not interaction.user.voice or not interaction.user.voice.channel:
        await interaction.response.send_message("❌ You must be in a voice channel.", ephemeral=True)
        return

    vc = interaction.user.voice.channel
    sess = vc_sessions.get(vc.id)
    if not sess:
        await interaction.response.send_message("No pomodoro running in your VC.", ephemeral=True)
        return

    # ── BUG FIX: live updating status embed ───────────────────────
    # Sends an ephemeral embed that edits itself every 30s for the
    # duration of the current phase instead of being a dead snapshot.
    embed = await build_pomo_embed(sess, vc)
    await interaction.response.send_message(embed=embed, ephemeral=True)

    # Keep updating for up to the remaining phase time (max 30 updates = 15 min)
    for _ in range(30):
        await asyncio.sleep(30)
        # Stop updating if session ended or phase changed
        current_sess = vc_sessions.get(vc.id)
        if not current_sess or current_sess is not sess:
            break
        try:
            embed = await build_pomo_embed(sess, vc)
            await interaction.edit_original_response(embed=embed)
        except Exception:
            break

# ─────────────────────────────────────────────
#  SLASH – PRIVATE ROOMS
# ─────────────────────────────────────────────
def is_room_owner_check(interaction: discord.Interaction) -> bool:
    if not interaction.user.voice or not interaction.user.voice.channel:
        return False
    return room_owners.get(interaction.user.voice.channel.id) == interaction.user.id

def is_mod_check(interaction: discord.Interaction) -> bool:
    return any(r.id in (ADMIN_ROLE_ID, MOD_ROLE_ID) for r in interaction.user.roles)


@tree.command(name="admin_exam_sprint", description="[ADMIN] Announce an exam sprint event", guild=discord.Object(id=GUILD_ID))
@app_commands.describe(
    title="Sprint title, e.g. NEET Final Push",
    duration_hours="How long the sprint runs",
    reward="What winners/getters receive",
    channel="Channel to post the announcement in",
    notes="Extra instructions or rules"
)
async def admin_exam_sprint_cmd(
    interaction: discord.Interaction,
    title: str,
    duration_hours: int,
    reward: str,
    channel: discord.TextChannel = None,
    notes: str = "Join study VC, stay focused, and log real hours."
):
    if not is_admin_check(interaction):
        await interaction.response.send_message("❌ Admins only.", ephemeral=True)
        return

    target_channel = channel or interaction.channel
    ends_at = datetime.now(timezone.utc) + timedelta(hours=duration_hours)
    embed = discord.Embed(
        title=f"🚀 Exam Sprint: {title}",
        description=(
            "This is an admin-launched focused sprint for the server.\n\n"
            f"**Duration:** {duration_hours} hour(s)\n"
            f"**Reward:** {reward}\n"
            f"**Ends:** {ends_at.strftime('%Y-%m-%d %H:%M UTC')}\n\n"
            f"**Rules / Notes:** {notes}"
        ),
        color=0xE67E22
    )
    embed.add_field(
        name="How to join",
        value="1. Join a VC\n2. Stay focused\n3. Let the bot track your hours\n4. Check `/active_studiers` and `/stats`",
        inline=False
    )
    embed.set_footer(text=f"Announced by {interaction.user.display_name}")

    await target_channel.send("@everyone", embed=embed)
    await interaction.response.send_message(f"✅ Exam sprint announced in {target_channel.mention}.", ephemeral=True)


@tree.command(name="weekly_awards", description="Show the weekly top studiers", guild=discord.Object(id=GUILD_ID))
@app_commands.choices(period_mode=[
    app_commands.Choice(name="Current rolling week", value="current"),
    app_commands.Choice(name="Previous full week", value="previous"),
])
async def weekly_awards_cmd(interaction: discord.Interaction, period_mode: str = "current"):
    data = load_data()
    previous_week = period_mode == "previous"
    winners = build_weekly_awards(data, interaction.guild, previous_week=previous_week)

    if not winners:
        await interaction.response.send_message("No tracked study hours yet for this weekly awards window.", ephemeral=True)
        return

    medals = ["🥇", "🥈", "🥉"]
    labels = ["Study Emperor", "Discipline Monster", "Focus Machine"]
    lines = []
    for i, (uid, hours) in enumerate(winners):
        member = interaction.guild.get_member(uid)
        name = member.mention if member else f"User `{uid}`"
        lines.append(f"{medals[i]} {name} — **{hours:.1f}h** • {labels[i]}")

    title_suffix = "Previous Week" if previous_week else "Current Rolling Week"
    embed = discord.Embed(
        title=f"🏆 Weekly Awards — {title_suffix}",
        description="\n".join(lines),
        color=0xF1C40F
    )
    embed.add_field(
        name="Recognition",
        value="Top 3 are based on tracked study hours from main.py voice activity data.",
        inline=False
    )
    await interaction.response.send_message(embed=embed)


@tree.command(name="admin_post_weekly_awards", description="[ADMIN] Post weekly awards and store them in member history", guild=discord.Object(id=GUILD_ID))
@app_commands.choices(period_mode=[
    app_commands.Choice(name="Current rolling week", value="current"),
    app_commands.Choice(name="Previous full week", value="previous"),
])
@app_commands.describe(channel="Channel to post the awards in")
async def admin_post_weekly_awards_cmd(
    interaction: discord.Interaction,
    channel: discord.TextChannel = None,
    period_mode: str = "previous"
):
    if not is_admin_check(interaction):
        await interaction.response.send_message("❌ Admins only.", ephemeral=True)
        return

    data = load_data()
    previous_week = period_mode == "previous"
    winners = build_weekly_awards(data, interaction.guild, previous_week=previous_week)
    if not winners:
        await interaction.response.send_message("No tracked study hours found for that weekly awards window.", ephemeral=True)
        return

    target_channel = channel or interaction.channel
    medals = ["🥇", "🥈", "🥉"]
    labels = ["Study Emperor", "Discipline Monster", "Focus Machine"]
    lines = []

    for i, (uid, hours) in enumerate(winners):
        member = interaction.guild.get_member(uid)
        name = member.mention if member else f"User `{uid}`"
        label = labels[i]
        lines.append(f"{medals[i]} {name} — **{hours:.1f}h** • {label}")
        record_award(data, uid, f"Weekly Award: {label}", f"{hours:.1f}h in {'previous' if previous_week else 'current'} weekly window")

    save_data(data)

    title_suffix = "Previous Week" if previous_week else "Current Rolling Week"
    embed = discord.Embed(
        title=f"🏆 Weekly Awards — {title_suffix}",
        description="\n".join(lines),
        color=0xF1C40F
    )
    embed.add_field(
        name="Server Standard",
        value="Elite students do not just show up. They stack hours consistently.",
        inline=False
    )
    embed.set_footer(text=f"Posted by {interaction.user.display_name}")

    await target_channel.send(embed=embed)
    await interaction.response.send_message(f"✅ Weekly awards posted in {target_channel.mention} and saved to member award history.", ephemeral=True)


@tree.command(name="room_invite", description="Invite a user to your private study room", guild=discord.Object(id=GUILD_ID))
@app_commands.describe(user="User to invite")
async def room_invite(interaction: discord.Interaction, user: discord.Member):
    if not is_room_owner_check(interaction):
        await interaction.response.send_message("❌ You must be the room owner.", ephemeral=True)
        return
    ch = interaction.user.voice.channel
    await ch.set_permissions(user, connect=True)
    await interaction.response.send_message(f"✅ {user.mention} has been invited!", ephemeral=True)
    try:
        invite = await ch.create_invite(max_age=3600, max_uses=1, reason="Room invite")
        await user.send(
            f"📨 **{interaction.user.display_name}** invited you to their study room!\n"
            f"**Room:** {ch.name}\n"
            f"**Join link** (1-time use, 1h): {invite.url}"
        )
    except Exception:
        pass


@tree.command(name="room_kick", description="Kick a user from your private study room", guild=discord.Object(id=GUILD_ID))
async def room_kick(interaction: discord.Interaction, user: discord.Member):
    if not is_room_owner_check(interaction) and not is_mod_check(interaction):
        await interaction.response.send_message("❌ Room owner or mod only.", ephemeral=True)
        return
    ch = interaction.user.voice.channel
    await ch.set_permissions(user, connect=False)
    if user.voice and user.voice.channel == ch:
        await user.move_to(None)
    await interaction.response.send_message(f"✅ {user.mention} removed.", ephemeral=True)


@tree.command(name="room_lock", description="Lock your private study room", guild=discord.Object(id=GUILD_ID))
async def room_lock(interaction: discord.Interaction):
    if not is_room_owner_check(interaction):
        await interaction.response.send_message("❌ Room owner only.", ephemeral=True)
        return
    await interaction.user.voice.channel.set_permissions(interaction.guild.default_role, connect=False)
    await interaction.response.send_message("🔒 Room locked.", ephemeral=True)


@tree.command(name="room_unlock", description="Unlock your private study room", guild=discord.Object(id=GUILD_ID))
async def room_unlock(interaction: discord.Interaction):
    if not is_room_owner_check(interaction):
        await interaction.response.send_message("❌ Room owner only.", ephemeral=True)
        return
    await interaction.user.voice.channel.set_permissions(interaction.guild.default_role, connect=True)
    await interaction.response.send_message("🔓 Room unlocked.", ephemeral=True)


@tree.command(name="room_rename", description="Rename your private study room", guild=discord.Object(id=GUILD_ID))
@app_commands.describe(name="New room name")
async def room_rename(interaction: discord.Interaction, name: str):
    if not is_room_owner_check(interaction):
        await interaction.response.send_message("❌ Room owner only.", ephemeral=True)
        return
    await interaction.user.voice.channel.edit(name=name)
    await interaction.response.send_message(f"✅ Room renamed to **{name}**.", ephemeral=True)


@tree.command(name="room_limit", description="Set user limit for your private room", guild=discord.Object(id=GUILD_ID))
@app_commands.describe(limit="Max users (0 = unlimited)")
async def room_limit(interaction: discord.Interaction, limit: int):
    if not is_room_owner_check(interaction):
        await interaction.response.send_message("❌ Room owner only.", ephemeral=True)
        return
    await interaction.user.voice.channel.edit(user_limit=limit)
    await interaction.response.send_message(f"✅ Room limit set to {limit}.", ephemeral=True)


@tree.command(name="room_transfer", description="Transfer room ownership to another user", guild=discord.Object(id=GUILD_ID))
@app_commands.describe(user="New owner")
async def room_transfer(interaction: discord.Interaction, user: discord.Member):
    if not is_room_owner_check(interaction):
        await interaction.response.send_message("❌ Room owner only.", ephemeral=True)
        return
    ch = interaction.user.voice.channel
    room_owners[ch.id] = user.id
    await ch.set_permissions(user, connect=True, manage_channels=True, move_members=True)
    await ch.set_permissions(interaction.user, connect=True, manage_channels=False, move_members=False)
    await interaction.response.send_message(f"✅ Ownership transferred to {user.mention}.", ephemeral=True)
    try:
        await user.send(f"👑 You are now the owner of **{ch.name}** in **{interaction.guild.name}**!")
    except Exception:
        pass


@tree.command(name="room_info", description="Show info about your current private room", guild=discord.Object(id=GUILD_ID))
async def room_info(interaction: discord.Interaction):
    if not interaction.user.voice or not interaction.user.voice.channel:
        await interaction.response.send_message("❌ You must be in a voice channel.", ephemeral=True)
        return
    ch = interaction.user.voice.channel
    if ch.category_id != PRIVATE_VC_CATEGORY_ID:
        await interaction.response.send_message("❌ This isn't a private study room.", ephemeral=True)
        return
    owner_id = room_owners.get(ch.id)
    owner = interaction.guild.get_member(owner_id) if owner_id else None
    humans = [m for m in ch.members if not m.bot]
    embed = discord.Embed(title=f"🏠 {ch.name}", color=0x5865F2)
    embed.add_field(name="Owner", value=owner.mention if owner else "Unknown")
    embed.add_field(name="Members", value=f"{len(humans)}/{ch.user_limit or '∞'}")
    embed.add_field(name="In room", value=", ".join(m.display_name for m in humans) or "Empty", inline=False)
    pomo = vc_sessions.get(ch.id)
    embed.add_field(name="Pomodoro", value=f"Round {pomo.current_round}/{pomo.rounds} — {pomo.phase.upper()}" if pomo else "None")
    await interaction.response.send_message(embed=embed, ephemeral=True)

# ─────────────────────────────────────────────
#  SLASH – MODERATION
# ─────────────────────────────────────────────
async def send_mod_log(guild: discord.Guild, embed: discord.Embed):
    ch = guild.get_channel(LOG_CHANNEL_ID)
    if ch:
        await ch.send(embed=embed)


@tree.command(name="warn", description="Warn a user", guild=discord.Object(id=GUILD_ID))
@app_commands.describe(user="User to warn", reason="Reason")
async def warn_cmd(interaction: discord.Interaction, user: discord.Member, reason: str = "No reason provided"):
    if not is_mod_check(interaction):
        await interaction.response.send_message("❌ Mods only.", ephemeral=True)
        return
    data = load_data()
    u = get_user(data, user.id)
    u["warnings"].append({"reason": reason, "time": time.time(), "by": interaction.user.id})
    save_data(data)
    warn_count = len(u["warnings"])
    embed = discord.Embed(title="⚠️ Warning Issued", color=0xFFA500)
    embed.add_field(name="User", value=user.mention)
    embed.add_field(name="Reason", value=reason)
    embed.add_field(name="Total Warnings", value=str(warn_count))
    embed.add_field(name="Issued by", value=interaction.user.mention)
    await interaction.response.send_message(embed=embed)
    await send_mod_log(interaction.guild, embed)
    try:
        await user.send(f"⚠️ You have been warned in **{interaction.guild.name}**.\nReason: {reason}\nTotal warnings: {warn_count}")
    except Exception:
        pass


@tree.command(name="warnings", description="View warnings for a user", guild=discord.Object(id=GUILD_ID))
async def warnings_cmd(interaction: discord.Interaction, user: discord.Member):
    if not is_mod_check(interaction):
        await interaction.response.send_message("❌ Mods only.", ephemeral=True)
        return
    data = load_data()
    u = get_user(data, user.id)
    warns = u["warnings"]
    if not warns:
        await interaction.response.send_message(f"{user.mention} has no warnings.", ephemeral=True)
        return
    lines = [
        f"**{i}.** {w['reason']} — {datetime.fromtimestamp(w['time'], tz=timezone.utc).strftime('%Y-%m-%d')}"
        for i, w in enumerate(warns, 1)
    ]
    embed = discord.Embed(title=f"⚠️ Warnings for {user.display_name}", description="\n".join(lines), color=0xFFA500)
    await interaction.response.send_message(embed=embed, ephemeral=True)


@tree.command(name="clearwarnings", description="Clear all warnings for a user", guild=discord.Object(id=GUILD_ID))
async def clearwarnings_cmd(interaction: discord.Interaction, user: discord.Member):
    if not is_mod_check(interaction):
        await interaction.response.send_message("❌ Mods only.", ephemeral=True)
        return
    data = load_data()
    get_user(data, user.id)["warnings"] = []
    save_data(data)
    await interaction.response.send_message(f"✅ Cleared warnings for {user.mention}.", ephemeral=True)


@tree.command(name="kick", description="Kick a user from the server", guild=discord.Object(id=GUILD_ID))
@app_commands.describe(user="User to kick", reason="Reason")
async def kick_cmd(interaction: discord.Interaction, user: discord.Member, reason: str = "No reason provided"):
    if not is_mod_check(interaction):
        await interaction.response.send_message("❌ Mods only.", ephemeral=True)
        return
    await user.kick(reason=reason)
    embed = discord.Embed(title="👢 User Kicked", color=0xFF6600)
    embed.add_field(name="User", value=str(user))
    embed.add_field(name="Reason", value=reason)
    embed.add_field(name="By", value=interaction.user.mention)
    await interaction.response.send_message(embed=embed)
    await send_mod_log(interaction.guild, embed)


@tree.command(name="ban", description="Ban a user from the server", guild=discord.Object(id=GUILD_ID))
@app_commands.describe(user="User", reason="Reason", delete_days="Days of messages to delete (0-7)")
async def ban_cmd(interaction: discord.Interaction, user: discord.Member, reason: str = "No reason provided", delete_days: int = 0):
    if not is_mod_check(interaction):
        await interaction.response.send_message("❌ Mods only.", ephemeral=True)
        return
    await user.ban(reason=reason, delete_message_days=delete_days)
    embed = discord.Embed(title="🔨 User Banned", color=0xFF0000)
    embed.add_field(name="User", value=str(user))
    embed.add_field(name="Reason", value=reason)
    embed.add_field(name="By", value=interaction.user.mention)
    await interaction.response.send_message(embed=embed)
    await send_mod_log(interaction.guild, embed)


@tree.command(name="timeout", description="Timeout a user", guild=discord.Object(id=GUILD_ID))
@app_commands.describe(user="User", minutes="Duration in minutes", reason="Reason")
async def timeout_cmd(interaction: discord.Interaction, user: discord.Member, minutes: int = 10, reason: str = "No reason provided"):
    if not is_mod_check(interaction):
        await interaction.response.send_message("❌ Mods only.", ephemeral=True)
        return
    until = discord.utils.utcnow() + timedelta(minutes=minutes)
    await user.timeout(until, reason=reason)
    embed = discord.Embed(title="⏱️ User Timed Out", color=0xFFFF00)
    embed.add_field(name="User", value=user.mention)
    embed.add_field(name="Duration", value=f"{minutes} min")
    embed.add_field(name="Reason", value=reason)
    await interaction.response.send_message(embed=embed)
    await send_mod_log(interaction.guild, embed)


@tree.command(name="purge", description="Delete messages in bulk", guild=discord.Object(id=GUILD_ID))
@app_commands.describe(amount="Number of messages to delete (1-100)")
async def purge_cmd(interaction: discord.Interaction, amount: int = 10):
    if not is_mod_check(interaction):
        await interaction.response.send_message("❌ Mods only.", ephemeral=True)
        return
    amount = min(max(amount, 1), 100)
    await interaction.response.defer(ephemeral=True)
    deleted = await interaction.channel.purge(limit=amount)
    await interaction.followup.send(f"🗑️ Deleted {len(deleted)} message(s).", ephemeral=True)


@tree.command(name="report", description="Anonymously report a user to staff", guild=discord.Object(id=GUILD_ID))
@app_commands.describe(user="User you're reporting", reason="What happened")
async def report_cmd(interaction: discord.Interaction, user: discord.Member, reason: str):
    embed = discord.Embed(title="🚨 New Report", color=0xFF0000)
    embed.add_field(name="Reported User", value=f"{user} ({user.id})")
    embed.add_field(name="Reason", value=reason)
    embed.add_field(name="Channel", value=interaction.channel.mention)
    embed.set_footer(text="Reported anonymously")
    log_ch = interaction.guild.get_channel(LOG_CHANNEL_ID)
    if log_ch:
        await log_ch.send(embed=embed)
    await interaction.response.send_message("✅ Your report has been sent to staff anonymously.", ephemeral=True)

# ─────────────────────────────────────────────
#  SLASH – ADMIN
# ─────────────────────────────────────────────
@tree.command(name="admin_addhours", description="[ADMIN] Add study hours to a user", guild=discord.Object(id=GUILD_ID))
@app_commands.describe(user="Target user", hours="Hours to add (decimals ok)", note="Reason/note")
async def admin_addhours(interaction: discord.Interaction, user: discord.Member, hours: float, note: str = "Manual import"):
    if not any(r.id == ADMIN_ROLE_ID for r in interaction.user.roles):
        await interaction.response.send_message("❌ Admins only.", ephemeral=True)
        return
    data = load_data()
    u = get_user(data, user.id)
    u["username"] = user.name
    add_hours(data, user.id, hours)
    save_data(data)
    embed = discord.Embed(title="✅ Hours Added (Admin)", color=0x00FF00)
    embed.add_field(name="User", value=user.mention)
    embed.add_field(name="Hours Added", value=f"{hours:.2f}h")
    embed.add_field(name="New All-time Total", value=f"{u['hours']['alltime']:.2f}h")
    embed.add_field(name="Note", value=note)
    embed.set_footer(text=f"By {interaction.user}")
    await interaction.response.send_message(embed=embed, ephemeral=True)
    await send_mod_log(interaction.guild, embed)


@tree.command(name="admin_sethours", description="[ADMIN] Set exact all-time hours for a user", guild=discord.Object(id=GUILD_ID))
@app_commands.describe(user="Target user", hours="Total hours to set", note="Reason/note")
async def admin_sethours(interaction: discord.Interaction, user: discord.Member, hours: float, note: str = "Manual override"):
    if not any(r.id == ADMIN_ROLE_ID for r in interaction.user.roles):
        await interaction.response.send_message("❌ Admins only.", ephemeral=True)
        return
    data = load_data()
    u = get_user(data, user.id)
    u["username"] = user.name
    u["hours"]["alltime"] = round(hours, 4)
    save_data(data)
    embed = discord.Embed(title="✅ Hours Set (Admin)", color=0x00FF00)
    embed.add_field(name="User", value=user.mention)
    embed.add_field(name="All-time hours set to", value=f"{hours:.2f}h")
    embed.add_field(name="Note", value=note)
    embed.set_footer(text=f"By {interaction.user}")
    await interaction.response.send_message(embed=embed, ephemeral=True)
    await send_mod_log(interaction.guild, embed)


@tree.command(name="admin_resetuser", description="[ADMIN] Reset all data for a user", guild=discord.Object(id=GUILD_ID))
async def admin_resetuser(interaction: discord.Interaction, user: discord.Member):
    if not any(r.id == ADMIN_ROLE_ID for r in interaction.user.roles):
        await interaction.response.send_message("❌ Admins only.", ephemeral=True)
        return
    data = load_data()
    key = str(user.id)
    if key in data:
        del data[key]
    save_data(data)
    await interaction.response.send_message(f"✅ Reset all data for {user.mention}.", ephemeral=True)


@tree.command(name="admin_viewdata", description="[ADMIN] View stored data summary for a user", guild=discord.Object(id=GUILD_ID))
async def admin_viewdata(interaction: discord.Interaction, user: discord.Member):
    if not any(r.id == ADMIN_ROLE_ID for r in interaction.user.roles):
        await interaction.response.send_message("❌ Admins only.", ephemeral=True)
        return
    data = load_data()
    u = get_user(data, user.id)
    embed = discord.Embed(title=f"🔍 Data for {user.display_name}", color=0x888888)
    embed.add_field(name="All-time hours", value=f"{u['hours']['alltime']:.2f}h")
    embed.add_field(name="This month", value=f"{u['hours']['monthly'].get(month_key(), 0):.2f}h")
    embed.add_field(name="Today", value=f"{u['hours']['daily'].get(today_key(), 0):.2f}h")
    embed.add_field(name="Streak (current/longest)", value=f"{u['streak']['current']}/{u['streak']['longest']}")
    embed.add_field(name="Warnings", value=str(len(u["warnings"])))
    embed.add_field(name="Sessions logged", value=str(len(u["sessions"])))
    await interaction.response.send_message(embed=embed, ephemeral=True)


@tree.command(name="admin_backup", description="[ADMIN] Trigger a manual backup now", guild=discord.Object(id=GUILD_ID))
async def admin_backup(interaction: discord.Interaction):
    if not any(r.id == ADMIN_ROLE_ID for r in interaction.user.roles):
        await interaction.response.send_message("❌ Admins only.", ephemeral=True)
        return
    do_backup(label="manual")
    backups = sorted(os.listdir(BACKUP_DIR), reverse=True)
    await interaction.response.send_message(
        f"💾 Manual backup created. Total backups stored: **{len(backups)}** (max {MAX_BACKUPS})",
        ephemeral=True
    )


@tree.command(name="admin_listbackups", description="[ADMIN] List available backups", guild=discord.Object(id=GUILD_ID))
async def admin_listbackups(interaction: discord.Interaction):
    if not any(r.id == ADMIN_ROLE_ID for r in interaction.user.roles):
        await interaction.response.send_message("❌ Admins only.", ephemeral=True)
        return
    ensure_dirs()
    backups = sorted(os.listdir(BACKUP_DIR), reverse=True)
    if not backups:
        await interaction.response.send_message("No backups found.", ephemeral=True)
        return
    lines = [f"`{b}`" for b in backups[:20]]
    embed = discord.Embed(title=f"💾 Backups ({len(backups)} total)", description="\n".join(lines), color=0x888888)
    embed.set_footer(text="To restore: cp backups/filename.json data.json  then restart the bot")
    await interaction.response.send_message(embed=embed, ephemeral=True)


# ─────────────────────────────────────────────
#  RUN
# ─────────────────────────────────────────────
ensure_dirs()
bot.run(TOKEN)
