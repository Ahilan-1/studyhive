"""
╔══════════════════════════════════════════════════════════════════╗
║             📚  STUDY BOT — PREMIUM EDITION  v5.0               ║
║         Built for serious study communities                      ║
║                                                                  ║
║  CORE : VC streak · Daily reports · XP · Badges · Quests        ║
║  v2.0 : Invite rewards · Premium · Nap alarm                    ║
║  v3.0 : Premium visual flex · /settings DM toggles              ║
║  v4.0 : 25 frames · 5 tiers · Secret/Prestige frames            ║
║         Tournament system · Public feed · /gift_premium          ║
║         50h+1000XP purchase path · Invite bug fixed             ║
║         /progress dashboard · UX polish pass                    ║
║  v5.0 : Hero frames (Spider-Man · Venom · Iron Man · Batman)    ║
║         /gaming — private gaming room (no study hours)          ║
║         Tournament VC lock — admin sets specific VC             ║
║         Aesthetic frame upgrades across all tiers               ║
╚══════════════════════════════════════════════════════════════════╝

SETUP:
  1. pip install discord.py python-dotenv pytz
  2. Copy .env.example to .env and set TOKEN + channel IDs
  3. Invite bot with: Send Messages, Embed Links, Mention Everyone,
     Manage Roles, Read Message History, Move Members,
     Create Instant Invite, Manage Channels
  4. python studybot.py

PREMIUM UNLOCK PATHS:
  Path 1 — Invite 3 friends (via /invite)
  Path 2 — Reach 50 total hours AND spend 1000 XP (via /premium_status)

FRAME TIERS:
  Standard  — all 9 standard frames (all premium users)
  Cosmic    — 6 space/galaxy frames (all premium users)
  Aesthetic — 5 style frames (all premium users)
  Hero      — 4 superhero frames — Spider-Man, Venom, Iron Man, Batman
  Prestige  — 2 frames (tournament winners only)
  Secret    — 4 frames (special milestone unlocks)

GAMING ROOMS:
  /gaming — creates a private VC in the gaming category
  Time spent in gaming rooms is NOT counted as study hours
  Room auto-deletes when everyone leaves

TOURNAMENT VC LOCK:
  /admin_set_tournament_vc — restrict tournament hours to one specific VC
  Only hours in that VC count toward tournament standings
"""

import asyncio
import datetime
import json
import math
import os
import random
import time
from pathlib import Path

import discord
import pytz
from discord import app_commands
from discord.ext import commands, tasks
from dotenv import load_dotenv

load_dotenv()

# ══════════════════════════════════════════════════════════
# CONFIGURATION  (set in .env file)
# ══════════════════════════════════════════════════════════
TOKEN = os.getenv("DISCORD_TOKEN", "YOUR_TOKEN_HERE")

WELCOME_CHANNEL_ID  = int(os.getenv("WELCOME_CHANNEL_ID",  "1469292869113352450"))
REPORT_CHANNEL_ID   = int(os.getenv("REPORT_CHANNEL_ID",   "1469294887886389435"))
GENERAL_CHANNEL_ID  = int(os.getenv("GENERAL_CHANNEL_ID",  "1469294887886389435"))
LOUNGE_VC_ID        = int(os.getenv("LOUNGE_VC_ID",        "1469292869113352455"))
SLEEP_VC_ID         = int(os.getenv("SLEEP_VC_ID",         "1475049469752905738"))

INVITE_XP_REWARD    = 50
PREMIUM_INVITE_MIN  = 3
PREMIUM_HOURS_MIN   = 50
PREMIUM_XP_COST     = 1000

IST = pytz.timezone("Asia/Kolkata")

# ── Colours ───────────────────────────────────────────────
C_BLUE    = 0x4A90D9
C_GREEN   = 0x2ECC71
C_GOLD    = 0xF1C40F
C_RED     = 0xE74C3C
C_PURPLE  = 0x9B59B6
C_TEAL    = 0x1ABC9C
C_ORANGE  = 0xE67E22
C_PINK    = 0xFF85A1
C_DARK    = 0x2C2F33
C_PREMIUM = 0xFFD700

# ══════════════════════════════════════════════════════════
# FRAME DEFINITIONS  v5.0  (29 frames, 6 tiers)
# ══════════════════════════════════════════════════════════
# Format: id → (border_chars, label, colour, tier)
# Tiers: standard | cosmic | aesthetic | hero | prestige | secret

PREMIUM_FRAMES = {
    # ── Standard (9) ──────────────────────────────────────
    "gold":       ("✦━━✦━━✦━━✦━━✦",   "✨ Gold Scholar",    C_GOLD,    "standard"),
    "diamond":    ("◈⎯◈⎯◈⎯◈⎯◈⎯◈⎯",   "💎 Diamond Elite",   0x00CFFF,  "standard"),
    "fire":       ("🔥≡═≡🔥≡═≡🔥≡═",   "🔥 Flame Lord",      0xFF4500,  "standard"),
    "sakura":     ("🌸·꒷꒦·🌸·꒷꒦·🌸",  "🌸 Sakura Scholar",  C_PINK,    "standard"),
    "crown":      ("♛꧁━━━꧂♛꧁━━━꧂",   "👑 The Crown",       C_PREMIUM, "standard"),
    "ocean":      ("≈〰≈〰≈〰≈〰≈〰≈",  "🌊 Deep Focus",      0x0077BE,  "standard"),
    "frost":      ("❄·❅·❄·❅·❄·❅·❄",   "❄️ Ice Cold",        0xADD8E6,  "standard"),
    "forest":     ("⊱✿⊰⊱✿⊰⊱✿⊰⊱✿",    "🌿 Forest Scholar",  0x228B22,  "standard"),
    "neon":       ("▐║▐║▐║▐║▐║▐║",    "💡 Neon Grinder",    0x39FF14,  "standard"),
    # ── Cosmic (6) ────────────────────────────────────────
    "space":      ("⋆｡°✩˚⋆｡°✩˚⋆｡°",  "🌌 Space Cadet",     0x2C1654,  "cosmic"),
    "galaxy":     ("✦˚⋆｡✧˚✦˚⋆｡✧˚✦",  "🌠 Galaxy Brain",    0x4B0082,  "cosmic"),
    "nebula":     ("◌⊹◌⊹◌⊹◌⊹◌⊹◌",    "🔭 Nebula Scholar",  0x9400D3,  "cosmic"),
    "aurora":     ("≋≈≋≈≋≈≋≈≋≈≋≈≋",   "🌌 Aurora",          0x00FFCC,  "cosmic"),
    "meteor":     ("۞»«●»«۞»«●»«۞",   "☄️ Meteor Grinder",  0xFF8C00,  "cosmic"),
    "stardust":   ("·˚꙳·˚꙳·˚꙳·˚꙳·",  "💫 Stardust",        0xE8E8FF,  "cosmic"),
    # ── Aesthetic (5) ─────────────────────────────────────
    "cyberpunk":  ("░▒▓█▓▒░▒▓█▓▒░",   "🤖 Cyberpunk",       0xFFE600,  "aesthetic"),
    "vaporwave":  ("╔╦═╦╗╔╦═╦╗╔╦═",   "🎵 Vaporwave",       0xFF6EC7,  "aesthetic"),
    "matrix":     ("▓01▓01▓01▓01▓",   "💻 In The Matrix",   0x00FF41,  "aesthetic"),
    "storm":      ("⚡━━━⚡━━━⚡━━━",   "⛈️ Storm Chaser",    0x1E90FF,  "aesthetic"),
    "obsidian":   ("◆◈◆◈◆◈◆◈◆◈◆◈",   "🖤 Obsidian Elite",  0x1C1C1C,  "aesthetic"),
    # ── Hero (4) — superhero frames ───────────────────────
    "spiderman":  ("🕷️╬═╬═╬═╬═╬🕷️",  "🕷️ Spider-Scholar",  0xCC0000,  "hero"),
    "venom":      ("◼▓▀▓◼▓▀▓◼▓▀▓◼",  "🖤 We Are Venom",    0x1A0A2E,  "hero"),
    "ironman":    ("◆▶━━◆▶━━◆▶━━◆",  "⚙️ Iron Genius",     0xFF1744,  "hero"),
    "batman":     ("🦇◤━━◢🦇◤━━◢🦇",  "🦇 Dark Scholar",    0x2C2F3F,  "hero"),
    # ── Prestige (2) — tournament winners only ────────────
    "champion":   ("🏆꧁══════꧂🏆",    "🏆 The Champion",    0xFFD700,  "prestige"),
    "legendary":  ("⚜️━━━⚜️━━━⚜️━━",  "⚜️ Legendary",       0x7B2FBE,  "prestige"),
    # ── Secret (4) — milestone unlocks ────────────────────
    "shadow":     ("▓░▓░▓░▓░▓░▓░▓",   "🌑 Shadow Scholar",  0x2C2C2C,  "secret"),
    "celestial":  ("✧･ﾟ✧･ﾟ✧･ﾟ✧･ﾟ",  "✨ Celestial Being",  0xFFF8DC,  "secret"),
    "void":       ("▪▸▾▸▪▸▾▸▪▸▾▸▪",  "🌀 The Void",        0x000033,  "secret"),
    "transcendent":("💠━━━💠━━━💠━━",  "💠 Transcendent",    0x00BFFF,  "secret"),
}
DEFAULT_FRAME = "gold"

# Secret frame unlock conditions (checked in check_and_award_badges)
SECRET_FRAME_UNLOCKS = {
    "shadow":       ("hours",       500),   # 500 total hours
    "celestial":    ("streak",      100),   # 100-day streak
    "void":         ("admin",       0),     # admin grant only
    "transcendent": ("tourn_wins",  3),     # win 3 tournaments
}
PRESTIGE_FRAMES = {"champion", "legendary"}
SECRET_FRAMES   = set(SECRET_FRAME_UNLOCKS.keys())

def tier_label(tier: str) -> str:
    return {"standard": "⭐ Standard", "cosmic": "🌌 Cosmic",
            "aesthetic": "🎨 Aesthetic", "hero": "🦸 Hero",
            "prestige": "🏆 Prestige", "secret": "🔮 Secret"}.get(tier, tier)

# ══════════════════════════════════════════════════════════
# BOT SETUP
# ══════════════════════════════════════════════════════════
intents = discord.Intents.default()
intents.message_content = True
intents.members         = True
intents.guilds          = True
intents.voice_states    = True

bot = commands.Bot(command_prefix="!", intents=intents)

# ══════════════════════════════════════════════════════════
# PERSISTENCE
# ══════════════════════════════════════════════════════════
DATA_DIR = Path("data")
DATA_DIR.mkdir(exist_ok=True)

F_STUDY         = DATA_DIR / "study.json"
F_STREAK        = DATA_DIR / "streaks.json"
F_XP            = DATA_DIR / "xp.json"
F_BADGES        = DATA_DIR / "badges.json"
F_QUESTS        = DATA_DIR / "quests.json"
F_REMINDERS     = DATA_DIR / "reminders.json"
F_MILESTONE     = DATA_DIR / "milestones.json"
F_REPORT        = DATA_DIR / "report.json"
F_INVITES       = DATA_DIR / "invites.json"
F_PREMIUM       = DATA_DIR / "premium.json"
F_ALARMS        = DATA_DIR / "alarms.json"
F_SETTINGS      = DATA_DIR / "settings.json"
F_INVITE_PRAISE = DATA_DIR / "invite_praise.json"
F_FEED          = DATA_DIR / "feed.json"
F_TOURNAMENTS   = DATA_DIR / "tournaments.json"
F_TEMP_PREMIUM  = DATA_DIR / "temp_premium.json"
F_GIFT_LOG      = DATA_DIR / "gift_log.json"
F_UNLOCKED_FRAMES = DATA_DIR / "unlocked_frames.json"

study_data = streak_data = xp_data = badges_data = {}
quests_data = reminders_data = milestone_data = report_data = {}
invites_data = premium_data = alarms_data = settings_data = {}
invite_praise_data = feed_data = tournaments_data = {}
temp_premium_data = gift_log_data = unlocked_frames_data = {}

# In-memory gaming VC tracker — no persistence needed (VCs get deleted)
# guild_id (int) → set of channel IDs (int)
_gaming_vcs: dict = {}

GAMING_CATEGORY_ID = 1472522441346514974

def _load(p):
    if Path(p).exists():
        try: return json.loads(Path(p).read_text("utf-8"))
        except: pass
    return {}

def _save(p, d):
    Path(p).write_text(json.dumps(d, indent=2, default=str), "utf-8")

def load_all():
    global study_data, streak_data, xp_data, badges_data
    global quests_data, reminders_data, milestone_data, report_data
    global invites_data, premium_data, alarms_data, settings_data
    global invite_praise_data, feed_data, tournaments_data
    global temp_premium_data, gift_log_data, unlocked_frames_data
    study_data           = _load(F_STUDY)
    streak_data          = _load(F_STREAK)
    xp_data              = _load(F_XP)
    badges_data          = _load(F_BADGES)
    quests_data          = _load(F_QUESTS)
    reminders_data       = _load(F_REMINDERS)
    milestone_data       = _load(F_MILESTONE)
    report_data          = _load(F_REPORT)
    invites_data         = _load(F_INVITES)
    premium_data         = _load(F_PREMIUM)
    alarms_data          = _load(F_ALARMS)
    settings_data        = _load(F_SETTINGS)
    invite_praise_data   = _load(F_INVITE_PRAISE)
    feed_data            = _load(F_FEED)
    tournaments_data     = _load(F_TOURNAMENTS)
    temp_premium_data    = _load(F_TEMP_PREMIUM)
    gift_log_data        = _load(F_GIFT_LOG)
    unlocked_frames_data = _load(F_UNLOCKED_FRAMES)

def mk(gid, uid):  return f"{gid}:{uid}"
def now_ts():      return time.time()
def today_str():   return datetime.date.today().isoformat()
def fmt_dur(secs):
    s = int(secs)
    h, rem = divmod(s, 3600)
    m, s   = divmod(rem, 60)
    if h: return f"{h}h {m}m"
    if m: return f"{m}m {s}s"
    return f"{s}s"

def save_study():           _save(F_STUDY,           study_data)
def save_streak():          _save(F_STREAK,          streak_data)
def save_xp():              _save(F_XP,              xp_data)
def save_badges():          _save(F_BADGES,          badges_data)
def save_quests():          _save(F_QUESTS,          quests_data)
def save_reminders():       _save(F_REMINDERS,       reminders_data)
def save_milestone():       _save(F_MILESTONE,       milestone_data)
def save_report():          _save(F_REPORT,          report_data)
def save_invites():         _save(F_INVITES,         invites_data)
def save_premium():         _save(F_PREMIUM,         premium_data)
def save_alarms():          _save(F_ALARMS,          alarms_data)
def save_settings():        _save(F_SETTINGS,        settings_data)
def save_invite_praise():   _save(F_INVITE_PRAISE,   invite_praise_data)
def save_feed():            _save(F_FEED,            feed_data)
def save_tournaments():     _save(F_TOURNAMENTS,     tournaments_data)
def save_temp_premium():    _save(F_TEMP_PREMIUM,    temp_premium_data)
def save_gift_log():        _save(F_GIFT_LOG,        gift_log_data)
def save_unlocked_frames(): _save(F_UNLOCKED_FRAMES, unlocked_frames_data)

# ══════════════════════════════════════════════════════════
# USER SETTINGS
# ══════════════════════════════════════════════════════════
DEFAULT_SETTINGS = {
    "dm_report":   True,
    "dm_session":  True,
    "dm_reminder": True,
    "dm_welcome":  True,
    "dm_invite":   True,
}

def get_settings(gid, uid) -> dict:
    s = settings_data.get(mk(gid, uid), {})
    return {k: s.get(k, v) for k, v in DEFAULT_SETTINGS.items()}

def set_setting(gid, uid, key: str, value: bool):
    skey = mk(gid, uid)
    if skey not in settings_data: settings_data[skey] = {}
    settings_data[skey][key] = value
    save_settings()

def dm_enabled(gid, uid, setting: str) -> bool:
    return get_settings(gid, uid).get(setting, True)

# ══════════════════════════════════════════════════════════
# XP & LEVELS
# ══════════════════════════════════════════════════════════
def get_xp(gid, uid) -> int:
    return xp_data.get(mk(gid, uid), 0)

def add_xp(gid, uid, amount: int) -> int:
    if is_premium(gid, uid) and datetime.date.today().weekday() >= 5:
        amount *= 2
    key = mk(gid, uid)
    xp_data[key] = xp_data.get(key, 0) + amount
    save_xp()
    return xp_data[key]

def deduct_xp(gid, uid, amount: int) -> bool:
    key = mk(gid, uid)
    cur = xp_data.get(key, 0)
    if cur < amount: return False
    xp_data[key] = cur - amount
    save_xp()
    return True

def get_level(gid, uid) -> int:
    return max(1, int(math.sqrt(get_xp(gid, uid) / 100)))

def xp_for_next_level(level: int) -> int:
    return ((level + 1) ** 2) * 100

def xp_progress_bar(gid, uid, premium: bool = False) -> str:
    level      = get_level(gid, uid)
    cur_xp     = get_xp(gid, uid)
    cur_floor  = (level ** 2) * 100
    next_floor = xp_for_next_level(level)
    filled     = int(((cur_xp - cur_floor) / max(1, next_floor - cur_floor)) * 12)
    filled     = max(0, min(12, filled))
    if premium: return "▰" * filled + "▱" * (12 - filled)
    return "█" * filled + "░" * (12 - filled)

# ══════════════════════════════════════════════════════════
# PREMIUM SYSTEM  v4.0
# ══════════════════════════════════════════════════════════
def is_premium(gid, uid) -> bool:
    key  = mk(gid, uid)
    data = premium_data.get(key, {})
    if data.get("admin_granted"): return True
    if get_invite_count(gid, uid) >= PREMIUM_INVITE_MIN: return True
    if data.get("hours_purchased"): return True
    # Check temp premium
    temp = temp_premium_data.get(key, {})
    if temp.get("expiry", 0) > now_ts(): return True
    return False

def is_permanent_premium(gid, uid) -> bool:
    key  = mk(gid, uid)
    data = premium_data.get(key, {})
    if data.get("admin_granted"): return True
    if get_invite_count(gid, uid) >= PREMIUM_INVITE_MIN: return True
    if data.get("hours_purchased"): return True
    return False

def get_premium_data(gid, uid) -> dict:
    key = mk(gid, uid)
    temp = temp_premium_data.get(key, {})
    temp_expiry = temp.get("expiry", 0)
    temp_remaining = max(0, temp_expiry - now_ts()) if temp_expiry else 0
    return {
        "is_premium":      is_premium(gid, uid),
        "is_permanent":    is_permanent_premium(gid, uid),
        "invite_count":    get_invite_count(gid, uid),
        "admin_granted":   premium_data.get(key, {}).get("admin_granted", False),
        "hours_purchased": premium_data.get(key, {}).get("hours_purchased", False),
        "custom_title":    premium_data.get(key, {}).get("custom_title", None),
        "frame":           premium_data.get(key, {}).get("frame", DEFAULT_FRAME),
        "temp_remaining":  temp_remaining,
    }

def get_frame(gid, uid) -> tuple:
    if not is_premium(gid, uid): return ("", "", C_PURPLE, "none")
    key      = mk(gid, uid)
    frame_id = premium_data.get(key, {}).get("frame", DEFAULT_FRAME)
    # Check if they can use this frame
    if not can_use_frame(gid, uid, frame_id): frame_id = DEFAULT_FRAME
    f = PREMIUM_FRAMES.get(frame_id, PREMIUM_FRAMES[DEFAULT_FRAME])
    return (f[0], f[1], f[2], f[3])

def can_use_frame(gid, uid, frame_id: str) -> bool:
    if frame_id not in PREMIUM_FRAMES: return False
    tier = PREMIUM_FRAMES[frame_id][3]
    if tier in ("standard", "cosmic", "aesthetic", "hero"): return True
    if tier == "prestige": return frame_id in get_unlocked_frames(gid, uid)
    if tier == "secret":   return frame_id in get_unlocked_frames(gid, uid)
    return False

def get_unlocked_frames(gid, uid) -> set:
    return set(unlocked_frames_data.get(mk(gid, uid), []))

def unlock_frame(gid, uid, frame_id: str):
    key = mk(gid, uid)
    frames = unlocked_frames_data.get(key, [])
    if frame_id not in frames:
        frames.append(frame_id)
        unlocked_frames_data[key] = frames
        save_unlocked_frames()

def set_custom_title(gid, uid, title: str):
    key = mk(gid, uid)
    if key not in premium_data: premium_data[key] = {}
    premium_data[key]["custom_title"] = title
    save_premium()

def set_frame(gid, uid, frame_id: str):
    key = mk(gid, uid)
    if key not in premium_data: premium_data[key] = {}
    premium_data[key]["frame"] = frame_id
    save_premium()

def admin_grant_premium(gid, uid):
    key = mk(gid, uid)
    if key not in premium_data: premium_data[key] = {}
    premium_data[key]["admin_granted"] = True
    save_premium()

def grant_temp_premium(gid, uid, days: int):
    key  = mk(gid, uid)
    temp = temp_premium_data.get(key, {})
    cur_expiry = temp.get("expiry", now_ts())
    if cur_expiry < now_ts(): cur_expiry = now_ts()
    new_expiry = min(cur_expiry + days * 86400, now_ts() + 30 * 86400)
    temp_premium_data[key] = {"expiry": new_expiry}
    save_temp_premium()
    return new_expiry

def purchase_premium_with_hours(gid, uid) -> tuple:
    hours = get_total_hours(gid, uid)
    xp    = get_xp(gid, uid)
    if hours < PREMIUM_HOURS_MIN:
        return False, f"Need {PREMIUM_HOURS_MIN}h total study (you have {hours:.1f}h)"
    if xp < PREMIUM_XP_COST:
        return False, f"Need {PREMIUM_XP_COST:,} XP (you have {xp:,} XP)"
    if not deduct_xp(gid, uid, PREMIUM_XP_COST):
        return False, "Not enough XP"
    key = mk(gid, uid)
    if key not in premium_data: premium_data[key] = {}
    premium_data[key]["hours_purchased"] = True
    save_premium()
    return True, "Premium unlocked!"

# ══════════════════════════════════════════════════════════
# GIFT PREMIUM
# ══════════════════════════════════════════════════════════
def gift_premium(gid, gifter_uid, recipient_uid, days: int = 3) -> tuple:
    if not is_permanent_premium(gid, gifter_uid):
        return False, "You need permanent Premium to gift it."
    if gifter_uid == recipient_uid:
        return False, "You can't gift to yourself."
    # Check recipient 7-day cooldown
    rkey = mk(gid, recipient_uid)
    last_gift = gift_log_data.get(rkey, {}).get("last_received", 0)
    if now_ts() - last_gift < 7 * 86400:
        remaining = int((7 * 86400 - (now_ts() - last_gift)) / 3600)
        return False, f"This person received a gift recently. They can receive again in ~{remaining}h."
    expiry = grant_temp_premium(gid, recipient_uid, days)
    gift_log_data[rkey] = {"last_received": now_ts(), "gifted_by": gifter_uid}
    save_gift_log()
    exp_str = datetime.datetime.fromtimestamp(expiry, tz=IST).strftime("%d %b %Y %I:%M %p IST")
    return True, exp_str

# ══════════════════════════════════════════════════════════
# INVITE SYSTEM  (race-condition fixed)
# ══════════════════════════════════════════════════════════
_cached_invites: dict = {}
_invite_locks:   dict = {}

def get_invite_count(gid, uid) -> int:
    return invites_data.get(mk(gid, uid), {}).get("count", 0)

def get_invite_code(gid, uid) -> str:
    return invites_data.get(mk(gid, uid), {}).get("code", "")

def record_invite(gid, inviter_uid, invitee_uid):
    key  = mk(gid, inviter_uid)
    data = invites_data.get(key, {"count": 0, "invites": [], "code": ""})
    if invitee_uid not in data["invites"]:
        data["invites"].append(invitee_uid)
        data["count"] = len(data["invites"])
        add_xp(gid, inviter_uid, INVITE_XP_REWARD)
    invites_data[key] = data
    save_invites()

async def cache_guild_invites(guild: discord.Guild):
    try:
        invites = await guild.invites()
        _cached_invites[guild.id] = {inv.code: inv.uses for inv in invites}
    except: pass

async def find_inviter(guild: discord.Guild, snapshot_before: dict):
    lock = _invite_locks.setdefault(guild.id, asyncio.Lock())
    async with lock:
        try:
            new_invites = await guild.invites()
            for inv in new_invites:
                if inv.uses > snapshot_before.get(inv.code, 0) and inv.inviter:
                    _cached_invites[guild.id] = {i.code: i.uses for i in new_invites}
                    key  = mk(guild.id, inv.inviter.id)
                    data = invites_data.get(key, {"count": 0, "invites": [], "code": ""})
                    data["code"] = inv.code
                    invites_data[key] = data
                    save_invites()
                    return inv.inviter
            _cached_invites[guild.id] = {i.code: i.uses for i in new_invites}
        except: pass
    return None

# ══════════════════════════════════════════════════════════
# STREAKS
# ══════════════════════════════════════════════════════════
def get_streak(gid, uid) -> int:
    return streak_data.get(mk(gid, uid), {}).get("streak", 0)

def update_streak(gid, uid):
    key   = mk(gid, uid)
    d     = streak_data.get(key, {"streak": 0, "last_date": "", "longest": 0})
    today = today_str()
    yest  = (datetime.date.today() - datetime.timedelta(days=1)).isoformat()
    last  = d.get("last_date", "")
    if last == today:  pass
    elif last == yest: d["streak"] = d.get("streak", 0) + 1
    else:              d["streak"] = 1
    d["last_date"] = today
    d["longest"]   = max(d.get("longest", 0), d["streak"])
    streak_data[key] = d
    save_streak()
    return d["streak"]

def check_streak_broken(gid, uid) -> bool:
    d      = streak_data.get(mk(gid, uid), {})
    last   = d.get("last_date", "")
    today  = today_str()
    yest   = (datetime.date.today() - datetime.timedelta(days=1)).isoformat()
    streak = d.get("streak", 0)
    return streak > 0 and last not in (today, yest)

# ══════════════════════════════════════════════════════════
# STUDY SESSIONS
# ══════════════════════════════════════════════════════════
def get_user_study(gid, uid) -> dict:
    key = mk(gid, uid)
    if key not in study_data:
        study_data[key] = {
            "total_seconds":   0,
            "sessions":        [],
            "active_vc_start": None,
            "weekly_seconds":  {},
            "today_seconds":   0,
            "today_date":      "",
        }
    return study_data[key]

def start_vc_session(gid, uid):
    d = get_user_study(gid, uid)
    d["active_vc_start"] = now_ts()
    save_study()

def end_vc_session(gid, uid) -> int:
    d     = get_user_study(gid, uid)
    start = d.get("active_vc_start")
    if not start: return 0
    duration = int(now_ts() - start)
    d["active_vc_start"] = None
    if duration < 60: save_study(); return 0
    session = {"start": start, "end": now_ts(), "duration": duration, "date": today_str()}
    d["sessions"] = ([session] + d.get("sessions", []))[:50]
    d["total_seconds"] = d.get("total_seconds", 0) + duration
    week_key = datetime.date.today().strftime("%Y-W%W")
    d.setdefault("weekly_seconds", {})[week_key] = d["weekly_seconds"].get(week_key, 0) + duration
    if d.get("today_date") != today_str():
        d["today_seconds"] = 0
        d["today_date"]    = today_str()
    d["today_seconds"] = d.get("today_seconds", 0) + duration
    save_study()
    return duration

def get_total_hours(gid, uid) -> float:
    return get_user_study(gid, uid).get("total_seconds", 0) / 3600

def get_today_seconds(gid, uid) -> int:
    d = get_user_study(gid, uid)
    if d.get("today_date") != today_str(): return 0
    return d.get("today_seconds", 0)

def get_week_seconds(gid, uid) -> int:
    d    = get_user_study(gid, uid)
    week = datetime.date.today().strftime("%Y-W%W")
    return d.get("weekly_seconds", {}).get(week, 0)

def is_in_vc(gid, uid) -> bool:
    return study_data.get(mk(gid, uid), {}).get("active_vc_start") is not None

# ══════════════════════════════════════════════════════════
# PUBLIC FEED
# ══════════════════════════════════════════════════════════
def get_feed_channel(gid) -> int:
    return feed_data.get(str(gid), {}).get("channel_id", 0)

def set_feed_channel(gid, channel_id: int):
    feed_data[str(gid)] = {"channel_id": channel_id}
    save_feed()

async def post_to_feed(guild: discord.Guild, embed: discord.Embed):
    ch_id = get_feed_channel(guild.id)
    if not ch_id: return
    ch = guild.get_channel(ch_id)
    if ch:
        try: await ch.send(embed=embed)
        except: pass

async def feed_encourage(guild, sender: discord.Member, target: discord.Member, message: str):
    prem = is_premium(guild.id, sender.id)
    _, fl, fc, _ = get_frame(guild.id, sender.id)
    embed = discord.Embed(
        title="💬 Encouragement in the Community!",
        description=f"{sender.mention} encouraged {target.mention}\n\n> *\"{message}\"*",
        color=fc if prem else C_PINK,
    )
    embed.set_footer(text=f"Study Bot · /encourage to hype someone up!")
    embed.timestamp = datetime.datetime.utcnow()
    await post_to_feed(guild, embed)

async def feed_milestone(guild, member: discord.Member, hours: float):
    milestones = [10, 50, 100, 250, 500]
    if int(hours) not in milestones: return
    prem = is_premium(guild.id, member.id)
    _, fl, fc, _ = get_frame(guild.id, member.id)
    msgs = {
        10:  ("📖 10 Hours!", "Just hit 10 hours of study! The habit is forming. 🔥"),
        50:  ("📚 50 Hours!", "50 hours of pure dedication. Legendary grind! 💎"),
        100: ("🥇 100 Hours!", "100 HOURS! You're in the Century Club! 👑"),
        250: ("💎 250 Hours!", "250 hours. You're an absolute monster. 🏆"),
        500: ("👑 500 Hours!", "500 HOURS. Literally a study legend. 🌟"),
    }
    title, desc = msgs[int(hours)]
    embed = discord.Embed(
        title=f"🎉 {member.display_name} hit {title}",
        description=f"{member.mention} {desc}",
        color=fc if prem else C_GOLD,
    )
    embed.set_thumbnail(url=member.display_avatar.url)
    embed.set_footer(text="Study Bot · Keep grinding!")
    embed.timestamp = datetime.datetime.utcnow()
    await post_to_feed(guild, embed)

async def feed_badge(guild, member: discord.Member, emoji: str, name: str, desc: str):
    prem = is_premium(guild.id, member.id)
    _, fl, fc, _ = get_frame(guild.id, member.id)
    embed = discord.Embed(
        title=f"{emoji} Badge Unlocked!",
        description=f"{member.mention} just earned **{name}**\n*{desc}*",
        color=fc if prem else C_PURPLE,
    )
    embed.set_thumbnail(url=member.display_avatar.url)
    embed.set_footer(text="Study Bot · Earn badges by grinding!")
    embed.timestamp = datetime.datetime.utcnow()
    await post_to_feed(guild, embed)

async def feed_streak(guild, member: discord.Member, streak: int):
    if streak not in (7, 14, 30, 60, 100): return
    prem = is_premium(guild.id, member.id)
    _, fl, fc, _ = get_frame(guild.id, member.id)
    msgs = {
        7:   "One full week streak! Discipline is forming. ⚡",
        14:  "Two weeks straight! This is real dedication. 💫",
        30:  "30-DAY STREAK! You're unstoppable! 🔥",
        60:  "60 days! Two months of consistency. 💎",
        100: "100-DAY STREAK! A living legend walks among us. 👑",
    }
    embed = discord.Embed(
        title=f"🔥 {member.display_name} — {streak} Day Streak!",
        description=f"{member.mention} {msgs[streak]}",
        color=fc if prem else C_ORANGE,
    )
    embed.set_thumbnail(url=member.display_avatar.url)
    embed.set_footer(text="Study Bot · Build your streak!")
    embed.timestamp = datetime.datetime.utcnow()
    await post_to_feed(guild, embed)

# ══════════════════════════════════════════════════════════
# TOURNAMENT SYSTEM
# ══════════════════════════════════════════════════════════
# ══════════════════════════════════════════════════════════
# GAMING VC SYSTEM
# ══════════════════════════════════════════════════════════
def register_gaming_vc(gid: int, channel_id: int):
    _gaming_vcs.setdefault(gid, set()).add(channel_id)

def unregister_gaming_vc(gid: int, channel_id: int):
    if gid in _gaming_vcs:
        _gaming_vcs[gid].discard(channel_id)

def is_gaming_vc(gid: int, channel_id: int) -> bool:
    return channel_id in _gaming_vcs.get(gid, set())

# ══════════════════════════════════════════════════════════
# TOURNAMENT SYSTEM
# ══════════════════════════════════════════════════════════
def get_active_tournament(gid) -> dict:
    return tournaments_data.get(str(gid), {}).get("active", {})

def get_tournament_vc(gid) -> int:
    return tournaments_data.get(str(gid), {}).get("tournament_vc_id", 0)

def set_tournament_vc(gid, vc_id: int):
    if str(gid) not in tournaments_data:
        tournaments_data[str(gid)] = {"active": {}, "history": []}
    tournaments_data[str(gid)]["tournament_vc_id"] = vc_id
    save_tournaments()

def get_tournament_vc_hours(gid, uid) -> float:
    return get_user_study(gid, uid).get("tournament_vc_seconds", 0) / 3600

def add_tournament_vc_seconds(gid, uid, seconds: int):
    d = get_user_study(gid, uid)
    d["tournament_vc_seconds"] = d.get("tournament_vc_seconds", 0) + seconds
    save_study()

def start_tournament(gid, t_type: str, duration_hours: int, xp_prizes: list,
                     admin_uid: int, name: str = "") -> dict:
    end_ts = now_ts() + duration_hours * 3600
    tourn  = {
        "id":         int(now_ts()),
        "type":       t_type,
        "name":       name or f"{t_type.title()} Tournament",
        "start":      now_ts(),
        "end":        end_ts,
        "xp_prizes":  xp_prizes,
        "started_by": admin_uid,
        "teams":      {},
        "snapshots":  {},
        "ended":      False,
    }
    if str(gid) not in tournaments_data:
        tournaments_data[str(gid)] = {"active": {}, "history": []}
    tournaments_data[str(gid)]["active"] = tourn
    save_tournaments()
    return tourn

def end_tournament(gid) -> dict:
    gdata = tournaments_data.get(str(gid), {})
    tourn = gdata.get("active", {})
    if not tourn: return {}
    tourn["ended"] = True
    gdata.setdefault("history", []).append(tourn)
    gdata["active"] = {}
    tournaments_data[str(gid)] = gdata
    save_tournaments()
    return tourn

def get_tournament_standings(gid) -> list:
    tourn = get_active_tournament(gid)
    if not tourn: return []
    all_uids = set()
    for k in study_data:
        if k.startswith(f"{gid}:"):
            try: all_uids.add(int(k.split(":")[1]))
            except: pass
    snapshots    = tourn.get("snapshots", {})
    vc_snapshots = tourn.get("vc_snapshots", {})
    vc_id        = get_tournament_vc(gid)
    entries = []
    for uid in all_uids:
        if vc_id:
            snap  = vc_snapshots.get(str(uid), 0)
            cur   = get_tournament_vc_hours(gid, uid)
        else:
            snap  = snapshots.get(str(uid), 0)
            cur   = get_total_hours(gid, uid)
        gained = max(0, cur - snap)
        entries.append((uid, gained))
    return sorted(entries, key=lambda x: x[1], reverse=True)

def snapshot_tournament(gid):
    tourn = get_active_tournament(gid)
    if not tourn: return
    all_uids = set()
    for k in study_data:
        if k.startswith(f"{gid}:"):
            try: all_uids.add(int(k.split(":")[1]))
            except: pass
    for uid in all_uids:
        tourn["snapshots"][str(uid)]    = get_total_hours(gid, uid)
        tourn.setdefault("vc_snapshots", {})[str(uid)] = get_tournament_vc_hours(gid, uid)
    save_tournaments()

def get_tourn_wins(gid, uid) -> int:
    history = tournaments_data.get(str(gid), {}).get("history", [])
    wins = 0
    for t in history:
        winner_uid = t.get("winner_uid")
        if winner_uid == uid: wins += 1
    return wins

async def finalize_tournament(guild: discord.Guild, tourn: dict):
    gid       = guild.id
    standings = get_tournament_standings(gid)
    xp_prizes = tourn.get("xp_prizes", [500, 300, 150])
    ch        = guild.get_channel(GENERAL_CHANNEL_ID)
    feed_ch   = guild.get_channel(get_feed_channel(gid))

    lines = []
    medals = ["🥇", "🥈", "🥉"]
    for i, (uid, hours) in enumerate(standings[:3]):
        m    = guild.get_member(uid)
        name = m.display_name if m else f"User {uid}"
        xp   = xp_prizes[i] if i < len(xp_prizes) else 0
        lines.append(f"{medals[i]} **{name}** — {hours:.2f}h gained (+{xp} XP)")
        if m:
            add_xp(gid, uid, xp)
            grant_temp_premium(gid, uid, 7)
            if i == 0:
                unlock_frame(gid, uid, "champion")
                tourn["winner_uid"] = uid
                save_tournaments()
                # Check transcendent unlock
                if get_tourn_wins(gid, uid) >= 3:
                    unlock_frame(gid, uid, "transcendent")
                    try:
                        e = discord.Embed(
                            title="💠 Secret Frame Unlocked: Transcendent!",
                            description="You've won 3 tournaments. The **Transcendent** frame is yours.",
                            color=0x00BFFF)
                        await m.send(embed=e)
                    except: pass
            # Award winner badge
            award_badge(gid, uid, "tournament_winner")
            try:
                prize_embed = discord.Embed(
                    title=f"🏆 Tournament Result — {medals[i]} {['1st', '2nd', '3rd'][i]} Place!",
                    description=(
                        f"You placed **{['1st','2nd','3rd'][i]}** in **{tourn['name']}**!\n\n"
                        f"Prizes:\n• **+{xp} XP** added\n• **7-day Premium** granted\n"
                        + ("• 🏆 **Champion frame unlocked!** Use `/set_frame champion`\n" if i == 0 else "")
                    ),
                    color=C_GOLD if i == 0 else C_BLUE,
                )
                await m.send(embed=prize_embed)
            except: pass

    result_embed = discord.Embed(
        title=f"🏆 {tourn['name']} — Final Results!",
        description="\n".join(lines) if lines else "No participants.",
        color=C_GOLD,
    )
    result_embed.set_footer(text="Study Bot · /tournament to see next event")
    result_embed.timestamp = datetime.datetime.utcnow()

    for target_ch in [ch, feed_ch]:
        if target_ch:
            try: await target_ch.send(embed=result_embed)
            except: pass

# ══════════════════════════════════════════════════════════
# BADGES
# ══════════════════════════════════════════════════════════
BADGE_DEFINITIONS = [
    ("first_session",     "🎓", "First Step",           "Logged your first study session",        "sessions",     1),
    ("streak_3",          "🔥", "On Fire",               "3-day study streak",                     "streak",       3),
    ("streak_7",          "⚡", "Week Warrior",          "7-day study streak",                     "streak",       7),
    ("streak_14",         "💫", "Fortnight Scholar",     "14-day study streak",                    "streak",       14),
    ("streak_30",         "🌟", "Monthly Master",        "30-day study streak",                    "streak",       30),
    ("streak_100",        "🌙", "Century Streak",        "100-day study streak",                   "streak",       100),
    ("hours_1",           "📖", "Getting Started",       "1 total hour studied",                   "hours",        1),
    ("hours_10",          "📚", "Dedicated",             "10 total hours studied",                 "hours",        10),
    ("hours_25",          "🏅", "Committed",             "25 total hours studied",                 "hours",        25),
    ("hours_50",          "🥈", "Half Century",          "50 total hours studied",                 "hours",        50),
    ("hours_100",         "🥇", "Century Club",          "100 total hours studied",                "hours",        100),
    ("hours_250",         "💎", "Diamond Scholar",       "250 total hours studied",                "hours",        250),
    ("hours_500",         "👑", "Legendary Studier",     "500 total hours studied",                "hours",        500),
    ("level_5",           "⭐", "Rising Star",           "Reached Level 5",                        "level",        5),
    ("level_10",          "🌙", "Level 10 Scholar",      "Reached Level 10",                       "level",        10),
    ("level_20",          "☀️","Level 20 Elite",         "Reached Level 20",                       "level",        20),
    ("quest_master",      "📋", "Quest Master",          "Completed 50 daily quests",              "quests_done",  50),
    ("first_invite",      "📨", "Recruiter",             "Invited your first friend",              "invites",      1),
    ("invite_5",          "🤝", "Community Builder",     "Invited 5 friends",                      "invites",      5),
    ("invite_10",         "🌐", "Network King",          "Invited 10 friends",                     "invites",      10),
    ("premium_unlock",    "💠", "Premium Scholar",       "Unlocked Premium",                       "premium",      1),
    ("premium_flex",      "✨", "Flexing Hard",          "Changed profile frame",                  "has_frame",    1),
    ("premium_crown",     "♛",  "The Crown",             "Using the Crown frame",                  "crown_frame",  1),
    ("cosmic_explorer",   "🌌", "Cosmic Explorer",       "Equipped a Cosmic tier frame",           "cosmic_frame", 1),
    ("aesthetic_mode",    "🎨", "Aesthetic Mode",        "Equipped an Aesthetic tier frame",       "aesth_frame",  1),
    ("tournament_winner", "🏆", "Tournament Winner",     "Won a study tournament",                 "tourn_win",    1),
    ("secret_hunter",     "🔮", "Secret Hunter",         "Unlocked a Secret tier frame",           "secret_frame", 1),
    ("gifter",            "🎁", "The Gifter",            "Gifted Premium to someone",              "gifted",       1),
]

def get_badges(gid, uid) -> list:
    return badges_data.get(mk(gid, uid), {}).get("earned", [])

def award_badge(gid, uid, badge_id: str) -> bool:
    key     = mk(gid, uid)
    current = badges_data.get(key, {"earned": [], "quests_done": 0})
    if badge_id in current["earned"]: return False
    current["earned"].append(badge_id)
    badges_data[key] = current
    save_badges()
    return True

async def check_and_award_badges(gid, uid, guild: discord.Guild,
                                  post_feed: bool = False) -> list:
    newly_awarded = []
    hours       = get_total_hours(gid, uid)
    streak      = get_streak(gid, uid)
    level       = get_level(gid, uid)
    sessions    = len(get_user_study(gid, uid).get("sessions", []))
    q_done      = badges_data.get(mk(gid, uid), {}).get("quests_done", 0)
    invites     = get_invite_count(gid, uid)
    premium     = 1 if is_premium(gid, uid) else 0
    pdata_raw   = premium_data.get(mk(gid, uid), {})
    cur_frame   = pdata_raw.get("frame", DEFAULT_FRAME)
    has_frame   = 1 if cur_frame != DEFAULT_FRAME else 0
    crown_frame = 1 if cur_frame == "crown" else 0
    cosmic_frame= 1 if (cur_frame in PREMIUM_FRAMES and PREMIUM_FRAMES[cur_frame][3] == "cosmic") else 0
    aesth_frame = 1 if (cur_frame in PREMIUM_FRAMES and PREMIUM_FRAMES[cur_frame][3] == "aesthetic") else 0
    tourn_win   = 1 if get_tourn_wins(gid, uid) >= 1 else 0
    secret_frame= 1 if any(f in get_unlocked_frames(gid, uid) for f in SECRET_FRAMES) else 0
    gifted      = 1 if gift_log_data.get(f"gifted:{mk(gid, uid)}", 0) else 0

    for bid, emoji, name, desc, ctype, threshold in BADGE_DEFINITIONS:
        val = {"sessions": sessions, "streak": streak, "hours": hours,
               "level": level, "quests_done": q_done, "invites": invites,
               "premium": premium, "has_frame": has_frame,
               "crown_frame": crown_frame, "cosmic_frame": cosmic_frame,
               "aesth_frame": aesth_frame, "tourn_win": tourn_win,
               "secret_frame": secret_frame, "gifted": gifted}.get(ctype, 0)
        if val < threshold: continue
        newly = award_badge(gid, uid, bid)
        if newly:
            newly_awarded.append((bid, emoji, name, desc))
            role_id = milestone_data.get(mk(gid, bid))
            if role_id and guild:
                member = guild.get_member(uid)
                role   = guild.get_role(int(role_id))
                if member and role:
                    try: await member.add_roles(role)
                    except: pass
            if post_feed and guild:
                member = guild.get_member(uid)
                if member:
                    await feed_badge(guild, member, emoji, name, desc)

    # Check secret frame unlocks
    member = guild.get_member(uid) if guild else None
    for frame_id, (condition, threshold) in SECRET_FRAME_UNLOCKS.items():
        if frame_id in get_unlocked_frames(gid, uid): continue
        unlock = False
        if condition == "hours"      and hours  >= threshold: unlock = True
        if condition == "streak"     and streak >= threshold: unlock = True
        if condition == "tourn_wins" and get_tourn_wins(gid, uid) >= threshold: unlock = True
        if unlock:
            unlock_frame(gid, uid, frame_id)
            f = PREMIUM_FRAMES[frame_id]
            if member:
                try:
                    e = discord.Embed(
                        title=f"🔮 Secret Frame Unlocked: {f[1]}!",
                        description=f"You've unlocked the secret **{f[1]}** frame!\nUse `/set_frame {frame_id}` to equip it.",
                        color=f[2],
                    )
                    await member.send(embed=e)
                except: pass

    return newly_awarded

# ══════════════════════════════════════════════════════════
# DAILY QUESTS
# ══════════════════════════════════════════════════════════
QUEST_POOL = [
    {"id": "study_30m",    "desc": "Study for 30 minutes in VC",           "type": "study_mins", "target": 30,  "xp": 50},
    {"id": "study_1h",     "desc": "Study for 1 hour in VC",               "type": "study_mins", "target": 60,  "xp": 80},
    {"id": "study_2h",     "desc": "Study for 2 hours in VC",              "type": "study_mins", "target": 120, "xp": 150},
    {"id": "study_3h",     "desc": "Study for 3 hours in VC",              "type": "study_mins", "target": 180, "xp": 200},
    {"id": "one_session",  "desc": "Complete any study session",           "type": "sessions",   "target": 1,   "xp": 30},
    {"id": "two_sessions", "desc": "Complete 2 study sessions",            "type": "sessions",   "target": 2,   "xp": 60},
    {"id": "keep_streak",  "desc": "Maintain your streak today",           "type": "streak_day", "target": 1,   "xp": 40},
    {"id": "early_bird",   "desc": "Start a session before 9 AM IST",     "type": "early_bird", "target": 1,   "xp": 70},
    {"id": "night_owl",    "desc": "Study after 9 PM IST",                "type": "night_owl",  "target": 1,   "xp": 60},
    {"id": "encourage",    "desc": "Encourage a fellow studier",           "type": "encourage",  "target": 1,   "xp": 25},
    {"id": "long_sit",     "desc": "Study in one session for 90 min",     "type": "single_90",  "target": 1,   "xp": 120},
    {"id": "invite_friend","desc": "Invite a friend to the server",        "type": "invite",     "target": 1,   "xp": 60},
]

def get_daily_quests(gid, uid) -> dict:
    key   = mk(gid, uid)
    qdata = quests_data.get(key, {})
    if qdata.get("date") != today_str():
        chosen = random.sample(QUEST_POOL, 3)
        quests_data[key] = {
            "date":   today_str(),
            "quests": [{"id": q["id"], "progress": 0, "done": False} for q in chosen],
            "ids":    [q["id"] for q in chosen],
        }
        save_quests()
    return quests_data[key]

def progress_quest(gid, uid, qtype: str, amount: int = 1) -> list:
    qdata     = get_daily_quests(gid, uid)
    completed = []
    for q in qdata["quests"]:
        if q["done"]: continue
        pool_q = next((x for x in QUEST_POOL if x["id"] == q["id"]), None)
        if not pool_q or pool_q["type"] != qtype: continue
        q["progress"] = min(pool_q["target"], q["progress"] + amount)
        if q["progress"] >= pool_q["target"]:
            q["done"] = True
            add_xp(gid, uid, pool_q["xp"])
            completed.append((pool_q["desc"], pool_q["xp"]))
            bd = badges_data.get(mk(gid, uid), {"earned": [], "quests_done": 0})
            bd["quests_done"] = bd.get("quests_done", 0) + 1
            badges_data[mk(gid, uid)] = bd
            save_badges()
    save_quests()
    return completed

# ══════════════════════════════════════════════════════════
# REMINDERS
# ══════════════════════════════════════════════════════════
def add_reminder(gid, uid, message: str, fire_at: float) -> int:
    key = mk(gid, uid)
    if key not in reminders_data: reminders_data[key] = []
    rid = int(now_ts() * 1000) % 999999
    reminders_data[key].append({"id": rid, "message": message, "fire_at": fire_at, "gid": gid})
    save_reminders()
    return rid

def get_reminders(gid, uid) -> list:
    return reminders_data.get(mk(gid, uid), [])

def clear_reminders(gid, uid):
    reminders_data[mk(gid, uid)] = []
    save_reminders()

# ══════════════════════════════════════════════════════════
# NAP ALARM
# ══════════════════════════════════════════════════════════
def set_alarm(gid, uid, channel_id: int, fire_at: float):
    alarms_data[mk(gid, uid)] = {"fire_at": fire_at, "channel_id": channel_id, "gid": gid}
    save_alarms()

def clear_alarm(gid, uid):
    alarms_data.pop(mk(gid, uid), None)
    save_alarms()

async def discord_wake_up(guild: discord.Guild, member: discord.Member, vc_chan=None):
    wake_messages = [
        "⏰ **WAKE UP! WAKE UP! WAKE UP!**\nYour nap timer just went off! Get back to work! 📚💪",
        "🔔 **TIME TO RISE!** Your alarm is going off!\nClose your eyes any longer and the streak breaks! 🔥",
        "☀️ **NAP'S OVER!** The grind doesn't sleep even if you do!\nGet back in a Study VC NOW! 📖",
    ]
    embed = discord.Embed(
        title="⏰ WAKE UP! YOUR ALARM IS RINGING!",
        description=random.choice(wake_messages),
        color=C_GOLD,
    )
    embed.add_field(name="🕐 What now?", value="Jump into a **Study VC** and get back to work! 🔥")
    embed.set_footer(text="Study Bot · Nap complete — time to grind 💪")
    embed.timestamp = datetime.datetime.utcnow()
    try: await member.send(embed=embed)
    except: pass
    gen_ch = guild.get_channel(GENERAL_CHANNEL_ID)
    if gen_ch:
        for line in [
            f"⏰ {member.mention} **WAKE UP!** Your nap alarm just went off!",
            f"🔔 {member.mention} Seriously, get up! The grind is calling! 📚",
            f"☀️ {member.mention} **Last warning!** Get into a Study VC! 💪🔥",
        ]:
            try: await gen_ch.send(line); await asyncio.sleep(1)
            except: pass
    if member.voice and member.voice.channel:
        lounge = guild.get_channel(LOUNGE_VC_ID)
        if lounge and isinstance(lounge, discord.VoiceChannel):
            try: await member.move_to(lounge)
            except: pass

# ══════════════════════════════════════════════════════════
# DAILY REPORT
# ══════════════════════════════════════════════════════════
def build_report_embed(member, gid, uid, today_secs, streak, broken, level, xp, badges_today):
    hours_today = today_secs / 3600
    prem        = is_premium(gid, uid)
    frame_chars, frame_label, frame_color, frame_tier = get_frame(gid, uid)

    if today_secs == 0:      verdict = "😴 You didn't study today. Tomorrow is a fresh start."; color = C_RED
    elif hours_today < 0.5:  verdict = "📖 A short session is still a session. Keep it alive."; color = C_ORANGE
    elif hours_today < 2:    verdict = "✅ Solid work! Consistency beats intensity.";            color = C_GREEN
    elif hours_today < 4:    verdict = "🔥 Great session! You're putting in serious hours.";    color = C_TEAL
    else:                    verdict = "🏆 Incredible dedication. You're winning the grind.";    color = C_GOLD

    if prem: color = frame_color

    now_ist  = datetime.datetime.now(IST)
    date_str = now_ist.strftime("%A, %d %B %Y")
    prem_tag = f" {frame_label}" if prem else ""
    desc     = f"Hey **{member.display_name}**{prem_tag}\n\n{verdict}"
    if prem and frame_chars: desc = f"{frame_chars}\n{desc}\n{frame_chars}"

    embed = discord.Embed(title=f"📊 Daily Study Report — {date_str}", description=desc, color=color)
    embed.set_thumbnail(url=member.display_avatar.url)
    embed.add_field(name="⏱️ Today",     value=fmt_dur(today_secs) if today_secs > 0 else "No study logged", inline=True)
    embed.add_field(name="📅 This Week", value=f"{get_week_seconds(gid,uid)/3600:.1f}h",                      inline=True)
    embed.add_field(name="📚 All Time",  value=f"{get_total_hours(gid,uid):.1f}h",                            inline=True)

    if broken:         streak_val = f"💔 Streak broken! Was at {streak} days. Start fresh!"
    elif streak == 0:  streak_val = "No streak yet — study today to start one!"
    else:              streak_val = f"🔥 **{streak} day{'s' if streak != 1 else ''}** — keep it going!"
    embed.add_field(name="🔥 Streak", value=streak_val, inline=False)

    bar = xp_progress_bar(gid, uid, prem)
    embed.add_field(name="⭐ Level", value=f"Level **{level}** · `{xp:,}` XP\n`[{bar}]`", inline=False)

    if badges_today:
        embed.add_field(name="🎖️ New Badges!", value="\n".join(f"{e} **{n}**" for _, e, n, _ in badges_today))

    if prem and datetime.date.today().weekday() >= 5:
        embed.add_field(name="💠 Weekend 2× XP Active!", value="You're earning double XP today! 🎉")

    # Premium unlock progress for non-premium
    if not prem:
        hours     = get_total_hours(gid, uid)
        inv_count = get_invite_count(gid, uid)
        hour_bar  = "█" * int(min(hours / PREMIUM_HOURS_MIN, 1) * 10) + "░" * (10 - int(min(hours / PREMIUM_HOURS_MIN, 1) * 10))
        inv_bar   = "█" * min(inv_count, PREMIUM_INVITE_MIN) + "░" * max(0, PREMIUM_INVITE_MIN - inv_count)
        embed.add_field(
            name="💠 Unlock Premium",
            value=(
                f"Path 1 — Invites: `[{inv_bar}]` {inv_count}/{PREMIUM_INVITE_MIN}\n"
                f"Path 2 — Hours: `[{hour_bar}]` {hours:.1f}/{PREMIUM_HOURS_MIN}h + 1,000 XP"
            ),
            inline=False,
        )

    tips = [
        "💡 Start before 10 AM for momentum.",
        "💡 Use `/quests` every morning.",
        "💡 20 minutes beats zero — just start.",
        "💡 `/invite` friends = XP + Premium.",
        "💡 `/settings` to control which DMs you get.",
        "💡 `/progress` for a quick dashboard view.",
        "💡 Premium frames unlock at milestones — keep grinding!",
    ]
    embed.add_field(name="💡 Tip", value=random.choice(tips))
    embed.set_footer(text="Study Bot v4.0 · /settings to turn off this DM")
    embed.timestamp = datetime.datetime.utcnow()
    return embed

# ══════════════════════════════════════════════════════════
# VIEWS
# ══════════════════════════════════════════════════════════

class AlarmView(discord.ui.View):
    def __init__(self, member, vc_channel):
        super().__init__(timeout=120)
        self.member = member
        self.vc_channel = vc_channel

    async def _set(self, interaction: discord.Interaction, minutes: int, label: str):
        await interaction.response.defer()
        fire_at  = now_ts() + minutes * 60
        fire_str = datetime.datetime.fromtimestamp(fire_at, tz=IST).strftime("%I:%M %p IST")
        set_alarm(self.member.guild.id, self.member.id,
                  self.vc_channel.id if self.vc_channel else 0, fire_at)
        embed = discord.Embed(title="😴 Nap Alarm Set!", description=f"Sweet dreams! 🌙\nI'll wake you in **{label}** at **{fire_str}**.", color=C_PURPLE)
        embed.set_footer(text="Study Bot · Nap well, grind harder 💤")
        try: await interaction.followup.send(embed=embed, ephemeral=True)
        except: pass
        self.stop()

    @discord.ui.button(label="5 min",   style=discord.ButtonStyle.primary,  emoji="⏱️")
    async def five_min(self, i, b):     await self._set(i, 5,   "5 minutes")
    @discord.ui.button(label="15 min",  style=discord.ButtonStyle.primary,  emoji="⏰")
    async def fifteen_min(self, i, b):  await self._set(i, 15,  "15 minutes")
    @discord.ui.button(label="1 hour",  style=discord.ButtonStyle.success,  emoji="🕐")
    async def one_hour(self, i, b):     await self._set(i, 60,  "1 hour")
    @discord.ui.button(label="4 hours", style=discord.ButtonStyle.success,  emoji="🕓")
    async def four_hours(self, i, b):   await self._set(i, 240, "4 hours")
    @discord.ui.button(label="Cancel",  style=discord.ButtonStyle.danger,   emoji="❌")
    async def cancel(self, interaction: discord.Interaction, b):
        await interaction.response.send_message("No alarm set. Rest well! 💤", ephemeral=True)
        self.stop()


class SettingsView(discord.ui.View):
    def __init__(self, gid: int, uid: int):
        super().__init__(timeout=180)
        self.gid = gid
        self.uid = uid

    def _make_embed(self, user) -> discord.Embed:
        s = get_settings(self.gid, self.uid)
        embed = discord.Embed(title="⚙️ Your Notification Settings",
                              description="Toggle which DMs the Study Bot sends you.\nChanges save instantly.",
                              color=C_TEAL)
        embed.set_thumbnail(url=user.display_avatar.url)
        for key, label in [
            ("dm_report",   "📊 Daily Report DM"),
            ("dm_session",  "📚 Session Complete DM"),
            ("dm_reminder", "⏰ Reminder DMs"),
            ("dm_welcome",  "👋 Welcome DM on join"),
            ("dm_invite",   "📨 Invite nudge DM"),
        ]:
            embed.add_field(name=label, value="✅ **ON**" if s[key] else "❌ **OFF**", inline=True)
        embed.set_footer(text="Study Bot v4.0 · Preferences saved permanently")
        return embed

    async def _toggle(self, interaction: discord.Interaction, key: str):
        set_setting(self.gid, self.uid, key, not dm_enabled(self.gid, self.uid, key))
        await interaction.response.edit_message(embed=self._make_embed(interaction.user), view=self)

    @discord.ui.button(label="Toggle Report DM",   style=discord.ButtonStyle.secondary, row=0)
    async def tog_report(self, i, b):   await self._toggle(i, "dm_report")
    @discord.ui.button(label="Toggle Session DM",  style=discord.ButtonStyle.secondary, row=0)
    async def tog_session(self, i, b):  await self._toggle(i, "dm_session")
    @discord.ui.button(label="Toggle Reminder DM", style=discord.ButtonStyle.secondary, row=1)
    async def tog_reminder(self, i, b): await self._toggle(i, "dm_reminder")
    @discord.ui.button(label="Toggle Welcome DM",  style=discord.ButtonStyle.secondary, row=1)
    async def tog_welcome(self, i, b):  await self._toggle(i, "dm_welcome")
    @discord.ui.button(label="Toggle Invite DM",   style=discord.ButtonStyle.secondary, row=2)
    async def tog_invite(self, i, b):   await self._toggle(i, "dm_invite")
    @discord.ui.button(label="Reset All to ON",    style=discord.ButtonStyle.danger,    row=2)
    async def reset_all(self, interaction: discord.Interaction, b):
        for key in DEFAULT_SETTINGS: set_setting(self.gid, self.uid, key, True)
        await interaction.response.edit_message(embed=self._make_embed(interaction.user), view=self)


class FramesView(discord.ui.View):
    """Paginated frame browser with live mock profile preview."""
    FRAME_ORDER = list(PREMIUM_FRAMES.keys())

    def __init__(self, gid: int, uid: int, start_index: int = 0):
        super().__init__(timeout=180)
        self.gid   = gid
        self.uid   = uid
        self.index = start_index

    def _current_frame_id(self) -> str:
        return self.FRAME_ORDER[self.index]

    def _make_embed(self) -> discord.Embed:
        fid  = self._current_frame_id()
        f    = PREMIUM_FRAMES[fid]
        chars, label, color, tier = f
        prem     = is_premium(self.gid, self.uid)
        unlocked = can_use_frame(self.gid, self.uid, fid)
        tier_str = tier_label(tier)

        # Mock profile preview
        mock_xp_bar = "▰▰▰▰▰▰▰▱▱▱▱▱" if prem else "████████░░░░"
        mock_preview = (
            f"{chars}\n"
            f"**Maverick** · {label}\n"
            f"Level **11** · `12,500` XP\n"
            f"`[{mock_xp_bar}]`\n"
            f"🔥 12 days · 📚 145h · 🏅 #1\n"
            f"{chars}"
        ) if chars else f"**{label}** *(no border — clean style)*"

        status = "✅ **Unlocked & Available**" if unlocked else (
            "🔒 **Prestige** — Win a tournament" if tier == "prestige" else
            "🔮 **Secret** — Special milestone required" if tier == "secret" else
            "💠 **Premium Required**"
        )
        hero_note = ""
        if tier == "hero":
            hero_note = "\n🦸 *Hero frame — available to all Premium members!*"

        embed = discord.Embed(
            title=f"🖼️ Frame Preview — {label}",
            description=mock_preview,
            color=color,
        )
        embed.add_field(name="📂 Tier",   value=tier_str + hero_note, inline=True)
        embed.add_field(name="🔑 Status", value=status,               inline=True)
        embed.add_field(name="🔢 Frame",  value=f"`{fid}`",           inline=True)
        embed.set_footer(
            text=f"Frame {self.index + 1} / {len(self.FRAME_ORDER)} · "
                 f"{'Use ✅ Select to equip' if unlocked and prem else 'Unlock to use'}"
        )
        return embed

    @discord.ui.button(label="◀ Prev",  style=discord.ButtonStyle.secondary, row=0)
    async def prev_btn(self, interaction: discord.Interaction, b):
        self.index = (self.index - 1) % len(self.FRAME_ORDER)
        await interaction.response.edit_message(embed=self._make_embed(), view=self)

    @discord.ui.button(label="▶ Next",  style=discord.ButtonStyle.secondary, row=0)
    async def next_btn(self, interaction: discord.Interaction, b):
        self.index = (self.index + 1) % len(self.FRAME_ORDER)
        await interaction.response.edit_message(embed=self._make_embed(), view=self)

    @discord.ui.button(label="✅ Select This Frame", style=discord.ButtonStyle.success, row=1)
    async def select_btn(self, interaction: discord.Interaction, b):
        fid = self._current_frame_id()
        if not is_premium(self.gid, self.uid):
            return await interaction.response.send_message(
                "💠 Premium required! Unlock via `/premium_status`.", ephemeral=True)
        if not can_use_frame(self.gid, self.uid, fid):
            tier = PREMIUM_FRAMES[fid][3]
            msg  = ("🏆 Prestige frame — win a tournament first!" if tier == "prestige"
                    else "🔮 Secret frame — unlock it through a special milestone first!")
            return await interaction.response.send_message(msg, ephemeral=True)
        set_frame(self.gid, self.uid, fid)
        await check_and_award_badges(self.gid, self.uid, interaction.guild)
        f = PREMIUM_FRAMES[fid]
        await interaction.response.send_message(
            f"✅ Frame set to **{f[1]}**!\n{f[0]}\nShows on `/profile`, `/flex`, and your daily report!",
            ephemeral=True)
        self.stop()

    @discord.ui.button(label="❌ Cancel", style=discord.ButtonStyle.danger, row=1)
    async def cancel_btn(self, interaction: discord.Interaction, b):
        await interaction.response.send_message("Frame browser closed.", ephemeral=True)
        self.stop()


class PremiumPurchaseView(discord.ui.View):
    def __init__(self, gid: int, uid: int):
        super().__init__(timeout=60)
        self.gid = gid
        self.uid = uid

    @discord.ui.button(label="💠 Claim Premium — 1,000 XP",
                       style=discord.ButtonStyle.success, emoji="💠")
    async def claim_btn(self, interaction: discord.Interaction, b):
        ok, msg = purchase_premium_with_hours(self.gid, self.uid)
        if ok:
            embed = discord.Embed(
                title="💠 Premium Unlocked!",
                description=(
                    "🎉 **Welcome to Premium!**\n\n"
                    "You earned this through 50 hours of real study.\n\n"
                    "**Your new perks:**\n"
                    "🖼️ `/frames` — Browse 25 frames\n"
                    "✏️ `/set_title` — Custom study motto\n"
                    "⚡ `/flex` — Public show-off card\n"
                    "💰 Double XP every weekend\n"
                    "👑 Crown on all leaderboards\n"
                    "🔮 Unlock Secret frames through milestones\n"
                    "🏆 Win tournaments for Prestige frames"
                ),
                color=C_PREMIUM,
            )
            await interaction.response.send_message(embed=embed, ephemeral=True)
        else:
            await interaction.response.send_message(f"❌ {msg}", ephemeral=True)
        self.stop()

# ══════════════════════════════════════════════════════════
# WELCOME
# ══════════════════════════════════════════════════════════
async def send_welcome(member: discord.Member):
    if not dm_enabled(member.guild.id, member.id, "dm_welcome"): return
    guild = member.guild
    embed = discord.Embed(
        title=f"👋 Welcome to {guild.name}, {member.display_name}!",
        description=(
            "We're a focused study community — happy you joined!\n\n"
            "**Get started:**\n"
            "📺 Join any **Study VC** to auto-track your session\n"
            "📊 `/profile` — see your stats\n"
            "📋 `/quests` — today's challenges\n"
            "⚡ `/progress` — quick dashboard\n"
            "💬 `/encourage @user` — hype someone up\n"
            "📨 `/invite` — invite friends · earn XP + Premium!\n"
            "⚙️ `/settings` — control which DMs you get\n\n"
            "🔥 Build your streak. Earn XP. Unlock badges.\n"
            "*Let's get to work.* 💪"
        ),
        color=C_BLUE,
    )
    embed.set_thumbnail(url=member.display_avatar.url)
    embed.set_footer(text=f"{guild.name} · Study Bot v4.0")
    embed.timestamp = datetime.datetime.utcnow()
    sent = False
    try: await member.send(embed=embed); sent = True
    except discord.Forbidden: pass
    if not sent and WELCOME_CHANNEL_ID:
        ch = guild.get_channel(WELCOME_CHANNEL_ID)
        if ch: await ch.send(content=member.mention, embed=embed)

# ══════════════════════════════════════════════════════════
# BACKGROUND TASKS
# ══════════════════════════════════════════════════════════
@tasks.loop(seconds=30)
async def reminder_check():
    now = now_ts()
    for key, rems in list(reminders_data.items()):
        to_remove = []
        for r in rems:
            if r["fire_at"] <= now:
                try:
                    gid, uid = int(r["gid"]), int(key.split(":")[1])
                    guild    = bot.get_guild(gid)
                    member   = guild.get_member(uid) if guild else None
                    if member and dm_enabled(gid, uid, "dm_reminder"):
                        embed = discord.Embed(title="⏰ Study Reminder", description=r["message"], color=C_BLUE)
                        embed.set_footer(text="Set via /reminder · /settings to manage")
                        await member.send(embed=embed)
                except: pass
                to_remove.append(r["id"])
        reminders_data[key] = [r for r in rems if r["id"] not in to_remove]
    save_reminders()

@reminder_check.before_loop
async def before_reminder(): await bot.wait_until_ready()


@tasks.loop(seconds=30)
async def alarm_check():
    now = now_ts()
    for key, alarm in list(alarms_data.items()):
        if alarm.get("fire_at", 0) <= now:
            try:
                gid    = int(alarm["gid"])
                uid    = int(key.split(":")[1])
                guild  = bot.get_guild(gid)
                if not guild: continue
                member = guild.get_member(uid)
                if not member: continue
                ch_id  = alarm.get("channel_id")
                vc_chan = guild.get_channel(ch_id) if ch_id else None
                await discord_wake_up(guild, member, vc_chan)
            except Exception as e: print(f"[Alarm Error] {key}: {e}")
            finally: clear_alarm(int(alarm["gid"]), int(key.split(":")[1]))

@alarm_check.before_loop
async def before_alarm(): await bot.wait_until_ready()


@tasks.loop(minutes=1)
async def daily_report_task():
    now_ist = datetime.datetime.now(IST)
    if now_ist.hour != 21 or now_ist.minute != 30: return
    for guild in bot.guilds:
        for key in [k for k in study_data if k.startswith(f"{guild.id}:")]:
            if report_data.get(key) == today_str(): continue
            report_data[key] = today_str(); save_report()
            try:
                uid    = int(key.split(":")[1])
                member = guild.get_member(uid)
                if not member or member.bot: continue
                gid        = guild.id
                new_badges = await check_and_award_badges(gid, uid, guild, post_feed=True)
                embed      = build_report_embed(
                    member, gid, uid, get_today_seconds(gid, uid),
                    get_streak(gid, uid), check_streak_broken(gid, uid),
                    get_level(gid, uid), get_xp(gid, uid), new_badges)
                if not dm_enabled(gid, uid, "dm_report"): continue
                sent = False
                try: await member.send(embed=embed); sent = True
                except discord.Forbidden: pass
                if not sent and REPORT_CHANNEL_ID:
                    ch = guild.get_channel(REPORT_CHANNEL_ID)
                    if ch: await ch.send(content=member.mention, embed=embed)
            except Exception as e: print(f"[Report Error] {key}: {e}")

@daily_report_task.before_loop
async def before_report(): await bot.wait_until_ready()


@tasks.loop(hours=1)
async def temp_premium_expiry_check():
    now = now_ts()
    for key, data in list(temp_premium_data.items()):
        expiry = data.get("expiry", 0)
        if 0 < expiry < now:
            # Expired — notify user
            try:
                parts  = key.split(":")
                gid, uid = int(parts[0]), int(parts[1])
                guild  = bot.get_guild(gid)
                member = guild.get_member(uid) if guild else None
                if member:
                    hours     = get_total_hours(gid, uid)
                    inv_count = get_invite_count(gid, uid)
                    embed = discord.Embed(
                        title="⏳ Your Trial Premium Has Expired",
                        description=(
                            "Your temporary Premium has ended.\n\n"
                            "**Lock it in permanently:**\n"
                            f"Path 1 — Invite {PREMIUM_INVITE_MIN} friends: **{inv_count}/{PREMIUM_INVITE_MIN}**\n"
                            f"Path 2 — Reach {PREMIUM_HOURS_MIN}h + 1,000 XP: **{hours:.1f}h** studied\n\n"
                            "Use `/premium_status` to claim when ready!"
                        ),
                        color=C_PURPLE,
                    )
                    await member.send(embed=embed)
            except: pass
            del temp_premium_data[key]
            save_temp_premium()

@temp_premium_expiry_check.before_loop
async def before_expiry(): await bot.wait_until_ready()


@tasks.loop(hours=24)
async def invite_praise_task():
    today = today_str()
    for guild in bot.guilds:
        gid     = guild.id
        all_inv = {
            int(k.split(":")[1]): invites_data[k].get("count", 0)
            for k in invites_data
            if k.startswith(f"{gid}:") and invites_data[k].get("count", 0) > 0
        }
        if not all_inv: continue
        top_uid, top_count = max(all_inv.items(), key=lambda x: x[1])
        invite_praise_data[f"{gid}:pending"] = {"uid": top_uid, "count": top_count, "date": today}
        save_invite_praise()

@invite_praise_task.before_loop
async def before_praise(): await bot.wait_until_ready()


async def maybe_fire_invite_praise(guild: discord.Guild, member: discord.Member):
    gid   = guild.id
    uid   = member.id
    pdata = invite_praise_data.get(f"{gid}:pending", {})
    if not pdata or pdata.get("uid") != uid or pdata.get("date") != today_str(): return
    count                        = pdata.get("count", 0)
    frame_chars, frame_label, fc, _ = get_frame(gid, uid)
    prem                         = is_premium(gid, uid)
    ch = guild.get_channel(GENERAL_CHANNEL_ID)
    if ch:
        body = (
            f"Big shoutout to {member.mention} 🎉\n\n"
            f"They've brought **{count} friend{'s' if count != 1 else ''}** to our study community! 🙌\n\n"
            f"Want bonus XP + **Premium**? Use `/invite` to get your link!"
        )
        if prem and frame_chars: body = f"{frame_chars}\n{body}\n{frame_chars}"
        embed = discord.Embed(title="🏆 Today's Top Recruiter!", description=body,
                              color=fc if prem else C_GOLD)
        embed.set_thumbnail(url=member.display_avatar.url)
        embed.set_footer(text=f"Study Bot v4.0 · {frame_label if prem else 'Invite friends, build the community'}")
        embed.timestamp = datetime.datetime.utcnow()
        try: await ch.send(embed=embed)
        except: pass
    invite_praise_data.pop(f"{gid}:pending", None)
    save_invite_praise()
    progress_quest(gid, uid, "invite", 1)

# ══════════════════════════════════════════════════════════
# VOICE STATE
# ══════════════════════════════════════════════════════════
@bot.event
async def on_voice_state_update(member, before, after):
    if member.bot: return
    gid, uid = member.guild.id, member.id

    if before.channel is None and after.channel is not None:
        # Don't track gaming VCs as study time
        if is_gaming_vc(gid, after.channel.id):
            # Send a "who to add" message in the gaming VC's text chat
            vc_ch = after.channel
            # Find online members not already in a VC (potential party members)
            online_free = [
                m for m in member.guild.members
                if not m.bot
                and m.id != uid
                and m.status != discord.Status.offline
                and (m.voice is None or m.voice.channel is None)
            ]
            friend_lines = "\n".join(
                f"• {m.mention} — `{m.display_name}`"
                for m in online_free[:8]
            ) or "No one seems to be free right now — try pinging in general!"

            embed = discord.Embed(
                title=f"🎮 {member.display_name} entered the room!",
                description=(
                    f"**{member.mention}** just joined. Let's get a squad!\n\n"
                    f"**Friends you can invite right now** (online & free):\n{friend_lines}\n\n"
                    f"Right-click any name → **Invite to Voice Channel** to pull them in!"
                ),
                color=0x5865F2,
            )
            embed.set_thumbnail(url=member.display_avatar.url)
            embed.set_footer(text="🕹️ Gaming Room · Time here is NOT counted as study hours")
            embed.timestamp = datetime.datetime.utcnow()
            try:
                await vc_ch.send(embed=embed)
            except Exception:
                pass
            return

        start_vc_session(gid, uid)

        if after.channel.id == SLEEP_VC_ID:
            view  = AlarmView(member, after.channel)
            embed = discord.Embed(
                title="😴 Heading to the nap zone?",
                description=(
                    f"Hey **{member.display_name}**! You've joined the Sleep VC.\n\n"
                    "**Want me to wake you up?** Pick a timer below! 🔔"
                ),
                color=C_PURPLE,
            )
            embed.set_footer(text="Study Bot · Nap well, grind harder 💤")
            try: await member.send(embed=embed, view=view)
            except discord.Forbidden: pass

        await maybe_fire_invite_praise(member.guild, member)

        nudge_key = f"nudge:{mk(gid, uid)}"
        if (invite_praise_data.get(nudge_key) != today_str()
                and get_invite_count(gid, uid) == 0
                and dm_enabled(gid, uid, "dm_invite")):
            invite_praise_data[nudge_key] = today_str()
            save_invite_praise()
            try:
                embed = discord.Embed(
                    title="📨 Invite a Friend, Earn Rewards!",
                    description=(
                        f"Hey **{member.display_name}**! 👋\n\n"
                        f"Invite friends and earn:\n"
                        f"• **+{INVITE_XP_REWARD} XP** per invite\n"
                        f"• 💠 **Premium** at {PREMIUM_INVITE_MIN} invites\n"
                        f"• Or study **{PREMIUM_HOURS_MIN}h** + spend **1,000 XP**\n\n"
                        f"Use `/invite` to get your link. *(Turn off with `/settings`)*"
                    ),
                    color=C_TEAL,
                )
                await member.send(embed=embed)
            except: pass

    elif before.channel is not None and after.channel is None:
        # Handle gaming VC leave — cleanup if empty, no study tracking
        if is_gaming_vc(gid, before.channel.id):
            ch = member.guild.get_channel(before.channel.id)
            if ch and len(ch.members) == 0:
                unregister_gaming_vc(gid, before.channel.id)
                try: await ch.delete(reason="Gaming room empty — auto-cleanup")
                except: pass
            return

        duration = end_vc_session(gid, uid)
        if duration > 0:
            # Track tournament VC hours if applicable
            tourn_vc_id = get_tournament_vc(gid)
            if tourn_vc_id and before.channel.id == tourn_vc_id and get_active_tournament(gid):
                add_tournament_vc_seconds(gid, uid, duration)
            new_streak = update_streak(gid, uid)
            add_xp(gid, uid, max(1, duration // 60))
            mins      = duration // 60
            completed = []
            completed += progress_quest(gid, uid, "study_mins", mins)
            completed += progress_quest(gid, uid, "sessions",   1)
            completed += progress_quest(gid, uid, "streak_day", 1)
            if datetime.datetime.now(IST).hour < 9:
                completed += progress_quest(gid, uid, "early_bird", 1)
            if datetime.datetime.now(IST).hour >= 21:
                completed += progress_quest(gid, uid, "night_owl", 1)
            if duration >= 5400:
                completed += progress_quest(gid, uid, "single_90", 1)

            new_badges = await check_and_award_badges(gid, uid, member.guild, post_feed=True)

            # Feed: milestones + streaks
            total_h = get_total_hours(gid, uid)
            await feed_milestone(member.guild, member, total_h)
            await feed_streak(member.guild, member, new_streak)

            if (completed or new_badges) and dm_enabled(gid, uid, "dm_session"):
                prem = is_premium(gid, uid)
                frame_chars, frame_label, frame_color, _ = get_frame(gid, uid)
                lines = []
                for qdesc, qxp in completed:
                    lines.append(f"✅ Quest: **{qdesc}** (+{qxp} XP)")
                for _, bemoji, bname, _ in new_badges:
                    lines.append(f"🎖️ Badge: {bemoji} **{bname}**")
                desc = "\n".join(lines) or "Keep it up!"
                if prem and frame_chars: desc = f"{frame_chars}\n{desc}"
                embed = discord.Embed(
                    title=f"📚 Session Complete — {fmt_dur(duration)}",
                    description=desc,
                    color=frame_color if prem else C_GREEN,
                )
                embed.add_field(name="🔥 Streak", value=f"{new_streak} day{'s' if new_streak != 1 else ''}", inline=True)
                embed.add_field(name="⭐ Level",  value=str(get_level(gid, uid)),                             inline=True)
                if prem:
                    embed.add_field(name=f"💠 {frame_label}", value="Premium Scholar 🔥", inline=True)
                embed.set_footer(text="Study Bot v5.0 · /settings to manage DMs")
                try: await member.send(embed=embed)
                except: pass

    elif before.channel is not None and after.channel is not None:
        # Moving between channels — handle gaming VC transitions
        leaving_gaming = is_gaming_vc(gid, before.channel.id)
        joining_gaming = is_gaming_vc(gid, after.channel.id)

        if leaving_gaming and not joining_gaming:
            # Left gaming room → entering study: start study session
            # Check if gaming room is now empty → cleanup
            ch = member.guild.get_channel(before.channel.id)
            if ch and len(ch.members) == 0:
                unregister_gaming_vc(gid, before.channel.id)
                try: await ch.delete(reason="Gaming room empty — auto-cleanup")
                except: pass
            start_vc_session(gid, uid)

        elif not leaving_gaming and joining_gaming:
            # Left study VC → entering gaming room: end study session silently
            duration = end_vc_session(gid, uid)
            if duration > 0:
                tourn_vc_id = get_tournament_vc(gid)
                if tourn_vc_id and before.channel.id == tourn_vc_id and get_active_tournament(gid):
                    add_tournament_vc_seconds(gid, uid, duration)
                add_xp(gid, uid, max(1, duration // 60))
                update_streak(gid, uid)

        elif not leaving_gaming and not joining_gaming:
            # Regular channel switch — treat as continuing study
            pass

# ══════════════════════════════════════════════════════════
# MEMBER JOIN
# ══════════════════════════════════════════════════════════
@bot.event
async def on_member_join(member):
    if member.bot: return
    # Snapshot BEFORE any await — fixes race condition
    snapshot = dict(_cached_invites.get(member.guild.id, {}))
    inviter  = await find_inviter(member.guild, snapshot)
    if inviter and inviter.id != member.id:
        record_invite(member.guild.id, inviter.id, member.id)
        try:
            inv_count = get_invite_count(member.guild.id, inviter.id)
            just_prem = inv_count == PREMIUM_INVITE_MIN
            embed = discord.Embed(
                title="🎉 Your Invite Worked!",
                description=(
                    f"**{member.display_name}** just joined via your invite!\n"
                    f"You earned **+{INVITE_XP_REWARD} XP**! 🎁\n\n"
                    f"Total invites: **{inv_count}** / {PREMIUM_INVITE_MIN} for Premium\n"
                    + (f"\n💠 **PREMIUM UNLOCKED!** Use `/frames` to choose your frame!" if just_prem else "")
                ),
                color=C_PREMIUM if just_prem else C_GREEN,
            )
            await inviter.send(embed=embed)
        except: pass
    await send_welcome(member)
    await cache_guild_invites(member.guild)

# ══════════════════════════════════════════════════════════
# BOT READY
# ══════════════════════════════════════════════════════════
@bot.event
async def on_ready():
    load_all()
    reminder_check.start()
    daily_report_task.start()
    alarm_check.start()
    invite_praise_task.start()
    temp_premium_expiry_check.start()
    for guild in bot.guilds:
        await cache_guild_invites(guild)
    try:    await bot.tree.sync()
    except Exception as e: print("Sync error:", e)
    print(f"📚 Study Bot v5.0 online | {len(bot.guilds)} guild(s) | {len(PREMIUM_FRAMES)} frames")

# ══════════════════════════════════════════════════════════
# SLASH COMMANDS
# ══════════════════════════════════════════════════════════

# ── SETTINGS ─────────────────────────────────────────────
@bot.tree.command(name="settings", description="⚙️ Toggle your Study Bot DM notifications")
async def settings_cmd(interaction: discord.Interaction):
    await interaction.response.defer(ephemeral=True)
    gid, uid = interaction.guild.id, interaction.user.id
    view     = SettingsView(gid, uid)
    embed    = view._make_embed(interaction.user)
    await interaction.followup.send(embed=embed, view=view, ephemeral=True)

# ── PROFILE ───────────────────────────────────────────────
@bot.tree.command(name="profile", description="View your full study profile 📊")
@app_commands.describe(member="View someone else's profile")
async def profile_cmd(interaction: discord.Interaction, member: discord.Member = None):
    await interaction.response.defer()
    target = member or interaction.user
    gid, uid = interaction.guild.id, target.id
    level        = get_level(gid, uid)
    xp           = get_xp(gid, uid)
    streak       = get_streak(gid, uid)
    longest      = streak_data.get(mk(gid, uid), {}).get("longest", 0)
    total_hours  = get_total_hours(gid, uid)
    week_hours   = get_week_seconds(gid, uid) / 3600
    today_secs   = get_today_seconds(gid, uid)
    sessions     = get_user_study(gid, uid).get("sessions", [])
    earned       = get_badges(gid, uid)
    next_lvl_xp  = xp_for_next_level(level)
    in_vc_now    = is_in_vc(gid, uid)
    prem         = is_premium(gid, uid)
    inv_count    = get_invite_count(gid, uid)
    pdata        = get_premium_data(gid, uid)
    custom_title = pdata.get("custom_title")
    frame_chars, frame_label, frame_color, frame_tier = get_frame(gid, uid)
    bar          = xp_progress_bar(gid, uid, prem)

    all_uids = set()
    for k in study_data:
        if k.startswith(f"{gid}:"):
            try: all_uids.add(int(k.split(":")[1]))
            except: pass
    ranking      = sorted(all_uids, key=lambda u: get_total_hours(gid, u), reverse=True)
    rank         = next((i+1 for i, u in enumerate(ranking) if u == uid), "—")
    rank_display = f"#{rank}" + (" 👑" if prem else "")

    embed = discord.Embed(color=frame_color if prem else C_PURPLE)
    if prem and frame_chars:
        embed.set_author(name=f"{frame_label}  ·  {target.display_name}'s Profile",
                         icon_url=target.display_avatar.url)
        top_border = f"{frame_chars}\n"
        bot_border = f"\n{frame_chars}"
    else:
        embed.set_author(name=f"{target.display_name}'s Study Profile",
                         icon_url=target.display_avatar.url)
        top_border = bot_border = ""

    embed.set_thumbnail(url=target.display_avatar.url)
    status_tag  = " 🟢 *Studying now*" if in_vc_now else ""
    motto_line  = f"*\"{custom_title}\"*\n" if custom_title and prem else ""
    prem_badge  = " 💠" if prem else ""

    embed.description = (
        f"{top_border}"
        f"{motto_line}"
        f"**Level {level}**{prem_badge} · `{xp:,}` / `{next_lvl_xp:,}` XP{status_tag}\n"
        f"`[{bar}]`"
        f"{bot_border}"
    )

    embed.add_field(name="📚 Total Hours",  value=f"{total_hours:.1f}h",                          inline=True)
    embed.add_field(name="📅 This Week",    value=f"{week_hours:.1f}h",                           inline=True)
    embed.add_field(name="⏱️ Today",        value=fmt_dur(today_secs) if today_secs else "—",     inline=True)
    embed.add_field(name="🔥 Streak",       value=f"{streak} day{'s' if streak != 1 else ''}",    inline=True)
    embed.add_field(name="🏆 Longest",      value=f"{longest} day{'s' if longest != 1 else ''}",  inline=True)
    embed.add_field(name="🏅 Server Rank",  value=rank_display,                                   inline=True)
    embed.add_field(name="📋 Sessions",     value=f"{len(sessions)} total",                       inline=True)
    embed.add_field(name="📨 Invites",      value=f"{inv_count} friend{'s' if inv_count != 1 else ''}", inline=True)
    if sessions:
        last = sessions[0]
        embed.add_field(name="🕒 Last Session",
                        value=f"{fmt_dur(last['duration'])} on {last['date']}", inline=True)

    # Active tournament position
    tourn = get_active_tournament(gid)
    if tourn:
        standings = get_tournament_standings(gid)
        t_pos = next((i+1 for i, (u, _) in enumerate(standings) if u == uid), None)
        t_hours = next((h for u, h in standings if u == uid), 0)
        embed.add_field(
            name=f"🏆 {tourn.get('name', 'Tournament')}",
            value=f"Rank #{t_pos} · {t_hours:.2f}h gained" if t_pos else "Not ranked yet",
            inline=False,
        )

    if prem:
        temp_rem = pdata.get("temp_remaining", 0)
        perm_tag = "♾️ Permanent" if pdata["is_permanent"] else f"⏳ {int(temp_rem/3600)}h remaining"
        unlocked = get_unlocked_frames(gid, uid)
        embed.add_field(
            name="💠 Premium Perks",
            value=(
                f"Frame: **{frame_label}** ({tier_label(frame_tier)}) · `/frames` to browse\n"
                f"Double XP weekends · 👑 Crown on leaderboards\n"
                f"**{len(unlocked)}** special frames unlocked · Status: {perm_tag}"
            ),
            inline=False,
        )
    else:
        # Show unlock progress
        hour_prog = min(total_hours / PREMIUM_HOURS_MIN, 1)
        inv_prog  = min(inv_count / PREMIUM_INVITE_MIN, 1)
        hour_bar  = "█" * int(hour_prog * 10) + "░" * (10 - int(hour_prog * 10))
        inv_bar   = "█" * min(inv_count, PREMIUM_INVITE_MIN) + "░" * max(0, PREMIUM_INVITE_MIN - inv_count)
        embed.add_field(
            name="💠 Unlock Premium",
            value=(
                f"🔸 Invites: `[{inv_bar}]` {inv_count}/{PREMIUM_INVITE_MIN}\n"
                f"🔸 Hours: `[{hour_bar}]` {total_hours:.1f}/{PREMIUM_HOURS_MIN}h + 1,000 XP\n"
                f"Use `/premium_status` to claim!"
            ),
            inline=False,
        )

    if earned:
        badge_emojis = [next((b[1] for b in BADGE_DEFINITIONS if b[0] == bid), "") for bid in earned[:12]]
        embed.add_field(name=f"🎖️ Badges ({len(earned)})", value="  ".join(badge_emojis), inline=False)
    else:
        embed.add_field(name="🎖️ Badges", value="None yet — keep studying!", inline=False)

    embed.set_footer(text="Study Bot v4.0 · /frames · /flex (Premium) · /progress")
    embed.timestamp = datetime.datetime.utcnow()
    await interaction.followup.send(embed=embed)

# ── PROGRESS ──────────────────────────────────────────────
@bot.tree.command(name="progress", description="⚡ Quick dashboard — all your stats at a glance")
async def progress_cmd(interaction: discord.Interaction):
    await interaction.response.defer(ephemeral=True)
    gid, uid     = interaction.guild.id, interaction.user.id
    prem         = is_premium(gid, uid)
    frame_chars, frame_label, frame_color, _ = get_frame(gid, uid)
    level        = get_level(gid, uid)
    xp           = get_xp(gid, uid)
    streak       = get_streak(gid, uid)
    total_hours  = get_total_hours(gid, uid)
    today_secs   = get_today_seconds(gid, uid)
    week_hours   = get_week_seconds(gid, uid) / 3600
    bar          = xp_progress_bar(gid, uid, prem)
    in_vc        = is_in_vc(gid, uid)
    d            = get_user_study(gid, uid)
    active_start = d.get("active_vc_start")

    # Quest summary
    qdata  = get_daily_quests(gid, uid)
    q_done = sum(1 for q in qdata["quests"] if q["done"])
    q_lines = []
    for q in qdata["quests"]:
        pool_q = next((x for x in QUEST_POOL if x["id"] == q["id"]), None)
        if not pool_q: continue
        pct = min(1.0, q["progress"] / pool_q["target"])
        bar_q = "█" * int(pct * 8) + "░" * (8 - int(pct * 8))
        status = "✅" if q["done"] else f"`[{bar_q}]`"
        q_lines.append(f"{status} {pool_q['desc']}")

    embed = discord.Embed(
        title=f"⚡ {interaction.user.display_name}'s Dashboard",
        color=frame_color if prem else C_BLUE,
    )
    if prem and frame_chars: embed.set_author(name=frame_label, icon_url=interaction.user.display_avatar.url)
    embed.set_thumbnail(url=interaction.user.display_avatar.url)

    if in_vc and active_start:
        embed.description = f"🟢 **Currently studying** — {fmt_dur(int(now_ts() - active_start))} active"
    else:
        embed.description = "⚫ Not in a study VC right now"

    embed.add_field(name="⏱️ Today",    value=fmt_dur(today_secs) if today_secs else "—", inline=True)
    embed.add_field(name="📅 Week",     value=f"{week_hours:.1f}h",                        inline=True)
    embed.add_field(name="📚 Total",    value=f"{total_hours:.1f}h",                       inline=True)
    embed.add_field(name="🔥 Streak",   value=f"{streak} days",                            inline=True)
    embed.add_field(name="⭐ Level",    value=f"{level} · `{xp:,}` XP",                   inline=True)
    embed.add_field(name="📊 XP Bar",   value=f"`[{bar}]`",                               inline=True)
    embed.add_field(name=f"📋 Quests ({q_done}/3)", value="\n".join(q_lines), inline=False)

    # Tournament
    tourn = get_active_tournament(gid)
    if tourn:
        standings = get_tournament_standings(gid)
        t_pos   = next((i+1 for i, (u, _) in enumerate(standings) if u == uid), None)
        t_hours = next((h for u, h in standings if u == uid), 0)
        end_str = datetime.datetime.fromtimestamp(tourn["end"], tz=IST).strftime("%d %b %I:%M %p IST")
        embed.add_field(
            name=f"🏆 {tourn.get('name','Tournament')} — Ends {end_str}",
            value=f"Your rank: **#{t_pos}** · {t_hours:.2f}h gained" if t_pos else "Join the tournament!",
            inline=False,
        )

    embed.set_footer(text="Study Bot v4.0 · /profile for full stats · /quests for details")
    embed.timestamp = datetime.datetime.utcnow()
    await interaction.followup.send(embed=embed, ephemeral=True)

# ── FRAMES ────────────────────────────────────────────────
@bot.tree.command(name="frames", description="🖼️ Browse all profile frames with live preview")
async def frames_cmd(interaction: discord.Interaction):
    await interaction.response.defer(ephemeral=True)
    gid, uid = interaction.guild.id, interaction.user.id
    view     = FramesView(gid, uid)
    await interaction.followup.send(embed=view._make_embed(), view=view, ephemeral=True)

# ── SET FRAME ─────────────────────────────────────────────
@bot.tree.command(name="set_frame", description="💠 Premium: Set your profile frame by ID")
@app_commands.describe(frame="Frame ID (use /frames to browse)")
async def set_frame_cmd(interaction: discord.Interaction, frame: str):
    await interaction.response.defer(ephemeral=True)
    gid, uid = interaction.guild.id, interaction.user.id
    if not is_premium(gid, uid):
        return await interaction.followup.send("💠 Premium only! Use `/premium_status` to unlock.", ephemeral=True)
    frame = frame.lower()
    if frame not in PREMIUM_FRAMES:
        return await interaction.followup.send(
            f"Unknown frame ID. Use `/frames` to browse all {len(PREMIUM_FRAMES)} frames.", ephemeral=True)
    if not can_use_frame(gid, uid, frame):
        tier = PREMIUM_FRAMES[frame][3]
        msg  = ("🏆 Prestige frame — win a tournament to unlock!" if tier == "prestige"
                else "🔮 Secret frame — unlock through a special milestone!")
        return await interaction.followup.send(msg, ephemeral=True)
    set_frame(gid, uid, frame)
    await check_and_award_badges(gid, uid, interaction.guild)
    f = PREMIUM_FRAMES[frame]
    await interaction.followup.send(
        f"✅ Frame set to **{f[1]}** ({tier_label(f[3])})\n{f[0]}\nShows on `/profile`, `/flex`, and your daily report!",
        ephemeral=True)

# ── SET TITLE ─────────────────────────────────────────────
@bot.tree.command(name="set_title", description="💠 Premium: Set a custom study motto on your profile")
@app_commands.describe(title="Your motto (max 60 chars)")
async def set_title_cmd(interaction: discord.Interaction, title: str):
    await interaction.response.defer(ephemeral=True)
    gid, uid = interaction.guild.id, interaction.user.id
    if not is_premium(gid, uid):
        return await interaction.followup.send("💠 Premium only! Use `/premium_status` to unlock.", ephemeral=True)
    if len(title) > 60:
        return await interaction.followup.send("Max 60 characters.", ephemeral=True)
    set_custom_title(gid, uid, title)
    await interaction.followup.send(
        f"✅ Motto set!\n> *\"{title}\"*\n\nShows on `/profile` and `/flex`!", ephemeral=True)

# ── FLEX ──────────────────────────────────────────────────
@bot.tree.command(name="flex", description="💠 Premium: Show off your profile card publicly!")
async def flex_cmd(interaction: discord.Interaction):
    await interaction.response.defer()
    gid, uid = interaction.guild.id, interaction.user.id
    if not is_premium(gid, uid):
        return await interaction.followup.send(
            "💠 `/flex` is **Premium only**! Use `/premium_status` to unlock.", ephemeral=True)
    frame_chars, frame_label, frame_color, frame_tier = get_frame(gid, uid)
    pdata        = get_premium_data(gid, uid)
    custom_title = pdata.get("custom_title")
    level        = get_level(gid, uid)
    xp           = get_xp(gid, uid)
    streak       = get_streak(gid, uid)
    total_hours  = get_total_hours(gid, uid)
    inv_count    = get_invite_count(gid, uid)
    bar          = xp_progress_bar(gid, uid, True)
    earned       = get_badges(gid, uid)
    unlocked_f   = get_unlocked_frames(gid, uid)

    title_str = f"{frame_chars if frame_chars else '💠'} {interaction.user.display_name} is FLEXING {frame_chars if frame_chars else '💠'}"
    embed = discord.Embed(title=title_str, color=frame_color)
    embed.set_thumbnail(url=interaction.user.display_avatar.url)
    if custom_title: embed.description = f"*\"{custom_title}\"*"
    embed.add_field(name="💠 Frame",      value=f"{frame_label}\n{tier_label(frame_tier)}", inline=True)
    embed.add_field(name="⭐ Level",      value=f"**{level}** · {xp:,} XP",                inline=True)
    embed.add_field(name="🔥 Streak",     value=f"**{streak}** days",                       inline=True)
    embed.add_field(name="📚 Hours",      value=f"**{total_hours:.1f}h** studied",           inline=True)
    embed.add_field(name="📨 Invites",    value=f"**{inv_count}** friends brought",          inline=True)
    embed.add_field(name="🎖️ Badges",     value=f"**{len(earned)}** earned",                 inline=True)
    embed.add_field(name="🔮 Frames",     value=f"**{len(unlocked_f)}** special unlocked",   inline=True)
    embed.add_field(name="📊 XP Progress",value=f"`[{bar}]`",                               inline=False)
    if earned:
        badge_emojis = [next((b[1] for b in BADGE_DEFINITIONS if b[0] == bid), "") for bid in earned[:8]]
        embed.add_field(name="Recent Badges", value="  ".join(badge_emojis), inline=False)
    embed.set_footer(text="Study Bot v4.0 · /premium_status to unlock Premium 💠")
    embed.timestamp = datetime.datetime.utcnow()
    await interaction.followup.send(embed=embed)

# ── PREMIUM STATUS ────────────────────────────────────────
@bot.tree.command(name="premium_status", description="View your premium status and unlock paths 💠")
async def premium_status_cmd(interaction: discord.Interaction):
    await interaction.response.defer(ephemeral=True)
    gid, uid = interaction.guild.id, interaction.user.id
    pdata    = get_premium_data(gid, uid)
    prem     = pdata["is_premium"]
    frame_chars, frame_label, frame_color, frame_tier = get_frame(gid, uid)
    hours    = get_total_hours(gid, uid)
    xp       = get_xp(gid, uid)
    inv      = pdata["invite_count"]

    embed = discord.Embed(title="💠 Premium Status", color=frame_color if prem else C_DARK)
    embed.set_thumbnail(url=interaction.user.display_avatar.url)

    if prem:
        temp_rem = pdata.get("temp_remaining", 0)
        perm_tag = "♾️ **Permanent**" if pdata["is_permanent"] else f"⏳ Trial — **{int(temp_rem/3600)}h** remaining"
        embed.description = f"🎉 **You have Premium!** {frame_chars if frame_chars else ''}\nStatus: {perm_tag}"
        unlocked = get_unlocked_frames(gid, uid)
        embed.add_field(name="🎁 Active Perks", value=(
            f"🖼️ **{len(PREMIUM_FRAMES)} frames** across 6 tiers · `/frames` to browse\n"
            f"🦸 **Hero frames**: 🕷️ Spider-Man · 🖤 Venom · ⚙️ Iron Man · 🦇 Batman\n"
            f"✏️ **Custom Motto** · `/set_title`\n"
            f"⚡ **`/flex`** — public show-off card\n"
            f"💰 **Double XP** every Sat & Sun\n"
            f"👑 **Crown** on all leaderboards\n"
            f"📊 **Fancy XP bar** (▰▱) on profile\n"
            f"🔮 **{len(unlocked)} special frames** unlocked (Prestige/Secret)\n"
            f"🏆 **Tournament eligibility** for Champion/Legendary frames\n"
        ), inline=False)
        if pdata["custom_title"]:
            embed.add_field(name="✏️ Motto", value=f'*"{pdata["custom_title"]}"*', inline=False)
        if not pdata["is_permanent"] and temp_rem:
            embed.add_field(
                name="🔒 Lock It In Permanently",
                value=(
                    f"Your trial expires in **{int(temp_rem/3600)}h**!\n"
                    f"Path 1 — Invites: {inv}/{PREMIUM_INVITE_MIN}\n"
                    f"Path 2 — Hours + XP: {hours:.1f}/{PREMIUM_HOURS_MIN}h · {xp:,}/{PREMIUM_XP_COST:,} XP"
                ),
                inline=False,
            )
    else:
        # Show both unlock paths with progress
        hour_prog = min(hours / PREMIUM_HOURS_MIN, 1)
        inv_prog  = min(inv / PREMIUM_INVITE_MIN, 1)
        hour_bar  = "█" * int(hour_prog * 10) + "░" * (10 - int(hour_prog * 10))
        inv_bar   = "█" * min(inv, PREMIUM_INVITE_MIN) + "░" * max(0, PREMIUM_INVITE_MIN - inv)
        eligible  = hours >= PREMIUM_HOURS_MIN and xp >= PREMIUM_XP_COST

        embed.description = "You don't have Premium yet. Choose your path:\n"
        embed.add_field(
            name="📨 Path 1 — Invite Friends",
            value=f"`[{inv_bar}]` **{inv}/{PREMIUM_INVITE_MIN}** friends invited\nUse `/invite` to get your link",
            inline=False,
        )
        embed.add_field(
            name="⏱️ Path 2 — Study Hard",
            value=(
                f"`[{hour_bar}]` **{hours:.1f}/{PREMIUM_HOURS_MIN}h** studied\n"
                f"XP: **{xp:,}/{PREMIUM_XP_COST:,}**\n"
                + ("✅ **Eligible! Click below to claim!**" if eligible else
                   f"Need: {'✅' if hours >= PREMIUM_HOURS_MIN else f'{PREMIUM_HOURS_MIN - hours:.1f}h more'} · "
                   f"{'✅' if xp >= PREMIUM_XP_COST else f'{PREMIUM_XP_COST - xp:,} XP more'}")
            ),
            inline=False,
        )
        embed.add_field(name="🎁 What you'll unlock", value=(
            f"🖼️ **{len(PREMIUM_FRAMES)} frames** across 6 tiers\n"
            f"🦸 **Hero frames**: 🕷️ Spider-Man · 🖤 Venom · ⚙️ Iron Man · 🦇 Batman\n"
            f"✏️ Custom study motto\n⚡ `/flex` card\n"
            f"💰 Double XP weekends\n👑 Crown on leaderboards\n"
            f"🔮 Secret frames via milestones\n🏆 Prestige frames via tournaments"
        ), inline=False)

        if eligible:
            view = PremiumPurchaseView(gid, uid)
            await interaction.followup.send(embed=embed, view=view, ephemeral=True)
            return

    embed.set_footer(text="Study Bot v4.0 · /invite · /frames")
    await interaction.followup.send(embed=embed, ephemeral=True)

# ── GIFT PREMIUM ──────────────────────────────────────────
@bot.tree.command(name="gift_premium", description="💠 Gift 3 days of Premium to someone!")
@app_commands.describe(member="Who to gift Premium to")
async def gift_premium_cmd(interaction: discord.Interaction, member: discord.Member):
    await interaction.response.defer(ephemeral=True)
    gid, uid = interaction.guild.id, interaction.user.id
    ok, result = gift_premium(gid, uid, member.id, days=3)
    if not ok:
        return await interaction.followup.send(f"❌ {result}", ephemeral=True)

    # Notify gifter
    await interaction.followup.send(
        f"🎁 You gifted **3 days of Premium** to **{member.display_name}**!\nExpires: {result}",
        ephemeral=True)

    # Mark gifter badge
    gift_log_data[f"gifted:{mk(gid, uid)}"] = 1
    save_gift_log()
    await check_and_award_badges(gid, uid, interaction.guild)

    # Notify recipient
    frame_chars, frame_label, frame_color, _ = get_frame(gid, uid)
    try:
        embed = discord.Embed(
            title="🎁 You've Been Gifted Premium!",
            description=(
                f"**{interaction.user.display_name}** just gifted you **3 days of Premium** on **{interaction.guild.name}**! 🎉\n\n"
                f"**Your trial expires:** {result}\n\n"
                f"**While it lasts:**\n"
                f"🖼️ `/frames` — Browse 25 frames\n"
                f"✏️ `/set_title` — Set a custom motto\n"
                f"⚡ `/flex` — Public show-off card\n"
                f"💰 Double XP on weekends\n\n"
                f"**Lock it in permanently:**\n"
                f"• Invite {PREMIUM_INVITE_MIN} friends via `/invite`\n"
                f"• Or hit {PREMIUM_HOURS_MIN}h total study + 1,000 XP"
            ),
            color=C_PREMIUM,
        )
        await member.send(embed=embed)
    except: pass

# ── SESSIONS ──────────────────────────────────────────────
@bot.tree.command(name="sessions", description="View your recent study sessions 📋")
@app_commands.describe(member="View someone else's sessions")
async def sessions_cmd(interaction: discord.Interaction, member: discord.Member = None):
    await interaction.response.defer(ephemeral=True)
    target   = member or interaction.user
    gid, uid = interaction.guild.id, target.id
    limit    = 20 if is_premium(gid, uid) else 7
    sessions = get_user_study(gid, uid).get("sessions", [])[:limit]
    if not sessions:
        return await interaction.followup.send("No sessions yet. Join a Study VC!", ephemeral=True)
    _, frame_label, frame_color, _ = get_frame(gid, uid)
    embed = discord.Embed(
        title=f"📋 {target.display_name}'s Sessions" + (f" · {frame_label}" if is_premium(gid, uid) else ""),
        color=frame_color if is_premium(gid, uid) else C_BLUE)
    for i, s in enumerate(sessions, 1):
        embed.add_field(name=f"Session {i} — {s['date']}", value=fmt_dur(s["duration"]), inline=True)
    embed.add_field(name="📚 All-Time", value=f"{get_total_hours(gid, uid):.1f} hours", inline=False)
    embed.set_footer(text="Auto-tracked via Study VC")
    await interaction.followup.send(embed=embed, ephemeral=True)

# ── QUESTS ────────────────────────────────────────────────
@bot.tree.command(name="quests", description="View today's daily quests 📜")
async def quests_cmd(interaction: discord.Interaction):
    await interaction.response.defer(ephemeral=True)
    gid, uid = interaction.guild.id, interaction.user.id
    qdata    = get_daily_quests(gid, uid)
    embed    = discord.Embed(title="📜 Daily Study Quests",
                             description="Complete quests for bonus XP. Resets midnight UTC.",
                             color=C_TEAL)
    for q in qdata["quests"]:
        pool_q = next((x for x in QUEST_POOL if x["id"] == q["id"]), None)
        if not pool_q: continue
        pct    = min(1.0, q["progress"] / pool_q["target"])
        bar    = "█" * int(pct * 10) + "░" * (10 - int(pct * 10))
        status = "✅ **COMPLETE**" if q["done"] else f"`[{bar}]` {q['progress']}/{pool_q['target']}"
        embed.add_field(
            name=f"{'✅' if q['done'] else '📋'} {pool_q['desc']}",
            value=f"{status}\nReward: **+{pool_q['xp']} XP**", inline=False)
    embed.set_footer(text="Join a Study VC — sessions auto-update quest progress!")
    await interaction.followup.send(embed=embed, ephemeral=True)

# ── ENCOURAGE ─────────────────────────────────────────────
@bot.tree.command(name="encourage", description="Send encouragement to a fellow studier 💬")
@app_commands.describe(member="Who to encourage", message="Your personal message")
async def encourage_cmd(interaction: discord.Interaction, member: discord.Member, message: str):
    await interaction.response.defer()
    gid, uid = interaction.guild.id, interaction.user.id
    if member.id == uid:
        return await interaction.followup.send("You can't encourage yourself!", ephemeral=True)
    t_uid    = member.id
    t_streak = get_streak(gid, t_uid)
    t_hours  = get_total_hours(gid, t_uid)
    t_level  = get_level(gid, t_uid)
    t_prem   = is_premium(gid, t_uid)
    _, t_frame_label, t_frame_color, _ = get_frame(gid, t_uid)
    embed = discord.Embed(title="💬 You've Got a Message!", color=t_frame_color if t_prem else C_PINK)
    embed.set_author(name=f"{interaction.user.display_name} sent you encouragement",
                     icon_url=interaction.user.display_avatar.url)
    embed.set_thumbnail(url=member.display_avatar.url)
    embed.description = (f"*{t_frame_label}*\n\n" if t_prem else "") + f"> *\"{message}\"*"
    embed.add_field(name=f"📊 {member.display_name}'s Stats",
                    value=f"🔥 {t_streak} day streak · 📚 {t_hours:.1f}h · ⭐ Level {t_level}", inline=False)
    if t_streak >= 30:   sign_off = "You're a legend. 30+ day streak. 👑"
    elif t_streak >= 14: sign_off = "Two weeks strong! Building something real. 💎"
    elif t_streak >= 7:  sign_off = "One week streak! Real discipline. ⚡"
    elif t_streak >= 3:  sign_off = "3-day streak! The habit is forming. 🔥"
    elif t_streak >= 1:  sign_off = "You started — that's everything. Don't stop. 💪"
    else:                sign_off = "Every expert was once a beginner. Start today. 🌱"
    embed.add_field(name="✨ Remember", value=sign_off, inline=False)
    embed.set_footer(text=f"Study Bot v4.0 · from {interaction.user.display_name}")
    embed.timestamp = datetime.datetime.utcnow()
    await interaction.followup.send(content=member.mention, embed=embed)
    progress_quest(gid, uid, "encourage", 1)
    await feed_encourage(interaction.guild, interaction.user, member, message)

# ── BADGES ────────────────────────────────────────────────
@bot.tree.command(name="badges", description="View all badges and which you've earned 🎖️")
@app_commands.describe(member="View someone else's badges")
async def badges_cmd(interaction: discord.Interaction, member: discord.Member = None):
    await interaction.response.defer(ephemeral=True)
    target   = member or interaction.user
    gid, uid = interaction.guild.id, target.id
    earned   = get_badges(gid, uid)
    prem     = is_premium(gid, uid)
    _, frame_label, frame_color, _ = get_frame(gid, uid)
    embed = discord.Embed(
        title=f"🎖️ {target.display_name}'s Badges" + (f" · {frame_label}" if prem else ""),
        color=frame_color if prem else C_GOLD)
    earned_lines, unearned_lines = [], []
    for bid, emoji, name, desc, _, _ in BADGE_DEFINITIONS:
        if bid in earned: earned_lines.append(f"{emoji} **{name}** — {desc}")
        else:             unearned_lines.append(f"⬜ ~~{name}~~ — {desc}")
    if earned_lines:
        embed.add_field(name=f"✅ Earned ({len(earned_lines)})", value="\n".join(earned_lines), inline=False)
    if unearned_lines:
        embed.add_field(name=f"🔒 Locked ({len(unearned_lines)})", value="\n".join(unearned_lines[:12]), inline=False)
    embed.set_footer(text=f"{len(earned)}/{len(BADGE_DEFINITIONS)} earned")
    await interaction.followup.send(embed=embed, ephemeral=True)

# ── STUDY STATUS ──────────────────────────────────────────
@bot.tree.command(name="study_status", description="Check your current session stats ⏱️")
async def study_status_cmd(interaction: discord.Interaction):
    await interaction.response.defer(ephemeral=True)
    gid, uid     = interaction.guild.id, interaction.user.id
    d            = get_user_study(gid, uid)
    active_start = d.get("active_vc_start")
    today_secs   = get_today_seconds(gid, uid)
    prem         = is_premium(gid, uid)
    _, _, fc, _  = get_frame(gid, uid)
    embed = discord.Embed(title="⏱️ Study Status", color=fc if prem else C_BLUE)
    if active_start:
        embed.description = f"🟢 **Currently studying!** Active for **{fmt_dur(int(now_ts() - active_start))}**"
        embed.color = fc if prem else C_GREEN
    else:
        embed.description = "You're not in a study VC right now."
    embed.add_field(name="📅 Today",     value=fmt_dur(today_secs) if today_secs else "—", inline=True)
    embed.add_field(name="📅 This Week", value=f"{get_week_seconds(gid,uid)/3600:.1f}h",   inline=True)
    embed.add_field(name="📚 All Time",  value=f"{get_total_hours(gid,uid):.1f}h",         inline=True)
    embed.add_field(name="🔥 Streak",    value=f"{get_streak(gid,uid)} day(s)",            inline=True)
    embed.add_field(name="⭐ Level",     value=str(get_level(gid, uid)),                   inline=True)
    if prem: embed.add_field(name="💠 Premium", value="Active ✅", inline=True)
    embed.set_footer(text="Study Bot v4.0 · /settings to manage DMs")
    await interaction.followup.send(embed=embed, ephemeral=True)

# ── REMINDERS ─────────────────────────────────────────────
@bot.tree.command(name="reminder", description="Manage your personal study reminders ⏰")
@app_commands.describe(action="set / list / clear", message="Reminder message", minutes="Minutes from now")
async def reminder_cmd(interaction: discord.Interaction, action: str,
                       message: str = None, minutes: int = None):
    await interaction.response.defer(ephemeral=True)
    gid, uid = interaction.guild.id, interaction.user.id
    action   = action.lower()
    if action == "set":
        if not message or not minutes:
            return await interaction.followup.send("Provide both `message` and `minutes`.", ephemeral=True)
        if not (1 <= minutes <= 1440):
            return await interaction.followup.send("Minutes must be 1–1440.", ephemeral=True)
        fire_at  = now_ts() + minutes * 60
        add_reminder(gid, uid, message, fire_at)
        fire_str = datetime.datetime.fromtimestamp(fire_at, tz=IST).strftime("%I:%M %p IST")
        await interaction.followup.send(f"✅ Reminder set for **{fire_str}**.\n> *{message}*", ephemeral=True)
    elif action == "list":
        rems = get_reminders(gid, uid)
        if not rems:
            return await interaction.followup.send("No active reminders.", ephemeral=True)
        embed = discord.Embed(title="⏰ Your Reminders", color=C_BLUE)
        for r in rems:
            fire_str = datetime.datetime.fromtimestamp(r["fire_at"], tz=IST).strftime("%I:%M %p IST")
            embed.add_field(name=f"ID {r['id']} · {fire_str}", value=r["message"], inline=False)
        await interaction.followup.send(embed=embed, ephemeral=True)
    elif action == "clear":
        clear_reminders(gid, uid)
        await interaction.followup.send("✅ All reminders cleared.", ephemeral=True)
    else:
        await interaction.followup.send("Use `set`, `list`, or `clear`.", ephemeral=True)

# ── LEADERBOARD ───────────────────────────────────────────
@bot.tree.command(name="leaderboard", description="Top studiers leaderboard 🏆")
@app_commands.describe(board="hours / weekly / xp / streak / invites / tournament")
async def leaderboard_cmd(interaction: discord.Interaction, board: str = "hours"):
    await interaction.response.defer()
    gid   = interaction.guild.id
    board = board.lower()
    all_uids = set()
    for k in list(study_data) + list(xp_data):
        if k.startswith(f"{gid}:"):
            try: all_uids.add(int(k.split(":")[1]))
            except: pass

    if board == "tournament":
        standings = get_tournament_standings(gid)
        tourn     = get_active_tournament(gid)
        if not standings or not tourn:
            return await interaction.followup.send("No active tournament!", ephemeral=True)
        top    = standings[:10]
        medals = ["🥇","🥈","🥉"] + ["🏅"] * 7
        lines  = []
        for i, (uid, hours) in enumerate(top):
            m    = interaction.guild.get_member(uid)
            name = m.display_name if m else f"User {uid}"
            prem = is_premium(gid, uid)
            _, fl, _, _ = get_frame(gid, uid)
            crown = f" 👑 *{fl}*" if prem else ""
            lines.append(f"{medals[i]} **{name}**{crown} — {hours:.2f}h gained")
        embed = discord.Embed(
            title=f"🏆 {tourn.get('name','Tournament')} Standings",
            description="\n".join(lines),
            color=C_GOLD)
        end_str = datetime.datetime.fromtimestamp(tourn["end"], tz=IST).strftime("%d %b %I:%M %p IST")
        embed.set_footer(text=f"Ends {end_str} · Study Bot v4.0")
        embed.timestamp = datetime.datetime.utcnow()
        return await interaction.followup.send(embed=embed)

    if board == "weekly":
        entries = sorted(all_uids, key=lambda u: get_week_seconds(gid, u), reverse=True)
        title   = "📅 This Week's Top Studiers"
        def val(u): return f"{get_week_seconds(gid,u)/3600:.1f}h"
    elif board == "xp":
        entries = sorted(all_uids, key=lambda u: get_xp(gid, u), reverse=True)
        title   = "⭐ XP Leaderboard"
        def val(u): return f"Lv.{get_level(gid,u)} · {get_xp(gid,u):,} XP"
    elif board == "streak":
        entries = sorted(all_uids, key=lambda u: get_streak(gid, u), reverse=True)
        title   = "🔥 Streak Leaderboard"
        def val(u): return f"{get_streak(gid,u)} days"
    elif board == "invites":
        entries = sorted(all_uids, key=lambda u: get_invite_count(gid, u), reverse=True)
        title   = "📨 Top Inviters"
        def val(u): return f"{get_invite_count(gid,u)} invite(s)"
    else:
        entries = sorted(all_uids, key=lambda u: get_total_hours(gid, u), reverse=True)
        title   = "📚 All-Time Study Hours"
        def val(u): return f"{get_total_hours(gid,u):.1f}h"

    top = entries[:10]
    if not top: return await interaction.followup.send("No data yet!")
    medals = ["🥇","🥈","🥉"] + ["🏅"] * 7
    lines  = []
    for i, uid in enumerate(top):
        m    = interaction.guild.get_member(uid)
        name = m.display_name if m else f"User {uid}"
        prem = is_premium(gid, uid)
        _, frame_label, _, _ = get_frame(gid, uid)
        crown = f" 👑 *{frame_label}*" if prem else ""
        lines.append(f"{medals[i]} **{name}**{crown} — {val(uid)}")
    embed = discord.Embed(title=title, description="\n".join(lines), color=C_GOLD)
    embed.set_footer(text="Study Bot v4.0 · /leaderboard hours/weekly/xp/streak/invites/tournament")
    embed.timestamp = datetime.datetime.utcnow()
    await interaction.followup.send(embed=embed)

# ── INVITE ────────────────────────────────────────────────
@bot.tree.command(name="invite", description="Get your personal invite link + stats 📨")
async def invite_cmd(interaction: discord.Interaction):
    await interaction.response.defer(ephemeral=True)
    gid, uid = interaction.guild.id, interaction.user.id
    inv_code = get_invite_code(gid, uid)
    link     = None
    if inv_code:
        try:
            invites = await interaction.guild.invites()
            for inv in invites:
                if inv.code == inv_code and inv.inviter and inv.inviter.id == uid:
                    link = inv.url; break
        except: pass
    if not link:
        try:
            channel = (
                interaction.guild.get_channel(GENERAL_CHANNEL_ID)
                or interaction.guild.system_channel
                or next((c for c in interaction.guild.text_channels
                         if c.permissions_for(interaction.guild.me).create_instant_invite), None)
            )
            if channel:
                new_inv  = await channel.create_invite(max_age=0, max_uses=0, unique=True)
                link     = new_inv.url
                inv_code = new_inv.code
                key      = mk(gid, uid)
                data     = invites_data.get(key, {"count": 0, "invites": [], "code": ""})
                data["code"] = inv_code
                invites_data[key] = data
                save_invites()
                await cache_guild_invites(interaction.guild)
        except Exception as e: print(f"[Invite Error] {e}")
    inv_count = get_invite_count(gid, uid)
    prem      = is_premium(gid, uid)
    _, _, fc, _ = get_frame(gid, uid)
    embed = discord.Embed(title="📨 Your Personal Invite Link", color=fc if prem else C_TEAL)
    embed.description = (
        f"🔗 **{link}**\n\nEvery friend who joins = **+{INVITE_XP_REWARD} XP**!" if link
        else "Could not create invite — check bot permissions."
    )
    embed.add_field(name="📊 Invites",   value=f"**{inv_count}** friends",                                   inline=True)
    embed.add_field(name="💠 Premium",   value="✅ Unlocked!" if prem else f"{inv_count}/{PREMIUM_INVITE_MIN}", inline=True)
    embed.add_field(name="💰 XP Earned", value=f"+{inv_count * INVITE_XP_REWARD} XP",                       inline=True)
    embed.add_field(
        name="🎁 Rewards",
        value=(
            f"• **+{INVITE_XP_REWARD} XP** per invite\n"
            f"• 💠 **Premium at {PREMIUM_INVITE_MIN}** — 25 frames, flex, double XP, crown\n"
            f"• 🎖️ Invite badges at 1, 5, 10 invites\n"
            f"• 🏆 Daily shoutout if you're the top inviter!\n"
            f"• Or study **{PREMIUM_HOURS_MIN}h** + 1,000 XP for Path 2"
        ), inline=False)
    embed.set_footer(text="Study Bot v4.0 · Invite friends, unlock Premium forever")
    await interaction.followup.send(embed=embed, ephemeral=True)

# ── TOURNAMENT ────────────────────────────────────────────
@bot.tree.command(name="tournament", description="View the current active tournament 🏆")
async def tournament_cmd(interaction: discord.Interaction):
    await interaction.response.defer(ephemeral=True)
    gid   = interaction.guild.id
    uid   = interaction.user.id
    tourn = get_active_tournament(gid)
    if not tourn:
        return await interaction.followup.send(
            "No active tournament right now.\nAdmins can start one with `/admin_tournament`.", ephemeral=True)

    standings = get_tournament_standings(gid)
    end_str   = datetime.datetime.fromtimestamp(tourn["end"], tz=IST).strftime("%d %b %Y %I:%M %p IST")
    start_str = datetime.datetime.fromtimestamp(tourn["start"], tz=IST).strftime("%d %b %Y")
    time_left = max(0, tourn["end"] - now_ts())
    h_left    = int(time_left // 3600)
    m_left    = int((time_left % 3600) // 60)

    prem     = is_premium(gid, uid)
    _, _, fc, _ = get_frame(gid, uid)

    embed = discord.Embed(
        title=f"🏆 {tourn.get('name', 'Tournament')}",
        description=f"**Type:** {tourn['type'].replace('_',' ').title()}\n**Started:** {start_str}\n**Ends:** {end_str}\n**Time left:** {h_left}h {m_left}m",
        color=fc if prem else C_GOLD,
    )

    medals = ["🥇","🥈","🥉"] + ["🏅"] * 7
    top    = standings[:5]
    lines  = []
    for i, (u, hours) in enumerate(top):
        m    = interaction.guild.get_member(u)
        name = m.display_name if m else f"User {u}"
        marker = " ← YOU" if u == uid else ""
        lines.append(f"{medals[i]} **{name}** — {hours:.2f}h{marker}")

    if lines: embed.add_field(name="📊 Top 5", value="\n".join(lines), inline=False)

    # User position
    t_pos   = next((i+1 for i, (u, _) in enumerate(standings) if u == uid), None)
    t_hours = next((h for u, h in standings if u == uid), 0)
    embed.add_field(
        name="📍 Your Position",
        value=f"Rank **#{t_pos}** · {t_hours:.2f}h gained this tournament" if t_pos else "No hours logged yet — join a study VC!",
        inline=False,
    )

    prizes = tourn.get("xp_prizes", [500, 300, 150])
    embed.add_field(
        name="🎁 Prizes (Top 3)",
        value=f"🥇 +{prizes[0]} XP · 7d Premium · 🏆 Champion frame\n🥈 +{prizes[1]} XP · 7d Premium\n🥉 +{prizes[2]} XP · 7d Premium",
        inline=False,
    )
    tourn_vc_id = get_tournament_vc(gid)
    if tourn_vc_id:
        vc_ch = interaction.guild.get_channel(tourn_vc_id)
        vc_name = vc_ch.name if vc_ch else f"VC #{tourn_vc_id}"
        embed.add_field(
            name="🎯 Tournament VC",
            value=f"Only hours in **{vc_name}** count toward standings!",
            inline=False,
        )
    else:
        embed.add_field(name="🎯 Eligible VCs", value="All study VCs count!", inline=False)
    embed.set_footer(text="Study Bot v5.0 · Study in the tournament VC to earn hours!")
    embed.timestamp = datetime.datetime.utcnow()
    await interaction.followup.send(embed=embed, ephemeral=True)

# ── ALARM ─────────────────────────────────────────────────
@bot.tree.command(name="alarm", description="Set a nap alarm — bot will wake you up 🔔")
async def alarm_cmd(interaction: discord.Interaction):
    await interaction.response.defer(ephemeral=True)
    if not interaction.user.voice or not interaction.user.voice.channel:
        return await interaction.followup.send("You need to be in a Voice Channel!", ephemeral=True)
    vc   = interaction.user.voice.channel
    view = AlarmView(interaction.user, vc)
    embed = discord.Embed(
        title="⏰ Set a Nap Alarm",
        description=f"You're in **{vc.name}**.\nPick your nap duration and I'll wake you up aggressively! 🔔",
        color=C_PURPLE,
    )
    embed.set_footer(text="Study Bot v4.0 · Wake up refreshed, grind harder 💪")
    await interaction.followup.send(embed=embed, view=view, ephemeral=True)

# ── GAMING ROOM ───────────────────────────────────────────
@bot.tree.command(name="gaming", description="🎮 Create a private gaming room (time NOT counted as study)")
async def gaming_cmd(interaction: discord.Interaction):
    await interaction.response.defer(ephemeral=True)
    guild = interaction.guild
    member = interaction.user
    gid = guild.id

    category = guild.get_channel(GAMING_CATEGORY_ID)
    if category is None or not isinstance(category, discord.CategoryChannel):
        return await interaction.followup.send(
            "❌ Gaming category not found. Ask an admin to check the category ID.", ephemeral=True)

    # Permissions: deny everyone, allow this user + bot
    overwrites = {
        guild.default_role: discord.PermissionOverwrite(view_channel=False, connect=False),
        member:             discord.PermissionOverwrite(view_channel=True,  connect=True, speak=True),
        guild.me:           discord.PermissionOverwrite(view_channel=True,  connect=True, move_members=True),
    }

    try:
        vc = await guild.create_voice_channel(
            name=f"🎮 {member.display_name}'s Room",
            category=category,
            overwrites=overwrites,
            reason=f"Gaming room created by {member.display_name}",
        )
    except discord.Forbidden:
        return await interaction.followup.send(
            "❌ Bot lacks **Manage Channels** permission.", ephemeral=True)

    register_gaming_vc(gid, vc.id)

    # Move member into the room if they're in a VC, otherwise just tell them to join
    moved = False
    if member.voice:
        try:
            await member.move_to(vc)
            moved = True
        except: pass

    moved_msg = "✅ You've been moved in." if moved else f"📍 Join **{vc.name}** in the gaming category!"
    embed = discord.Embed(
        title="🎮 Gaming Room Created!",
        description=(
            f"Your private room **{vc.name}** is ready!\n\n"
            f"{moved_msg}\n\n"
            f"⚠️ **Time in this room is NOT counted as study hours.**\n"
            f"The room auto-deletes when everyone leaves."
        ),
        color=0x5865F2,
    )
    embed.add_field(name="🎯 Room", value=vc.mention, inline=True)
    embed.add_field(name="👤 Owner", value=member.mention, inline=True)
    embed.set_footer(text="Study Bot v5.0 · Game on! Room deletes when empty 🕹️")
    embed.timestamp = datetime.datetime.utcnow()
    await interaction.followup.send(embed=embed, ephemeral=True)

# ══════════════════════════════════════════════════════════
# ADMIN COMMANDS
# ══════════════════════════════════════════════════════════
def is_admin(i): return i.user.guild_permissions.administrator

@bot.tree.command(name="admin_givexp", description="Admin: Give XP to a user")
@app_commands.describe(member="Target", amount="XP amount")
async def admin_givexp_cmd(interaction: discord.Interaction, member: discord.Member, amount: int):
    if not is_admin(interaction):
        return await interaction.response.send_message("No permission.", ephemeral=True)
    add_xp(interaction.guild.id, member.id, amount)
    await interaction.response.send_message(
        f"✅ Gave **{amount} XP** to {member.display_name}. "
        f"Total: {get_xp(interaction.guild.id,member.id):,} XP "
        f"(Lv {get_level(interaction.guild.id,member.id)})", ephemeral=True)

@bot.tree.command(name="admin_reset", description="Admin: Reset a user's study data")
@app_commands.describe(member="Target")
async def admin_reset_cmd(interaction: discord.Interaction, member: discord.Member):
    if not is_admin(interaction):
        return await interaction.response.send_message("No permission.", ephemeral=True)
    key = mk(interaction.guild.id, member.id)
    for d, fn in [(study_data, save_study),(streak_data, save_streak),(xp_data, save_xp),
                  (badges_data, save_badges),(quests_data, save_quests)]:
        d.pop(key, None); fn()
    await interaction.response.send_message(f"✅ Reset **{member.display_name}**.", ephemeral=True)

@bot.tree.command(name="admin_grant_premium", description="Admin: Grant permanent Premium to a user")
@app_commands.describe(member="Target")
async def admin_grant_premium_cmd(interaction: discord.Interaction, member: discord.Member):
    if not is_admin(interaction):
        return await interaction.response.send_message("No permission.", ephemeral=True)
    admin_grant_premium(interaction.guild.id, member.id)
    await interaction.response.send_message(f"✅ **{member.display_name}** granted Premium.", ephemeral=True)
    try:
        embed = discord.Embed(
            title="💠 You've Been Granted Premium!",
            description=(
                f"An admin gave you **Premium** on **{interaction.guild.name}**! 🎉\n\n"
                f"`/frames` · `/set_title` · `/flex` · `/premium_status`"
            ),
            color=C_PREMIUM)
        await member.send(embed=embed)
    except: pass

@bot.tree.command(name="admin_unlock_frame", description="Admin: Unlock a specific frame for a user")
@app_commands.describe(member="Target", frame_id="Frame ID to unlock")
async def admin_unlock_frame_cmd(interaction: discord.Interaction, member: discord.Member, frame_id: str):
    if not is_admin(interaction):
        return await interaction.response.send_message("No permission.", ephemeral=True)
    if frame_id not in PREMIUM_FRAMES:
        return await interaction.response.send_message(f"Unknown frame ID: `{frame_id}`", ephemeral=True)
    unlock_frame(interaction.guild.id, member.id, frame_id)
    f = PREMIUM_FRAMES[frame_id]
    await interaction.response.send_message(
        f"✅ Unlocked **{f[1]}** frame for **{member.display_name}**.", ephemeral=True)

@bot.tree.command(name="admin_setmilestone", description="Admin: Assign role when a badge is earned")
@app_commands.describe(badge_id="Badge ID", role="Role to assign")
async def admin_setmilestone_cmd(interaction: discord.Interaction, badge_id: str, role: discord.Role):
    if not is_admin(interaction):
        return await interaction.response.send_message("No permission.", ephemeral=True)
    valid = [b[0] for b in BADGE_DEFINITIONS]
    if badge_id not in valid:
        return await interaction.response.send_message(f"Valid IDs: {', '.join(valid)}", ephemeral=True)
    milestone_data[mk(interaction.guild.id, badge_id)] = role.id
    save_milestone()
    await interaction.response.send_message(f"✅ **{badge_id}** → **{role.name}**", ephemeral=True)

@bot.tree.command(name="admin_setfeed", description="Admin: Set the public study-wins feed channel")
@app_commands.describe(channel="The channel for public feed posts")
async def admin_setfeed_cmd(interaction: discord.Interaction, channel: discord.TextChannel):
    if not is_admin(interaction):
        return await interaction.response.send_message("No permission.", ephemeral=True)
    set_feed_channel(interaction.guild.id, channel.id)
    await interaction.response.send_message(
        f"✅ Public feed set to {channel.mention}!\n"
        f"Will auto-post: encouragements, milestones, badges, streak records, tournament results.",
        ephemeral=True)

@bot.tree.command(name="admin_tournament", description="Admin: Start or end a tournament")
@app_commands.describe(
    action="start / end",
    name="Tournament name",
    t_type="hours_race or team_wars",
    duration_hours="Duration in hours",
    xp_1st="XP for 1st place",
    xp_2nd="XP for 2nd place",
    xp_3rd="XP for 3rd place",
)
async def admin_tournament_cmd(
    interaction: discord.Interaction,
    action: str,
    name: str = "",
    t_type: str = "hours_race",
    duration_hours: int = 168,
    xp_1st: int = 500,
    xp_2nd: int = 300,
    xp_3rd: int = 150,
):
    if not is_admin(interaction):
        return await interaction.response.send_message("No permission.", ephemeral=True)
    await interaction.response.defer(ephemeral=True)
    gid = interaction.guild.id

    if action == "start":
        existing = get_active_tournament(gid)
        if existing and not existing.get("ended"):
            return await interaction.followup.send(
                "A tournament is already running! End it first with `/admin_tournament end`.", ephemeral=True)
        tourn = start_tournament(gid, t_type, duration_hours, [xp_1st, xp_2nd, xp_3rd],
                                 interaction.user.id, name)
        snapshot_tournament(gid)
        end_str = datetime.datetime.fromtimestamp(tourn["end"], tz=IST).strftime("%d %b %Y %I:%M %p IST")
        ch = interaction.guild.get_channel(GENERAL_CHANNEL_ID)
        embed = discord.Embed(
            title=f"🏆 Tournament Started — {tourn['name']}!",
            description=(
                f"**Type:** {t_type.replace('_',' ').title()}\n"
                f"**Duration:** {duration_hours} hours\n"
                f"**Ends:** {end_str}\n\n"
                f"Study in any VC to earn hours. Most hours gained wins!\n\n"
                f"**Prizes:**\n🥇 +{xp_1st} XP · 7-day Premium · 🏆 Champion frame\n"
                f"🥈 +{xp_2nd} XP · 7-day Premium\n🥉 +{xp_3rd} XP · 7-day Premium"
            ),
            color=C_GOLD,
        )
        tourn_vc_id = get_tournament_vc(gid)
        if tourn_vc_id:
            vc_ch = interaction.guild.get_channel(tourn_vc_id)
            vc_name = vc_ch.name if vc_ch else f"VC #{tourn_vc_id}"
            embed.add_field(name="🎯 Tournament VC", value=f"Only hours in **{vc_name}** count!", inline=False)
        embed.set_footer(text=f"Study Bot v5.0 · Started by {interaction.user.display_name}")
        embed.timestamp = datetime.datetime.utcnow()
        if ch: await ch.send(embed=embed)
        await post_to_feed(interaction.guild, embed)
        await interaction.followup.send(f"✅ Tournament **{tourn['name']}** started!", ephemeral=True)

    elif action == "end":
        tourn = get_active_tournament(gid)
        if not tourn:
            return await interaction.followup.send("No active tournament.", ephemeral=True)
        ended = end_tournament(gid)
        await finalize_tournament(interaction.guild, ended)
        await interaction.followup.send("✅ Tournament ended and results posted!", ephemeral=True)

    else:
        await interaction.followup.send("Use `start` or `end`.", ephemeral=True)

@bot.tree.command(name="admin_set_tournament_vc", description="Admin: Lock tournament hours to a specific VC (or clear restriction)")
@app_commands.describe(
    channel="The VC where tournament hours are counted (leave empty to clear restriction)",
)
async def admin_set_tournament_vc_cmd(
    interaction: discord.Interaction,
    channel: discord.VoiceChannel = None,
):
    if not is_admin(interaction):
        return await interaction.response.send_message("No permission.", ephemeral=True)

    gid = interaction.guild.id
    if channel is None:
        set_tournament_vc(gid, 0)
        return await interaction.response.send_message(
            "✅ Tournament VC restriction **cleared**. All VCs count toward tournament hours.",
            ephemeral=True)

    set_tournament_vc(gid, channel.id)
    tourn = get_active_tournament(gid)
    extra = ""
    if tourn and not tourn.get("ended"):
        extra = f"\n\n⚠️ A tournament is already running — only new hours in {channel.mention} will count from now on."
    await interaction.response.send_message(
        f"✅ Tournament VC set to {channel.mention}!\n"
        f"Only hours studied in that channel will count toward tournament standings.{extra}",
        ephemeral=True)

@bot.tree.command(name="admin_announce", description="Admin: Broadcast an announcement")
@app_commands.describe(title="Title", message="Body")
async def admin_announce_cmd(interaction: discord.Interaction, title: str, message: str):
    if not is_admin(interaction):
        return await interaction.response.send_message("No permission.", ephemeral=True)
    embed = discord.Embed(title=f"📣 {title}", description=message, color=C_GOLD)
    embed.set_footer(text=f"Announced by {interaction.user.display_name} · Study Bot v4.0")
    embed.timestamp = datetime.datetime.utcnow()
    await interaction.channel.send(embed=embed)
    await interaction.response.send_message("✅ Sent!", ephemeral=True)

@bot.tree.command(name="admin_sendreport", description="Admin: Manually trigger daily reports now")
async def admin_sendreport_cmd(interaction: discord.Interaction):
    if not is_admin(interaction):
        return await interaction.response.send_message("No permission.", ephemeral=True)
    await interaction.response.send_message("⏳ Sending reports...", ephemeral=True)
    guild, sent = interaction.guild, 0
    for key in [k for k in study_data if k.startswith(f"{guild.id}:")]:
        try:
            uid    = int(key.split(":")[1])
            member = guild.get_member(uid)
            if not member or member.bot: continue
            gid        = guild.id
            new_badges = await check_and_award_badges(gid, uid, guild)
            embed      = build_report_embed(
                member, gid, uid, get_today_seconds(gid, uid),
                get_streak(gid, uid), check_streak_broken(gid, uid),
                get_level(gid, uid), get_xp(gid, uid), new_badges)
            if not dm_enabled(gid, uid, "dm_report"): continue
            try: await member.send(embed=embed); sent += 1
            except discord.Forbidden:
                ch = guild.get_channel(REPORT_CHANNEL_ID)
                if ch: await ch.send(content=member.mention, embed=embed); sent += 1
        except Exception as e: print(f"[Manual Report] {key}: {e}")
    await interaction.followup.send(f"✅ Sent to **{sent}** members.", ephemeral=True)

# ── HELP ──────────────────────────────────────────────────
@bot.tree.command(name="help", description="Show all Study Bot commands 📖")
async def help_cmd(interaction: discord.Interaction):
    await interaction.response.defer(ephemeral=True)
    gid, uid = interaction.guild.id, interaction.user.id
    prem     = is_premium(gid, uid)
    _, frame_label, frame_color, _ = get_frame(gid, uid)
    embed = discord.Embed(
        title="📖 Study Bot v4.0 — Commands",
        description="Sessions auto-tracked when you join/leave any Study VC.",
        color=frame_color if prem else C_BLUE)
    embed.add_field(name="📊 Studying",
                    value="`/study_status` · `/sessions` · `/profile` · `/progress`", inline=False)
    embed.add_field(name="📜 Quests & Badges",    value="`/quests` · `/badges`", inline=False)
    embed.add_field(name="🏆 Leaderboards",
                    value="`/leaderboard` `hours/weekly/xp/streak/invites/tournament`", inline=False)
    embed.add_field(name="🏅 Tournaments",        value="`/tournament` — view standings & prizes", inline=False)
    embed.add_field(name="💬 Social",             value="`/encourage @user <message>`", inline=False)
    embed.add_field(name="📨 Invites & Premium",  value=(
        "`/invite` — your link + stats\n"
        "`/premium_status` — unlock paths + claim\n"
        "`/frames` 💠 — browse all 25 frames with preview\n"
        "`/set_frame <id>` 💠 — equip a frame\n"
        "`/set_title` 💠 — custom study motto\n"
        "`/flex` 💠 — public show-off card\n"
        "`/gift_premium @user` 💠 — gift 3 days\n"), inline=False)
    embed.add_field(name="⏰ Reminders & Alarms",
                    value="`/reminder set/list/clear` · `/alarm`", inline=False)
    embed.add_field(name="⚙️ Settings",           value="`/settings` — toggle all DM notifications", inline=False)
    embed.add_field(name="🎮 Gaming", value="`/gaming` — private room (no study hours tracked)", inline=False)
    embed.add_field(name="🛡️ Admin", value=(
        "`/admin_givexp` · `/admin_reset` · `/admin_grant_premium`\n"
        "`/admin_unlock_frame` · `/admin_setmilestone`\n"
        "`/admin_setfeed` · `/admin_tournament start/end`\n"
        "`/admin_set_tournament_vc` — lock tournament to one VC\n"
        "`/admin_announce` · `/admin_sendreport`\n"
        "`!sync` — owner sync"), inline=False)
    embed.add_field(name="🦸 Hero Frames (all Premium)", value=(
        "🕷️ `spiderman` · 🖤 `venom` · ⚙️ `ironman` · 🦇 `batman`"), inline=False)
    embed.add_field(name="🔮 Secret Frames (milestone unlocks)", value=(
        "🌑 `shadow` — 500 total hours\n"
        "✨ `celestial` — 100-day streak\n"
        "🌀 `void` — admin grant only\n"
        "💠 `transcendent` — win 3 tournaments"), inline=False)
    embed.add_field(name="🏆 Prestige Frames (tournament only)", value=(
        "🏆 `champion` — win any tournament\n"
        "⚜️ `legendary` — win any tournament"), inline=False)
    embed.set_footer(
        text=f"Study Bot v5.0 · {frame_label + ' · ' if prem else ''}"
             f"29 frames · 6 tiers · /premium_status 💠")
    await interaction.followup.send(embed=embed, ephemeral=True)

# ── OWNER SYNC ────────────────────────────────────────────
@bot.command()
@commands.is_owner()
async def sync(ctx):
    await bot.tree.sync(guild=discord.Object(id=ctx.guild.id))
    await bot.tree.sync()
    await ctx.send("✅ Commands synced!")

# ══════════════════════════════════════════════════════════
# RUN
# ══════════════════════════════════════════════════════════
bot.run(TOKEN)
