import os
import re
import json
import time
import asyncio
import requests
from threading import Thread
from flask import Flask

import discord
from discord.ext import commands, tasks
from discord import app_commands, ui
from discord.errors import NotFound

# ==========================================
# HELPER FUNCTIONS
# ==========================================
async def send_private_protocol(leader_user: discord.User, protocol_content: str):
    """Sendet das fertig gestellte Protokoll privat per DM an den Gesprächsleiter."""
    try:
        await leader_user.send(
            f"📋 **Hier ist das Protokoll deiner letzten Sitzung:**\n\n{protocol_content}"
        )
        print("Protokoll erfolgreich privat zugestellt.")
    except discord.Forbidden:
        print("Fehler: Der Gesprächsleiter hat DMs deaktiviert.")


async def send_moderation_log(guild: discord.Guild, action_type: str, roblox_name: str, grund: str, dauer: str, moderator: str, avatar_url: str = None):
    """Sendet Moderations-Einträge zielgerichtet an den festgelegten Kanal (ID: 1527349831444729868)."""
    kanal = guild.get_channel(1527349831444729868)
    if not kanal:
        return
    embed = discord.Embed(
        title=f"🚨 Moderations-Aktion: {action_type}",
        color=discord.Color.red()
    )
    embed.add_field(name="👤 Roblox-Name", value=f"`{roblox_name}`", inline=True)
    embed.add_field(name="📌 Typ", value=f"`{action_type}`", inline=True)
    embed.add_field(name="⏳ Dauer", value=f"`{dauer}`", inline=True)
    embed.add_field(name="📝 Grund", value=grund, inline=False)
    embed.add_field(name="🛡️ Moderator", value=moderator, inline=False)
    if avatar_url:
        embed.set_thumbnail(url=avatar_url)
    embed.set_footer(text="Sirius RP • Moderations-Log")
    await kanal.send(embed=embed)


# ==========================================
# FLASK WEBSERVER FÜR KEEP-ALIVE
# ==========================================
app = Flask('')

@app.route('/', methods=['GET', 'HEAD'])
def home():
    return "Bot ist online!"

def run():
    port = int(os.environ.get("PORT", 8080))
    app.run(host='0.0.0.0', port=port)

def keep_alive():
    t = Thread(target=run)
    t.start()

# Webserver starten
keep_alive()

# ==========================================
# DISCORD BOT INITIALISIERUNG
# ==========================================
intents = discord.Intents.default()
intents.message_content = True
intents.members = True
intents.voice_states = True
intents.reactions = True

bot = commands.Bot(command_prefix='!', intents=intents)

# ==========================================
# KONFIGURATION (IDS & LINKS)
# ==========================================
TEAM_ROLLE_ID = 1527349817708122189

XP_BOOST_LOCK_ROLLE_ID = 1527349817875890356
XP_GIVE_REMOVE_ROLLE_ID = 1527349818031214718
RELOAD_COMMAND_ROLLE_ID = 1527739219907449022

FEEDBACK_PANEL_KANAL_ID = 1527349829942906995
LOG_KANAL_ID = 1532091859285966868
CALL_ADMIN_KANAL_ID = 1532102652790444123
CALL_ADMIN_TEAM_ROLLE_ID = 1532109458157862932
DIZZY_KANAL_ID = 1527349819742355624
ALLOWED_VOICE_CHANNELS = [1527349830228246701, 1527349830228246702]
LEADERBOARD_KANAL_ID = 1532118592177569822
XP_BOOST_ANNOUNCEMENT_KANAL_ID = 1527677485960007680
EINTRAG_PANEL_KANAL_ID = 1532144498317070586
BAN_BOLO_KANAL_ID = 1532144498317070586

# Neue Log-Kanal IDs
DIZZY_LOG_KANAL_ID = 1532348593573199872
XP_LOG_KANAL_ID = 1532348632412721312
BAN_BOLO_LOG_KANAL_ID = 1532348686385025205
CALL_ADMIN_LOG_KANAL_ID = 1532348723705811016
FEEDBACK_REMOVE_LOG_KANAL_ID = 1536669127891226624

# Verify System IDs
VERIFY_KANAL_ID = 1527404574430855340
UNVERIFIED_ROLLE_ID = 1527404452829466735
VERIFIED_ROLLE_ID = 1527349817586483229

# BEWERBUNG SYSTEM KONFIGURATION
ALLOWED_ROLES = [1527349818031214718, 1528123954659590154]
PASS_SCORE = 35
MAX_SCORE = 54

QUESTIONS = [
    {"q": "Welche Regeln sind laut Roblox verboten?", "max": 10},
    {"q": "Was bedeutet die New Life Regel?", "max": 6},
    {"q": "Erkläre what FRP ist.", "max": 2},
    {"q": "Was bedeutet Combat Logging?", "max": 6},
    {"q": "Erkläre what du under RDM verstehst.", "max": 2},
    {"q": "Erkläre what du under Meta Gaming verstehst und what machst du wenn du jemanden erwischt.", "max": 8},
    {"q": "Erkläre what du under VDM verstehst.", "max": 2},
    {"q": "Wie viele Geiseln darfst du maximal nehmen und wie hoch darf das Lösegeld sein?", "max": 6},
    {"q": "Stell dir vor ein Cop stürmt in einer Geiselnahme, obwohl die Geiseln bedroht wurden. Was tust du?", "max": 6},
    {"q": "Was sind unsere Savezonen?", "max": 4},
    {"q": "Was muss man in Savezonen beachten?", "max": 2}
]

# ==========================================
# DATENBANK & SPEICHER (MIT PERSISTENZ)
# ==========================================
DATA_FILE = "bot_database.json"

def load_data():
    if os.path.exists(DATA_FILE):
        try:
            with open(DATA_FILE, "r", encoding="utf-8") as f:
                data = json.load(f)
                xp_raw = data.get("user_xp", {})
                loaded_xp = {int(k): v for k, v in xp_raw.items()}
                
                raw_dizzy = data.get("durchgefuehrte_kontrollen", [])
                loaded_dizzy = {(int(item[0]), int(item[1])) for item in raw_dizzy}

                raw_mod = data.get("moderation_eintraege", {})
                loaded_mod = {k.lower(): v for k, v in raw_mod.items()}

                raw_feedbacks = data.get("team_feedbacks", {})
                loaded_feedbacks = {int(k): v for k, v in raw_feedbacks.items()}

                return loaded_xp, loaded_mod, data.get("active_ban_bolos", []), loaded_dizzy, data.get("time_leaderboard", []), loaded_feedbacks
        except Exception as e:
            print(f"Fehler beim Laden der Datenbank: {e}")
    return {}, {}, [], set(), [], {}

def save_data():
    dizzy_list = [[mod_id, target_id] for mod_id, target_id in durchgefuehrte_kontrollen]
    
    data = {
        "user_xp": user_xp,
        "moderation_eintraege": moderation_eintraege,
        "active_ban_bolos": active_ban_bolos,
        "durchgefuehrte_kontrollen": dizzy_list,
        "time_leaderboard": time_leaderboard,
        "team_feedbacks": team_feedbacks
    }
    try:
        with open(DATA_FILE, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=4)
    except Exception as e:
        print(f"Fehler beim Speichern der Datenbank: {e}")

user_xp, moderation_eintraege, active_ban_bolos, durchgefuehrte_kontrollen, time_leaderboard, team_feedbacks = load_data()

text_cooldowns = {}
fullmute_timers = {}
fullmute_warned = set()
voice_join_times = {}

xp_locks = {}
active_xp_boost = None
leaderboard_message_id = None


def is_team_member(member: discord.Member) -> bool:
    return any(r.id == TEAM_ROLLE_ID for r in member.roles)


def has_role(member: discord.Member, role_id: int) -> bool:
    return any(r.id == role_id for r in member.roles)


def is_xp_locked(user_id: int) -> bool:
    if user_id in xp_locks:
        if time.time() < xp_locks[user_id]:
            return True
        else:
            end_timestamp = xp_locks.pop(user_id, None)
            if end_timestamp:
                bot.loop.create_task(notify_xp_unlocked_automatically(user_id))
    return False


async def notify_xp_unlocked_automatically(user_id: int):
    for guild in bot.guilds:
        member = guild.get_member(user_id)
        if member:
            dm_embed = discord.Embed(
                title="🔓 Deine XP wurden automatisch freigeschaltet",
                description="Der Zeitraum deiner XP-Sperre ist abgelaufen. Du erhältst ab sofort wieder regulär XP.",
                color=discord.Color.green()
            )
            try:
                await member.send(embed=dm_embed)
            except discord.Forbidden:
                pass
            break


def parse_duration(duration_str: str):
    match = re.match(r"^(\d+)\s*([mhdw])$", duration_str.strip().lower())
    if not match:
        return None, None
    val, unit = int(match.group(1)), match.group(2)
    multipliers = {'m': 60, 'h': 3600, 'd': 86400, 'w': 604800}
    units_text = {'m': 'Minute(n)', 'h': 'Stunde(n)', 'd': 'Tag(en)', 'w': 'Woche(n)'}
    seconds = val * multipliers[unit]
    return seconds, f"{val} {units_text[unit]}"


async def log_xp_action(guild: discord.Guild, user: discord.Member, amount: int, source: str, details: str = ""):
    kanal = guild.get_channel(XP_LOG_KANAL_ID)
    if not kanal:
        return
    embed = discord.Embed(
        title="📊 XP Log",
        color=discord.Color.blue()
    )
    embed.add_field(name="👤 Benutzer", value=user.mention, inline=True)
    embed.add_field(name="✨ Erhaltene/Geänderte XP", value=f"`{amount} XP`", inline=True)
    embed.add_field(name="📌 Art der XP", value=source, inline=False)
    if details:
        embed.add_field(name="📝 Details", value=details, inline=False)
    embed.set_footer(text="Sirius RP • XP Logging")
    await kanal.send(embed=embed)


async def log_xp_general_action(guild: discord.Guild, action_title: str, description: str):
    kanal = guild.get_channel(XP_LOG_KANAL_ID)
    if not kanal:
        return
    embed = discord.Embed(
        title=f"📊 XP Log: {action_title}",
        description=description,
        color=discord.Color.gold()
    )
    embed.set_footer(text="Sirius RP • XP Logging")
    await kanal.send(embed=embed)


def add_xp(user_id: int, base_points: int) -> int:
    if is_xp_locked(user_id) or base_points <= 0:
        return 0
    final_points = base_points
    global active_xp_boost
    if active_xp_boost:
        if time.time() < active_xp_boost['end_timestamp']:
            mult = 1 + (active_xp_boost['percentage'] / 100.0)
            final_points = int(round(base_points * mult))
        else:
            active_xp_boost = None
    user_xp[user_id] = user_xp.get(user_id, 0) + final_points
    save_data()
    return final_points


def get_sorted_xp_list(guild: discord.Guild):
    sorted_users = sorted(user_xp.items(), key=lambda x: x[1], reverse=True)
    valid_team_xp = []
    for u_id, xp in sorted_users:
        member = guild.get_member(u_id)
        if member and is_team_member(member):
            valid_team_xp.append((member, xp))
    return valid_team_xp


def build_leaderboard_embed(guild: discord.Guild) -> discord.Embed:
    embed = discord.Embed(
        title="🏆 XP Leaderboard — Sirius RP",
        description=(
            "Klicke unten auf den Button, um das **gesamte Top 30 Leaderboard** einzusehen!\n\n"
            "━━━━━━━\n"
            "**__Wie du XP Sammelst:__**\n"
            " ✉️ **+5 XP** pro Nachricht (10 Sekunden Cooldown)\n"
            " 🎙️ **+1 XP** per Minute im Voice (keine Pause/AFK)\n"
            " ⭐ **+3–15 XP** für erhaltenes Feedback (3⭐=3XP, 4⭐=10XP, 5⭐=15XP)\n"
            " 📞 **+10 XP** für übernommenen Call Admin Fall\n"
            " 🚨 **+15 XP** für erfolgreiche Dizzy-Kontrolle\n\n"
            "━━━━━━━\n\n"
            " ⚠️ **XP-Ausnutzung (z. B. Spam, AFK-Farmen, Self-Feedback)** wird erkannt und **führt zu Sanktionen** — Verwarnung, Kick oder Bann nach Ermessen du Teams."
        ),
        color=discord.Color.blue()
    )
    return embed


def get_roblox_user_id(username: str) -> int:
    try:
        user_res = requests.post(
            "https://users.roblox.com/v1/usernames/users",
            json={"usernames": [username], "excludeBannedUsers": False},
            timeout=5
        )
        if user_res.status_code == 200:
            data = user_res.json()
            if data["data"]:
                return data["data"][0]["id"]
    except Exception as e:
        print(f"Fehler beim Überprüfen des Roblox-Benutzers: {e}")
    return None


def get_roblox_avatar_url(username: str) -> str:
    try:
        user_id = get_roblox_user_id(username)
        if user_id:
            thumb_res = requests.get(
                f"https://thumbnails.roblox.com/v1/users/avatar-headshot?userIds={user_id}&size=150x150&format=Png&isCircular=false",
                timeout=5
            )
            if thumb_res.status_code == 200:
                thumb_data = thumb_res.json()
                if thumb_data["data"]:
                    return thumb_data["data"][0]["imageUrl"]
    except Exception as e:
        print(f"Fehler beim Abrufen des Roblox-Avatars: {e}")
    return None


# ==========================================
# COMMAND: FEEDBACK STATS & REMOVE
# ==========================================
@bot.tree.command(name="feedback-stats", description="Zeige die Feedback-Statistiken für ein Teammitglied an.")
@app_commands.describe(user="Das Teammitglied")
async def feedback_stats(interaction: discord.Interaction, user: discord.Member):
    if not has_role(interaction.user, XP_BOOST_LOCK_ROLLE_ID):
        await interaction.response.send_message("❌ Du hast keine Berechtigung, diesen Befehl auszuführen.", ephemeral=True)
        return

    if not has_role(user, TEAM_ROLLE_ID):
        await interaction.response.send_message("❌ Diese Person hat keine Feedback-Statistiken (kein Teammitglied).", ephemeral=True)
        return

    feedbacks = team_feedbacks.get(str(user.id), [])
    count = len(feedbacks)

    if count == 0:
        await interaction.response.send_message(f"ℹ️ {user.display_name} hat bisher kein Feedback erhalten.", ephemeral=True)
    else:
        total_score = sum(f["sterne"] for f in feedbacks)
        avg = total_score / count
        embed = discord.Embed(
            title=f"📊 Feedback-Statistik: {user.display_name}",
            description=f"Hier ist der berechnete Durchschnitt aller erhaltenen Feedbacks:",
            color=discord.Color.gold()
        )
        embed.add_field(name="Durchschnittsbewertung", value=f"**{avg:.2f} ⭐** (basiert auf {count} Bewertungen)", inline=False)
        embed.set_thumbnail(url=user.display_avatar.url)
        embed.set_footer(text="Sirius RP • Feedback-System")
        
        await interaction.response.send_message(embed=embed, ephemeral=True)

    log_kanal = interaction.guild.get_channel(FEEDBACK_REMOVE_LOG_KANAL_ID)
    if log_kanal:
        log_embed = discord.Embed(
            title="📊 Feedback-Stats aufgerufen",
            description=f"Von {interaction.user.mention} für {user.mention}.",
            color=discord.Color.blue()
        )
        log_embed.set_footer(text="Sirius RP • Logging")
        await log_kanal.send(embed=log_embed)


class FeedbackRemoveReasonModal(ui.Modal, title="Grund für Feedback-Entfernung"):
    grund = ui.TextInput(
        label="Grund",
        style=discord.TextStyle.paragraph,
        placeholder="Warum wird dieses Feedback entfernt?",
        required=True,
        max_length=500
    )

    def __init__(self, target_user: discord.Member, feedback_index: int):
        super().__init__()
        self.target_user = target_user
        self.feedback_index = feedback_index

    async def on_submit(self, interaction: discord.Interaction):
        await interaction.response.defer(ephemeral=True)
        
        user_id_str = str(self.target_user.id)
        if user_id_str not in team_feedbacks or len(team_feedbacks[user_id_str]) <= self.feedback_index:
            await interaction.followup.send("❌ Das ausgewählte Feedback existiert nicht mehr.", ephemeral=True)
            return

        removed_fb = team_feedbacks[user_id_str].pop(self.feedback_index)
        if not team_feedbacks[user_id_str]:
            team_feedbacks.pop(user_id_str, None)
        save_data()

        xp_map = {3: 3, 4: 10, 5: 15}
        xp_zu_entfernen = xp_map.get(removed_fb["sterne"], 0)
        if xp_zu_entfernen > 0:
            current_xp = user_xp.get(self.target_user.id, 0)
            user_xp[self.target_user.id] = max(0, current_xp - xp_zu_entfernen)
            save_data()
            await refresh_leaderboard_in_channel()

        log_kanal = interaction.guild.get_channel(FEEDBACK_REMOVE_LOG_KANAL_ID)
        if log_kanal:
            log_embed = discord.Embed(
                title="🗑️ Feedback entfernt",
                description=f"Ein Feedback für {self.target_user.mention} wurde gelöscht.",
                color=discord.Color.red()
            )
            log_embed.add_field(name="🛡️ Moderator", value=interaction.user.mention, inline=True)
            log_embed.add_field(name="👤 Teammitglied", value=self.target_user.mention, inline=True)
            log_embed.add_field(name="⭐ Sterne", value="⭐" * removed_fb["sterne"], inline=True)
            log_embed.add_field(name="💬 Ursprünglicher Kommentar", value=removed_fb["kommentar"], inline=False)
            log_embed.add_field(name="📝 Grund der Entfernung", value=self.grund.value, inline=False)
            log_embed.set_footer(text="Sirius RP • Feedback-Remove System")
            await log_kanal.send(embed=log_embed)

        await interaction.followup.send("✅ Das Feedback wurde erfolgreich entfernt und die Stats/XP wurden aktualisiert.", ephemeral=True)


class FeedbackRemoveSelect(ui.Select):
    def __init__(self, target_user: discord.Member, feedbacks: list):
        self.target_user = target_user
        options = []
        for idx, fb in enumerate(feedbacks):
            stars_str = "⭐" * fb["sterne"]
            label = f"#{idx+1} | {stars_str} | Von: {fb['autor_name']}"
            desc = fb["kommentar"][:75] if len(fb["kommentar"]) > 75 else fb["kommentar"]
            options.append(discord.SelectOption(label=label[:100], value=str(idx), description=desc[:100]))
            
        super().__init__(placeholder="Wähle das zu entfernende Feedback aus...", min_values=1, max_values=1, options=options)

    async def callback(self, interaction: discord.Interaction):
        selected_idx = int(self.values[0])
        modal = FeedbackRemoveReasonModal(self.target_user, selected_idx)
        await interaction.response.send_modal(modal)


class FeedbackRemoveView(ui.View):
    def __init__(self, target_user: discord.Member, feedbacks: list):
        super().__init__(timeout=120)
        self.add_item(FeedbackRemoveSelect(target_user, feedbacks))


@bot.tree.command(name="feedback-remove", description="Entferne ein Feedback eines Teammitglieds.")
@app_commands.describe(user="Das Teammitglied")
async def feedback_remove(interaction: discord.Interaction, user: discord.Member):
    if not has_role(interaction.user, 1527349818031214718) and not interaction.user.guild_permissions.administrator:
        await interaction.response.send_message("❌ Du hast keine Berechtigung, diesen Befehl auszuführen.", ephemeral=True)
        return

    if not has_role(user, 1527349817708122189):
        await interaction.response.send_message("❌ Dieses Mitglied hat keine Teamrolle und somit keine Feedbacks.", ephemeral=True)
        return

    feedbacks = team_feedbacks.get(str(user.id), [])
    if not feedbacks:
        await interaction.response.send_message(f"ℹ️ Für {user.display_name} sind keine Feedbacks im System hinterlegt.", ephemeral=True)
        return

    sorted_feedbacks = sorted(feedbacks, key=lambda x: x["timestamp"], reverse=True)

    view = FeedbackRemoveView(user, sorted_feedbacks)
    
    embed = discord.Embed(
        title=f"🗑️ Feedback entfernen: {user.display_name}",
        description="Wähle im Dropdown-Menü unten das Feedback aus, welches du entfernen möchtest. (Neu nach Alt sortiert)",
        color=discord.Color.red()
    )
    for idx, fb in enumerate(sorted_feedbacks[:5]):
        embed.add_field(name=f"#{idx+1} — {'⭐'*fb['sterne']}", value=f"**Kommentar:** {fb['kommentar']}\n*Datum:* <t:{int(fb['timestamp'])}:R>", inline=False)
        
    await interaction.response.send_message(embed=embed, view=view, ephemeral=True)


# ==========================================
# BEWERBUNG SYSTEM (MODALS & VIEWS)
# ==========================================

class StartModal(discord.ui.Modal, title="Bewerbungsgespräch Starten"):
    applicant = discord.ui.TextInput(
        label="Bewerber (Name oder Mention)",
        placeholder="@Nutzername oder Name des Bewerbers",
        required=True
    )

    async def on_submit(self, interaction: discord.Interaction):
        view = EvaluationView(interviewer=interaction.user, applicant_str=self.applicant.value)
        embed = view.get_current_embed()
        await interaction.response.send_message(embed=embed, view=view, ephemeral=True)


class NoteModal(discord.ui.Modal, title="Notiz zur Frage hinzufügen"):
    def __init__(self, eval_view, current_note=""):
        super().__init__()
        self.eval_view = eval_view
        self.note_input = discord.ui.TextInput(
            label="Anmerkung / Notiz",
            style=discord.TextStyle.paragraph,
            default=current_note,
            required=False,
            placeholder="Optional: Bemerkung zur Antwort hier eintragen..."
        )
        self.add_item(self.note_input)

    async def on_submit(self, interaction: discord.Interaction):
        current_idx = self.eval_view.current_idx
        if current_idx not in self.eval_view.answers:
            self.eval_view.answers[current_idx] = {"points": 0, "emoji": "❌ Nicht bewertet", "note": self.note_input.value}
        else:
            self.eval_view.answers[current_idx]["note"] = self.note_input.value
            
        await interaction.response.edit_message(embed=self.eval_view.get_current_embed(), view=self.eval_view)


class FazitModal(discord.ui.Modal, title="Abschluss & Fazit"):
    fazit = discord.ui.TextInput(
        label="Fazit zum Bewerber",
        style=discord.TextStyle.paragraph,
        placeholder="z.B. Hat gut geantwortet, brauchte bei FRP etwas Bedenkzeit...",
        required=True
    )

    def __init__(self, eval_view):
        super().__init__()
        self.eval_view = eval_view

    async def on_submit(self, interaction: discord.Interaction):
        await interaction.response.defer()
        await self.eval_view.finish_evaluation(interaction, self.fazit.value)


class EvaluationView(discord.ui.View):
    def __init__(self, interviewer, applicant_str):
        super().__init__(timeout=None)
        self.interviewer = interviewer
        self.applicant_str = applicant_str
        self.current_idx = 0
        self.answers = {}

    def get_current_embed(self):
        q_data = QUESTIONS[self.current_idx]
        embed = discord.Embed(
            title=f"📋 Frage {self.current_idx + 1} von {len(QUESTIONS)}",
            description=f"**{q_data['q']}**\n\n*Maximal erreichbare Punkte:* **{q_data['max']} BP**",
            color=discord.Color.blue()
        )
        embed.set_author(name=f"Bewerber: {self.applicant_str}")
        
        saved = self.answers.get(self.current_idx)
        if saved:
            embed.add_field(name="Aktuelle Bewertung", value=f"{saved['emoji']} ({saved['points']} Punkte)", inline=False)
            if saved['note']:
                embed.add_field(name="Notiz", value=saved['note'], inline=False)
                
        return embed

    @discord.ui.button(label="100%", style=discord.ButtonStyle.success, emoji="🟢")
    async def btn_green(self, interaction: discord.Interaction, button: discord.ui.Button):
        await self.save_answer(interaction, 1.0, "🟢")

    @discord.ui.button(label="50%", style=discord.ButtonStyle.secondary, emoji="🟡")
    async def btn_yellow(self, interaction: discord.Interaction, button: discord.ui.Button):
        await self.save_answer(interaction, 0.5, "🟡")

    @discord.ui.button(label="0%", style=discord.ButtonStyle.danger, emoji="🔴")
    async def btn_red(self, interaction: discord.Interaction, button: discord.ui.Button):
        await self.save_answer(interaction, 0.0, "🔴")

    @discord.ui.button(label="📝 Notiz hinzufügen/ändern", style=discord.ButtonStyle.secondary, row=1)
    async def btn_note(self, interaction: discord.Interaction, button: discord.ui.Button):
        current_note = self.answers.get(self.current_idx, {}).get("note", "")
        modal = NoteModal(self, current_note=current_note)
        await interaction.response.send_modal(modal)

    async def save_answer(self, interaction: discord.Interaction, multiplier: float, emoji: str):
        max_p = QUESTIONS[self.current_idx]["max"]
        pts = int(max_p * multiplier)
        
        current_note = self.answers.get(self.current_idx, {}).get("note", "")
        self.answers[self.current_idx] = {
            "points": pts,
            "emoji": emoji,
            "note": current_note
        }

        if self.current_idx < len(QUESTIONS) - 1:
            self.current_idx += 1
            await interaction.response.edit_message(embed=self.get_current_embed(), view=self)
        else:
            modal = FazitModal(self)
            await interaction.response.send_modal(modal)

    async def finish_evaluation(self, interaction: discord.Interaction, fazit: str):
        total_points = sum(ans["points"] for ans in self.answers.values())
        passed = total_points >= PASS_SCORE

        status_text = "✅ BESTANDEN" if passed else "❌ NICHT BESTANDEN"

        applicant_display = self.applicant_str
        if self.applicant_str.isdigit():
            applicant_display = f"<@{self.applicant_str}>"

        text_msg = (
            f"📄 **AUSWERTUNG BEWERBUNGSGESPRÄCH** 📄\n"
            f"━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n"
            f"👤 **Bewerber:** {applicant_display}\n"
            f"🛡️ **Ausbilder:** {self.interviewer.mention}\n"
            f"📊 **Ergebnis:** {total_points} / {MAX_SCORE} Punkte ({status_text})\n"
            f"━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n\n"
            f"**__EINZELBEWERTUNG__**\n"
        )

        for i, q in enumerate(QUESTIONS):
            ans = self.answers.get(i, {"emoji": "⚪", "points": 0, "note": ""})
            text_msg += f"**{i+1}. {q['q']}**\n"
            text_msg += f"└ Bewertung: {ans['emoji']} ({ans['points']} / {q['max']} Pkt.)\n"
            if ans["note"]:
                text_msg += f"└ *Anmerkung:* {ans['note']}\n"
            text_msg += "\n"

        text_msg += f"━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n"
        text_msg += f"📝 **FAZIT DES AUSBILDERS:**\n{fazit}\n"
        text_msg += f"━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n"

        await send_private_protocol(self.interviewer, text_msg)

        await interaction.edit_original_response(
            content="✅ **Das Gespräch wurde erfolgreich ausgewertet und dir privat per DM zugestellt!**", 
            embed=None, 
            view=None
        )


class StartBewerbungView(discord.ui.View):
    def __init__(self):
        super().__init__(timeout=None)

    @discord.ui.button(label="Bewerbungsgespräch starten", style=discord.ButtonStyle.primary, emoji="📋", custom_id="start_bw_button")
    async def start_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        user_role_ids = [role.id for role in interaction.user.roles]
        if not any(role_id in user_role_ids for role_id in ALLOWED_ROLES):
            await interaction.response.send_message("❌ Du hast nicht die benötigte Rolle, um ein Gespräch zu führen!", ephemeral=True)
            return

        await interaction.response.send_modal(StartModal())


# ==========================================
# VERIFY UI-KOMPONENTEN
# ==========================================

class VerifyView(ui.View):
    def __init__(self):
        super().__init__(timeout=None)

    @ui.button(label="✅ Verifizieren", style=discord.ButtonStyle.success, custom_id="verify_button_click")
    async def verify_button(self, interaction: discord.Interaction, button: ui.Button):
        member = interaction.user
        guild = interaction.guild

        verified_role = guild.get_role(VERIFIED_ROLLE_ID)
        unverified_role = guild.get_role(UNVERIFIED_ROLLE_ID)

        if not verified_role or not unverified_role:
            await interaction.response.send_message("❌ Es gab ein Konfigurationsproblem mit den Rollen. Bitte kontaktiere das Team.", ephemeral=True)
            return

        if verified_role in member.roles:
            await interaction.response.send_message("⚠️ Du bist bereits verifiziert und kannst diesen Prozess nicht erneut durchführen!", ephemeral=True)
            return

        try:
            await member.add_roles(verified_role, reason="Erfolgreich verifiziert")
            if unverified_role in member.roles:
                await member.remove_roles(unverified_role, reason="Verifizierung abgeschlossen")

            await interaction.response.send_message("🎉 Du hast dich erfolgreich verifiziert! Viel Spaß auf dem Server.", ephemeral=True)
        except discord.Forbidden:
            await interaction.response.send_message("❌ Mir fehlen die Berechtigungen, um dir deine Rollen zuzuweisen.", ephemeral=True)
        except Exception as e:
            await interaction.response.send_message(f"❌ Ein unerwarteter Fehler ist aufgetreten: {e}", ephemeral=True)


# ==========================================
# ZEITAUSWAHL & LEADERBOARD UI-KOMPONENTEN
# ==========================================

class TimeSelectionModal(ui.Modal, title="Zeitauswahl & Eintrag"):
    username_input = ui.TextInput(label="Ihr Name", placeholder="z. B. Anna", required=True)
    hour_input = ui.TextInput(label="Stunde (00 bis 23)", placeholder="z.B. 14", min_length=1, max_length=2, required=True)
    minute_input = ui.TextInput(label="Minute (00, 15, 30, 45)", placeholder="z.B. 30", min_length=2, max_length=2, required=True)

    async def on_submit(self, interaction: discord.Interaction):
        await interaction.response.defer(ephemeral=True)

        name = self.username_input.value.strip()
        hour_str = self.hour_input.value.strip().zfill(2)
        minute_str = self.minute_input.value.strip()

        try:
            hour_int = int(hour_str)
            if not (0 <= hour_int <= 23) or minute_str not in ["00", "15", "30", "45"]:
                raise ValueError("Ungültige Zeitwerte.")

            selected_time = f"{hour_str}:{minute_str}"

            time_leaderboard.append({"name": name, "time": selected_time})
            time_leaderboard.sort(key=lambda x: x['time'])
            save_data()

            await interaction.followup.send(f"✅ Zeit **{selected_time} Uhr** für **{name}** erfolgreich im Leaderboard eingetragen!", ephemeral=True)

        except Exception:
            await interaction.followup.send("❌ Etwas ist schiefgelaufen. Bitte stellen Sie sicher, dass die Stunde (0-23) und Minute (00, 15, 30, 45) korrekt eingegeben wurden.", ephemeral=True)


class TimeLeaderboardView(ui.View):
    def __init__(self):
        super().__init__(timeout=None)

    @ui.button(label="⏰ Zeit eintragen", style=discord.ButtonStyle.primary, custom_id="open_time_modal_btn")
    async def open_modal(self, interaction: discord.Interaction, button: ui.Button):
        await interaction.response.send_modal(TimeSelectionModal())

    @ui.button(label="📋 Zeitauswahl-Leaderboard anzeigen", style=discord.ButtonStyle.secondary, custom_id="show_time_leaderboard_btn")
    async def show_leaderboard(self, interaction: discord.Interaction, button: ui.Button):
        await interaction.response.defer(ephemeral=True)

        if not time_leaderboard:
            await interaction.followup.send("Noch keine Einträge im Zeitauswahl-Leaderboard vorhanden.", ephemeral=True)
            return

        lines = []
        for index, entry in enumerate(time_leaderboard, start=1):
            lines.append(f"**{index}.** {entry['name']} — `{entry['time']} Uhr`")

        embed = discord.Embed(
            title="⏰ Zeitauswahl Leaderboard",
            description="\n".join(lines),
            color=discord.Color.blue()
        )
        await interaction.followup.send(embed=embed, ephemeral=True)


# ==========================================
# MODERATION VIEWS & MODALS
# ==========================================

class LeaderboardTop30View(ui.View):
    def __init__(self):
        super().__init__(timeout=None)

    @ui.button(label="🏆 Gesamtes Leaderboard (Top 30)", style=discord.ButtonStyle.primary, custom_id="open_top30_leaderboard")
    async def show_top30(self, interaction: discord.Interaction, button: ui.Button):
        await interaction.response.defer(ephemeral=True)
        top_list = get_sorted_xp_list(interaction.guild)[:30]
        if not top_list:
            await interaction.followup.send("Es sind aktuell noch keine XP auf dem Server vergeben worden.", ephemeral=True)
            return

        lines = []
        for index, (member, xp_val) in enumerate(top_list, start=1):
            prefix = "🥇" if index == 1 else "🥈" if index == 2 else "🥉" if index == 3 else f"**{index}.**"
            lines.append(f"{prefix} {member.mention} — **{xp_val} XP**")

        embed = discord.Embed(
            title="🏆 Top 30 XP Leaderboard — Sirius RP",
            description="\n".join(lines),
            color=discord.Color.blue()
        )
        await interaction.followup.send(embed=embed, ephemeral=True)


class ModerationEintragModal(ui.Modal):
    def __init__(self, typ: str):
        super().__init__(title=f"Eintrag: {typ}")
        self.typ = typ

        self.grund = ui.TextInput(label="Frage 1: Grund", style=discord.TextStyle.paragraph, placeholder="Grund angeben...", required=True)
        self.roblox_name = ui.TextInput(label="Frage 2: Roblox Benutzername", placeholder="z.B. Max_RP123", required=True)
        
        if self.typ != "Kick":
            self.dauer = ui.TextInput(label="Frage 3: Dauer", placeholder="z.B. 7d, 24h oder Permanent", required=True)
        else:
            self.dauer = None

        self.add_item(self.grund)
        self.add_item(self.roblox_name)
        if self.dauer:
            self.add_item(self.dauer)

    async def on_submit(self, interaction: discord.Interaction):
        await interaction.response.defer(ephemeral=True)

        r_name = self.roblox_name.value.strip()
        
        roblox_id = get_roblox_user_id(r_name)
        if not roblox_id:
            await interaction.followup.send(f"❌ Den Benutzer **{r_name}** gibt es auf Roblox nicht. Es wurde kein Eintrag erstellt.", ephemeral=True)
            return

        r_key = r_name.lower()
        typ = self.typ
        dauer_val = self.dauer.value.strip() if self.dauer else "Permanent"

        eintrag = {
            'typ': typ,
            'grund': self.grund.value.strip(),
            'dauer': dauer_val,
            'mod': interaction.user.display_name,
            'timestamp': time.time()
        }

        if r_key not in moderation_eintraege:
            moderation_eintraege[r_key] = []
        moderation_eintraege[r_key].append(eintrag)

        is_new_ban_bolo = False
        bolo_data = None

        if typ == "Ban Bolo":
            existing = any(b['roblox_name'].lower() == r_key for b in active_ban_bolos)
            if not existing:
                is_new_ban_bolo = True
                bolo_data = {
                    'roblox_name': r_name,
                    'warn_count': "Manuell",
                    'timestamp': time.time(),
                    'eintraege_kopie': list(moderation_eintraege[r_key])
                }
                active_ban_bolos.append(bolo_data)
            else:
                for b in active_ban_bolos:
                    if b['roblox_name'].lower() == r_key:
                        b['eintraege_kopie'] = list(moderation_eintraege[r_key])

        elif typ == "Warn":
            warn_count = sum(1 for e in moderation_eintraege[r_key] if e['typ'] == "Warn")
            if warn_count in [3, 6, 9]:
                existing = any(b['roblox_name'].lower() == r_key for b in active_ban_bolos)
                if not existing:
                    is_new_ban_bolo = True
                    bolo_data = {
                        'roblox_name': r_name,
                        'warn_count': f"{warn_count} Warns",
                        'timestamp': time.time(),
                        'eintraege_kopie': list(moderation_eintraege[r_key])
                    }
                    active_ban_bolos.append(bolo_data)

        save_data()

        if is_new_ban_bolo and bolo_data:
            bolo_log_kanal = interaction.guild.get_channel(BAN_BOLO_LOG_KANAL_ID)
            if bolo_log_kanal:
                b_embed = discord.Embed(
                    title=f"🚨 Neue Ban Bolo erstellt — {r_name}",
                    description="Es wurde eine neue Ban Bolo im System hinterlegt.",
                    color=discord.Color.red()
                )
                b_embed.add_field(name="👤 Roblox-Name", value=f"`{r_name}`", inline=True)
                b_embed.add_field(name="⚠️ Auslöser", value=f"`{bolo_data['warn_count']}`", inline=True)
                b_embed.add_field(name="🛡️ Erstellt von", value=interaction.user.mention, inline=False)
                b_embed.set_footer(text="Sirius RP • Ban Bolo System")
                avatar_url_check = get_roblox_avatar_url(r_name)
                if avatar_url_check:
                    b_embed.set_thumbnail(url=avatar_url_check)
                await bolo_log_kanal.send(embed=b_embed)

        avatar_url = get_roblox_avatar_url(r_name)

        await send_moderation_log(
            guild=interaction.guild,
            action_type=typ,
            roblox_name=r_name,
            grund=self.grund.value.strip(),
            dauer=dauer_val,
            moderator=interaction.user.mention,
            avatar_url=avatar_url
        )

        embed = discord.Embed(
            title=f"🚨 Neuer Eintrag: {typ}",
            description=f"Der Eintrag für **{r_name}** wurde erfolgreich im System hinterlegt.",
            color=discord.Color.red() if typ in ["Bann", "Ban Bolo"] else discord.Color.gold()
        )
        embed.add_field(name="👤 Roblox Name", value=f"`{r_name}`", inline=True)
        embed.add_field(name="📌 Typ", value=f"`{typ}`", inline=True)
        embed.add_field(name="⏳ Dauer", value=f"`{dauer_val}`", inline=True)
        embed.add_field(name="📝 Grund", value=self.grund.value.strip(), inline=False)
        embed.set_footer(text=f"Eingetragen von {interaction.user.display_name} • Sirius RP")

        if avatar_url:
            embed.set_thumbnail(url=avatar_url)

        await interaction.followup.send(embed=embed, ephemeral=True)


class ModerationSelectView(ui.View):
    def __init__(self):
        super().__init__(timeout=None)

    @ui.select(
        placeholder="Wähle eine Moderations-Aktion...",
        custom_id="moderation_action_select",
        options=[
            discord.SelectOption(label="Bann", value="Bann", emoji="🔨", description="Einen Spieler bannen"),
            discord.SelectOption(label="Kick", value="Kick", emoji="👢", description="Einen Spieler kicken"),
            discord.SelectOption(label="Ban Bolo", value="Ban Bolo", emoji="🚨", description="Einen Ban Bolo Eintrag erstellen"),
            discord.SelectOption(label="Warn", value="Warn", emoji="⚠️", description="Einen Spieler verwarnen"),
        ]
    )
    async def select_action(self, interaction: discord.Interaction, select: ui.Select):
        chosen_type = select.values[0]
        await interaction.response.send_modal(ModerationEintragModal(typ=chosen_type))


class SearchEintragModal(ui.Modal, title="Einträge abfragen"):
    roblox_name = ui.TextInput(label="Roblox Benutzername", placeholder="z.B. Max_RP123", required=True)

    async def on_submit(self, interaction: discord.Interaction):
        await interaction.response.defer(ephemeral=True)

        r_name = self.roblox_name.value.strip()
        r_key = r_name.lower()

        if r_key not in moderation_eintraege or not moderation_eintraege[r_key]:
            await interaction.followup.send(f"❌ Keine Einträge für den Roblox-Benutzer **{r_name}** gefunden.", ephemeral=True)
            return

        view = SearchResultView(r_name=r_name)
        embed = view.build_embed()
        await interaction.followup.send(embed=embed, view=view, ephemeral=True)


class DeleteEintragSelect(ui.Select):
    def __init__(self, r_name: str, eintraege: list):
        self.r_name = r_name
        options = []
        for index, e in enumerate(eintraege):
            label = f"#{index+1} [{e['typ']}] {e['grund'][:30]}"
            options.append(discord.SelectOption(label=label, value=str(index), description=f"Dauer: {e['dauer']} | Mod: {e['mod']}"))
        
        super().__init__(placeholder="🗑️ Wähle einen Eintrag zum Löschen...", min_values=1, max_values=1, options=options, custom_id="delete_eintrag_select_menu")

    async def callback(self, interaction: discord.Interaction):
        await interaction.response.defer(ephemeral=True)

        if not is_team_member(interaction.user):
            await interaction.followup.send("❌ Nur Teammitglieder können Einträge löschen!", ephemeral=True)
            return

        idx = int(self.values[0])
        r_key = self.r_name.lower()

        if r_key in moderation_eintraege and len(moderation_eintraege[r_key]) > idx:
            removed = moderation_eintraege[r_key].pop(idx)
            
            if not moderation_eintraege[r_key]:
                moderation_eintraege.pop(r_key, None)

            save_data()

            await send_moderation_log(
                guild=interaction.guild,
                action_type=f"Löschung ({removed['typ']})",
                roblox_name=self.r_name,
                grund=f"Gelöschter Grund: {removed['grund']}",
                dauer=removed['dauer'],
                moderator=interaction.user.mention,
                avatar_url=get_roblox_avatar_url(self.r_name)
            )

            view = SearchResultView(r_name=self.r_name)
            embed = view.build_embed()
            
            try:
                await interaction.message.edit(embed=embed, view=view)
            except NotFound:
                pass

            await interaction.followup.send(f"✅ Eintrag **#{idx+1} ({removed['typ']})** für **{self.r_name}** wurde erfolgreich entfernt und in den Logs festgehalten.", ephemeral=True)
        else:
            await interaction.followup.send("❌ Dieser Eintrag existiert nicht mehr.", ephemeral=True)


class SearchResultView(ui.View):
    def __init__(self, r_name: str = ""):
        super().__init__(timeout=None)
        self.r_name = r_name
        if r_name:
            r_key = r_name.lower()
            eintraege = moderation_eintraege.get(r_key, [])
            if eintraege:
                self.add_item(DeleteEintragSelect(r_name=r_name, eintraege=eintraege))

    def build_embed(self) -> discord.Embed:
        r_key = self.r_name.lower()
        eintraege = moderation_eintraege.get(r_key, [])
        avatar_url = get_roblox_avatar_url(self.r_name)

        embed = discord.Embed(
            title=f"📋 Moderations-Akte: {self.r_name}",
            description=f"Übersicht aller historischen Einträge für **{self.r_name}** im System:",
            color=discord.Color.dark_blue()
        )

        if avatar_url:
            embed.set_thumbnail(url=avatar_url)

        if not eintraege:
            embed.add_field(name="ℹ️ Keine Einträge", value="Für diesen Spieler sind aktuell keine Einträge im System hinterlegt.", inline=False)
        else:
            current_time = time.time()
            for i, e in enumerate(eintraege, start=1):
                t_upper = e['typ'].upper()
                badge = "🔴" if "BANN" in t_upper or "BOLO" in t_upper else "🟡" if "WARN" in t_upper else "🔵"
                
                is_expired = False
                dauer_str = e['dauer'].strip().lower()
                if dauer_str not in ["permanent", "perma", "unendlich", "lifetime"]:
                    sec, _ = parse_duration(dauer_str)
                    if sec is not None:
                        if current_time >= (e['timestamp'] + sec):
                            is_expired = True

                if is_expired:
                    field_value = (
                        f"~~• **Grund:** {e['grund']}~~\n"
                        f"~~• **Dauer:** `{e['dauer']}` (Abgelaufen)~~_\n"
                        f"~~• **Eingetragen von:** {e['mod']}~~\n"
                        f"*(Status: Abgelaufen)*"
                    )
                    badge = "✅"
                else:
                    field_value = (
                        f"• **Grund:** {e['grund']}\n"
                        f"• **Dauer:** `{e['dauer']}`\n"
                        f"• **Eingetragen von:** {e['mod']}"
                    )

                embed.add_field(name=f"{badge} Eintrag #{i} — [{t_upper}]", value=field_value, inline=False)

        embed.set_footer(text="Sirius RP • Moderations-Datenbank")
        return embed


class SetupEintragView(ui.View):
    def __init__(self):
        super().__init__(timeout=None)

    @discord.ui.button(label="Moderate", style=discord.ButtonStyle.danger, emoji="🛡️", custom_id="setup_moderate_btn")
    async def moderate_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        if not is_team_member(interaction.user):
            await interaction.response.send_message("❌ Du hast keine Berechtigung, dieses Tool zu nutzen!", ephemeral=True)
            return
        
        await interaction.response.defer(ephemeral=True)
        await interaction.followup.send("Bitte wähle eine Option aus:", view=ModerationSelectView(), ephemeral=True)

    @discord.ui.button(label="Einträge abfragen", style=discord.ButtonStyle.secondary, emoji="🔍", custom_id="setup_search_btn")
    async def search_button(self, interaction: discord.Interaction, button: ui.Button):
        if not is_team_member(interaction.user):
            await interaction.response.send_message("❌ Du hast keine Berechtigung, dieses Tool zu nutzen!", ephemeral=True)
            return
        await interaction.response.send_modal(SearchEintragModal())


class BanBoloAbschliessenView(ui.View):
    def __init__(self, roblox_name: str = ""):
        super().__init__(timeout=None)
        self.roblox_name = roblox_name

    @ui.button(label="Ban Bolo abgeschlossen", style=discord.ButtonStyle.success, emoji="✅", custom_id="close_ban_bolo_btn")
    async def close_bolo(self, interaction: discord.Interaction, button: ui.Button):
        await interaction.response.defer(ephemeral=True)

        if not is_team_member(interaction.user):
            await interaction.followup.send("❌ Nur Teammitglieder können Ban Bolos abschließen!", ephemeral=True)
            return

        global active_ban_bolos
        active_ban_bolos = [b for b in active_ban_bolos if b['roblox_name'].lower() != self.roblox_name.lower()]
        save_data()

        bolo_log_kanal = interaction.guild.get_channel(BAN_BOLO_LOG_KANAL_ID)
        if bolo_log_kanal:
            b_embed = discord.Embed(
                title=f"✅ Ban Bolo akzeptiert & abgeschlossen — {self.roblox_name}",
                description=f"Die Ban Bolo wurde von {interaction.user.mention} erfolgreich bearbeitet und abgeschlossen.",
                color=discord.Color.green()
            )
            b_embed.add_field(name="👤 Roblox-Name", value=f"`{self.roblox_name}`", inline=True)
            b_embed.add_field(name="🛡️ Bearbeitet von", value=interaction.user.mention, inline=True)
            b_embed.set_footer(text="Sirius RP • Ban Bolo System")
            await bolo_log_kanal.send(embed=b_embed)

        await interaction.followup.send(f"✅ Die Ban Bolo für **{self.roblox_name}** wurde erfolgreich abgeschlossen und entfernt.", ephemeral=True)


class BanBoloMainView(ui.View):
    def __init__(self):
        super().__init__(timeout=None)

    @ui.button(label="Offene Ban Bolos sehen", style=discord.ButtonStyle.danger, emoji="🚨", custom_id="view_open_ban_bolos_btn")
    async def view_bolos(self, interaction: discord.Interaction, button: ui.Button):
        await interaction.response.defer(ephemeral=True)

        if not active_ban_bolos:
            await interaction.followup.send("🎉 Aktuell gibt es keine offenen Ban Bolos im System!", ephemeral=True)
            return

        sorted_bolos = sorted(active_ban_bolos, key=lambda x: x['timestamp'])

        for bolo in sorted_bolos:
            r_name = bolo['roblox_name']
            avatar_url = get_roblox_avatar_url(r_name)

            embed = discord.Embed(
                title=f"🚨 Offizielle Ban Bolo — {r_name}",
                description=f"Status: **Aktiv**\nAuslöser/Grund: Spieler hat Schwellenwert erreicht (**{bolo['warn_count']}**).",
                color=discord.Color.red()
            )
            if avatar_url:
                embed.set_thumbnail(url=avatar_url)

            for i, e in enumerate(bolo['eintraege_kopie'], start=1):
                det = (
                    f"• **Typ:** `{e['typ']}`\n"
                    f"• **Grund:** {e['grund']}\n"
                    f"• **Dauer:** `{e['dauer']}`\n"
                    f"• **Mod:** {e['mod']}"
                )
                embed.add_field(name=f"📄 Historien-Eintrag #{i}", value=det, inline=False)

            embed.set_footer(text="Sirius RP • Sicherheitssystem")
            view = BanBoloAbschliessenView(roblox_name=r_name)
            await interaction.followup.send(embed=embed, view=view, ephemeral=True)


class FeedbackModal(ui.Modal, title="Dein Feedback"):
    grund_input = ui.TextInput(
        label="Grund / Feedback",
        style=discord.TextStyle.paragraph,
        placeholder="Schreibe hier dein Feedback hinein...",
        required=True,
        max_length=1000
    )

    def __init__(self, sterne: int, target_member: discord.Member):
        super().__init__()
        self.sterne = sterne
        self.target_member = target_member

    async def on_submit(self, interaction: discord.Interaction):
        await interaction.response.defer(ephemeral=True)

        xp_map = {1: 0, 2: 0, 3: 3, 4: 10, 5: 15}
        xp_erhalten = xp_map.get(self.sterne, 0)
        sterne_emojis = "⭐" * self.sterne

        target_id_str = str(self.target_member.id)
        if target_id_str not in team_feedbacks:
            team_feedbacks[target_id_str] = []
        
        feedback_entry = {
            "autor_id": interaction.user.id,
            "autor_name": interaction.user.display_name,
            "sterne": self.sterne,
            "kommentar": self.grund_input.value,
            "timestamp": time.time()
        }
        team_feedbacks[target_id_str].append(feedback_entry)
        save_data()

        if is_team_member(self.target_member):
            added = add_xp(self.target_member.id, xp_erhalten)
            if added > 0:
                await log_xp_action(
                    interaction.guild,
                    self.target_member,
                    added,
                    "Feedback XP",
                    f"Erhaltenes Feedback von {interaction.user.mention} mit {sterne_emojis}"
                )
            await refresh_leaderboard_in_channel()

        log_embed = discord.Embed(
            title="🌟 Neues Feedback",
            color=discord.Color.yellow()
        )
        log_embed.add_field(name="**Von:**", value=interaction.user.mention, inline=True)
        log_embed.add_field(name="**Bewertung:**", value=sterne_emojis, inline=True)
        log_embed.add_field(name="Kommentar:", value=self.grund_input.value, inline=False)
        log_embed.add_field(name="**An:**", value=self.target_member.mention, inline=False)

        log_kanal = interaction.guild.get_channel(LOG_KANAL_ID)
        if log_kanal:
            await log_kanal.send(embed=log_embed)

        await interaction.followup.send(
            f"✅ Vielen Dank! Dein Feedback für {self.target_member.mention} wurde eingereicht.",
            ephemeral=True
        )


class FeedbackStepView(ui.View):
    def __init__(self):
        super().__init__(timeout=120)
        self.selected_member = None

    @ui.select(cls=ui.UserSelect, placeholder="1. Wähle das Teammitglied aus...", min_values=1, max_values=1, row=0)
    async def select_user(self, interaction: discord.Interaction, select: ui.UserSelect):
        await interaction.response.defer(ephemeral=True)

        selected_user = select.values[0]
        member = interaction.guild.get_member(selected_user.id)
        if not member:
            try:
                member = await interaction.guild.fetch_member(selected_user.id)
            except:
                pass

        if selected_user.id == interaction.user.id:
            await interaction.followup.send("❌ Du kannst dir selbst kein Feedback geben!", ephemeral=True)
            return

        if not member or not is_team_member(member):
            await interaction.followup.send("❌ Dieses Mitglied ist kein berechtigtes Teammitglied!", ephemeral=True)
            return

        self.selected_member = member
        await interaction.followup.send(f"✅ Teammitglied **{member.display_name}** ausgewählt! Wähle nun die Sterne aus.", ephemeral=True)

    @ui.select(
        placeholder="2. Wähle die Sterne aus...",
        options=[
            discord.SelectOption(label="1 Stern", value="1", emoji="⭐"),
            discord.SelectOption(label="2 Sterne", value="2", emoji="⭐"),
            discord.SelectOption(label="3 Sterne", value="3", emoji="⭐"),
            discord.SelectOption(label="4 Sterne", value="4", emoji="⭐"),
            discord.SelectOption(label="5 Sterne", value="5", emoji="⭐"),
        ],
        row=1
    )
    async def select_sterne(self, interaction: discord.Interaction, select: ui.Select):
        if not self.selected_member:
            await interaction.response.send_message("❌ Bitte wähle zuerst oben ein Teammitglied aus!", ephemeral=True)
            return
        sterne = int(select.values[0])
        await interaction.response.send_modal(FeedbackModal(sterne=sterne, target_member=self.selected_member))


class StartFeedbackView(ui.View):
    def __init__(self):
        super().__init__(timeout=None)

    @ui.button(label="Feedback geben", style=discord.ButtonStyle.primary, emoji="⭐", custom_id="start_feedback_btn")
    async def start_feedback(self, interaction: discord.Interaction, button: discord.ui.Button):
        if is_team_member(interaction.user):
            await interaction.response.send_message("❌ Teammitglieder dürfen kein Feedback abgeben!", ephemeral=True)
            return
        await interaction.response.send_message("Bitte wähle zuerst das Teammitglied und anschließend die Sterne aus:", view=FeedbackStepView(), ephemeral=True)


class AdminAcceptView(ui.View):
    def __init__(self, requester_user: discord.User = None, roblox_name: str = "", ort: str = "", grund: str = ""):
        super().__init__(timeout=None)
        self.requester_user = requester_user
        self.roblox_name = roblox_name
        self.ort = ort
        self.grund = grund
        self.accepted = False

    @ui.button(label="Annehmen", style=discord.ButtonStyle.success, custom_id="accept_admin_call")
    async def accept_call(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.defer(ephemeral=True)

        if not is_team_member(interaction.user):
            await interaction.followup.send("❌ Du hast nicht die benötigte Teamrolle!", ephemeral=True)
            return
        if self.requester_user and interaction.user.id == self.requester_user.id:
            await interaction.followup.send("❌ Du kannst deinen eigenen Admin-Call nicht annehmen!", ephemeral=True)
            return
        if self.accepted:
            await interaction.followup.send("❌ Dieser Admin-Call wurde bereits angenommen!", ephemeral=True)
            return

        self.accepted = True
        button.disabled = True
        button.label = f"Angenommen von {interaction.user.display_name}"
        button.style = discord.ButtonStyle.secondary
        await interaction.message.edit(view=self)

        added = add_xp(interaction.user.id, 10)
        if added > 0:
            await log_xp_action(
                interaction.guild,
                interaction.user,
                added,
                "Call Admin XP",
                f"Übernahme eines Admin-Calls von {self.requester_user.mention if self.requester_user else 'Unbekannt'}"
            )
        await refresh_leaderboard_in_channel()

        call_log_kanal = interaction.guild.get_channel(CALL_ADMIN_LOG_KANAL_ID)
        if call_log_kanal:
            log_accept_embed = discord.Embed(
                title="📞 Admin-Call akzeptiert",
                description=f"Der Admin-Call wurde von **{interaction.user.mention}** angenommen.",
                color=discord.Color.green()
            )
            log_accept_embed.add_field(name="👤 Roblox-Name", value=f"`{self.roblox_name}`", inline=True)
            log_accept_embed.add_field(name="📍 Ort", value=f"`{self.ort}`", inline=True)
            log_accept_embed.add_field(name="🛡️ Bearbeitet von", value=interaction.user.mention, inline=False)
            log_accept_embed.set_footer(text="Sirius RP • Call Admin Logs")
            await call_log_kanal.send(embed=log_accept_embed)

        if self.requester_user:
            dm_embed = discord.Embed(
                title="💫 Admin unterwegs!",
                description="**Dein Admin Ruf wurde gesehen und ein Admin ist unterwegs zu dir!**",
                color=discord.Color.red()
            )
            try:
                await self.requester_user.send(embed=dm_embed)
            except discord.Forbidden:
                pass

        await interaction.followup.send("✅ Call angenommen!", ephemeral=True)


class CallAdminModal(ui.Modal, title="Admin Rufen"):
    roblox_name = ui.TextInput(label="Dein Roblox Benutzername", placeholder="z.B. Max_RP123", required=True)
    ort = ui.TextInput(label="Wo befindest du dich aktuell?", placeholder="z.B. Würfelpark", required=True)
    grund = ui.TextInput(label="Wieso benötigst du einen Admin?", style=discord.TextStyle.paragraph, placeholder="Problem beschreiben...", required=True, max_length=1000)

    async def on_submit(self, interaction: discord.Interaction):
        await interaction.response.defer(ephemeral=True)

        confirm_embed = discord.Embed(
            title="Admin wurde gerufen",
            description="**Alle Admins wurden benachrichtigt. Bitte habe kurz Geduld.**",
            color=discord.Color.red()
        )
        await interaction.followup.send(embed=confirm_embed, ephemeral=True)

        log_channel = interaction.guild.get_channel(CALL_ADMIN_KANAL_ID)
        avatar_url = get_roblox_avatar_url(self.roblox_name.value)

        if log_channel:
            admin_embed = discord.Embed(title="⚠️ Admin angefordert!", color=discord.Color.red())
            admin_embed.add_field(name="**Roblox Benutzername:**", value=self.roblox_name.value, inline=False)
            admin_embed.add_field(name="**Ort:**", value=self.ort.value, inline=False)
            admin_embed.add_field(name="**Grund:**", value=self.grund.value, inline=False)
            admin_embed.add_field(name="**Discord Benutzer:**", value=interaction.user.mention, inline=False)

            if avatar_url:
                admin_embed.set_thumbnail(url=avatar_url)

            view = AdminAcceptView(requester_user=interaction.user, roblox_name=self.roblox_name.value, ort=self.ort.value, grund=self.grund.value)
            await log_channel.send(content=f"<@&{CALL_ADMIN_TEAM_ROLLE_ID}>", embed=admin_embed, view=view)

        call_log_kanal = interaction.guild.get_channel(CALL_ADMIN_LOG_KANAL_ID)
        if call_log_kanal:
            c_log_embed = discord.Embed(
                title="📞 Neuer Call Admin erstellt",
                description="Ein neuer Admin-Call wurde eingereicht.",
                color=discord.Color.orange()
            )
            c_log_embed.add_field(name="👤 Roblox-Name", value=f"`{self.roblox_name.value}`", inline=True)
            c_log_embed.add_field(name="📍 Ort", value=f"`{self.ort.value}`", inline=True)
            c_log_embed.add_field(name="📝 Grund", value=self.grund.value, inline=False)
            c_log_embed.add_field(name="💬 Discord User", value=interaction.user.mention, inline=False)
            c_log_embed.set_footer(text="Sirius RP • Call Admin Logs")
            if avatar_url:
                c_log_embed.set_thumbnail(url=avatar_url)
            await call_log_kanal.send(embed=c_log_embed)


class StartCallAdminView(ui.View):
    def __init__(self):
        super().__init__(timeout=None)

    @ui.button(label="Admin rufen", style=discord.ButtonStyle.danger, emoji="👤", custom_id="start_call_admin_btn")
    async def start_call(self, interaction: discord.Interaction, button: ui.Button):
        await interaction.response.send_modal(CallAdminModal())


# ==========================================
# EVENTS & LOOPS
# ==========================================

@bot.event
async def on_voice_state_update(member: discord.Member, before: discord.VoiceState, after: discord.VoiceState):
    guild = member.guild

    if before.channel and before.channel.id in ALLOWED_VOICE_CHANNELS:
        if not after.channel or after.channel.id not in ALLOWED_VOICE_CHANNELS:
            join_info = voice_join_times.pop(member.id, None)
            if join_info and is_team_member(member):
                duration_seconds = int(time.time() - join_info)
                minutes_in_call = duration_seconds // 60
                if minutes_in_call > 0:
                    earned = add_xp(member.id, minutes_in_call)
                    if earned > 0:
                        await log_xp_action(
                            guild,
                            member,
                            earned,
                            "Voice XP",
                            f"Verlassen des Voice-Kanals `{before.channel.name}` nach `{minutes_in_call} Minuten`."
                        )
                        await refresh_leaderboard_in_channel()

    if after.channel and after.channel.id in ALLOWED_VOICE_CHANNELS:
        if not before.channel or before.channel.id not in ALLOWED_VOICE_CHANNELS:
            voice_join_times[member.id] = time.time()


@tasks.loop(seconds=15)
async def check_expired_boosts():
    global active_xp_boost
    if active_xp_boost and time.time() >= active_xp_boost['end_timestamp']:
        boost_channel = bot.get_channel(XP_BOOST_ANNOUNCEMENT_KANAL_ID)
        if boost_channel:
            embed = discord.Embed(
                title="# XP Boost deaktiviert 😑",
                description=(
                    "**Der aktuelle XP Boost wurde deaktiviert!**\n\n"
                    "-# XP Boost gestoppt von: @Normal abgelaufen"
                ),
                color=discord.Color.red()
            )
            await boost_channel.send(embed=embed)
            await log_xp_general_action(boost_channel.guild, "XP Boost abgelaufen", "Der aktive XP-Boost ist regulär abgelaufen.")
        active_xp_boost = None


@tasks.loop(seconds=60)
async def check_voice_xp():
    active_fullmute_users = set()

    for guild in bot.guilds:
        for channel_id in ALLOWED_VOICE_CHANNELS:
            channel = guild.get_channel(channel_id)
            if channel and isinstance(channel, discord.VoiceChannel):
                for member in channel.members:
                    if not member.bot and is_team_member(member):
                        is_muted = member.voice.self_mute or member.voice.mute
                        is_deafened = member.voice.self_deaf or member.voice.deaf
                        is_fullmute = is_muted and is_deafened

                        if is_fullmute:
                            active_fullmute_users.add(member.id)
                            fullmute_timers[member.id] = fullmute_timers.get(member.id, 0) + 1
                            if fullmute_timers[member.id] >= 10 and member.id not in fullmute_warned:
                                fullmute_warned.add(member.id)
                                warn_text = (
                                    "# ❗Inaktiv ❗\n\n"
                                    "**Aufpassen: Du bist seit 10 Minuten Full-Mute.**\n\n"
                                    "### Du erhältst aktuell keine XP mehr!"
                                )
                                try:
                                    await member.send(warn_text)
                                except discord.Forbidden:
                                    pass
                        else:
                            if member.id not in voice_join_times:
                                voice_join_times[member.id] = time.time()
                            fullmute_timers.pop(member.id, None)
                            fullmute_warned.discard(member.id)

    for user_id in list(fullmute_timers.keys()):
        if user_id not in active_fullmute_users:
            fullmute_timers.pop(user_id, None)
            fullmute_warned.discard(user_id)


async def refresh_leaderboard_in_channel():
    global leaderboard_message_id
    kanal = bot.get_channel(LEADERBOARD_KANAL_ID)
    if not kanal:
        return
    try:
        embed = build_leaderboard_embed(kanal.guild)
        view = LeaderboardTop30View()
        if leaderboard_message_id:
            try:
                msg = await kanal.fetch_message(leaderboard_message_id)
                await msg.edit(embed=embed, view=view)
                return
            except discord.NotFound:
                pass
        async for msg in kanal.history(limit=20):
            if msg.author == bot.user and msg.embeds and "XP Leaderboard" in (msg.embeds[0].title or ""):
                leaderboard_message_id = msg.id
                await msg.edit(embed=embed, view=view)
                return
    except Exception as e:
        print(f"Fehler beim Aktualisieren des Leaderboards: {e}")


@bot.event
async def on_ready():
    bot.add_view(LeaderboardTop30View())
    bot.add_view(SetupEintragView())
    bot.add_view(BanBoloMainView())
    bot.add_view(StartFeedbackView())
    bot.add_view(StartCallAdminView())
    bot.add_view(SearchResultView())
    bot.add_view(BanBoloAbschliessenView())
    bot.add_view(TimeLeaderboardView())
    bot.add_view(VerifyView())
    bot.add_view(StartBewerbungView())

    try:
        synced = await bot.tree.sync()
        print(f"✅ {len(synced)} Slash-Commands erfolgreich synchronisiert!")
    except Exception as e:
        print(f"❌ Fehler beim Synchronisieren: {e}")
    
    custom_status = discord.CustomActivity(name="🗝️Servercode: fuzmitqj")
    await bot.change_presence(activity=custom_status)
    
    if not check_voice_xp.is_running():
        check_voice_xp.start()
    if not check_expired_boosts.is_running():
        check_expired_boosts.start()
        
    print(f'Erfolg! Eingeloggt as {bot.user}')


@bot.event
async def on_message(message: discord.Message):
    if message.author.bot or not message.guild:
        await bot.process_commands(message)
        return

    if is_team_member(message.author):
        current_time = time.time()
        user_id = message.author.id
        last_msg_time = text_cooldowns.get(user_id, 0)
        if current_time - last_msg_time >= 10:
            text_cooldowns[user_id] = current_time
            added = add_xp(user_id, 5)
            if added > 0:
                await log_xp_action(
                    message.guild,
                    message.author,
                    added,
                    "Nachrichten XP",
                    f"Verfassen einer Nachricht in {message.channel.mention}"
                )
            await refresh_leaderboard_in_channel()

    await bot.process_commands(message)


# ==========================================
# SLASH COMMANDS & SETUP
# ==========================================

@bot.tree.command(name="xp-add", description="Füge einem Teammitglied XP hinzu.")
@app_commands.describe(user="Das Teammitglied", amount="Anzahl der XP")
async def xp_add_cmd(interaction: discord.Interaction, user: discord.Member, amount: int):
    if not has_role(interaction.user, XP_GIVE_REMOVE_ROLLE_ID) and not interaction.user.guild_permissions.administrator:
        await interaction.response.send_message("❌ Du hast keine Berechtigung für diesen Befehl!", ephemeral=True)
        return
    if not is_team_member(user):
        await interaction.response.send_message("❌ Du kannst nur Teammitgliedern XP hinzufügen!", ephemeral=True)
        return
    if amount <= 0:
        await interaction.response.send_message("❌ Bitte gib eine positive Anzahl an XP ein!", ephemeral=True)
        return

    add_xp(user.id, amount)
    await log_xp_action(interaction.guild, user, amount, "Manuell hinzugefügt", f"Hinzugefügt von {interaction.user.mention}")
    await log_xp_general_action(interaction.guild, "XP Hinzugefügt", f"Teammitglied {user.mention} hat `+{amount} XP` von {interaction.user.mention} erhalten.")
    await refresh_leaderboard_in_channel()
    await interaction.response.send_message(f"✅ Dem Teammitglied {user.mention} wurden **+{amount} XP** hinzugefügt.", ephemeral=True)


@bot.tree.command(name="xp-remove", description="Entferne einem Teammitglied XP.")
@app_commands.describe(user="Das Teammitglied", amount="Anzahl der XP")
async def xp_remove(interaction: discord.Interaction, user: discord.Member, amount: int):
    if not has_role(interaction.user, XP_GIVE_REMOVE_ROLLE_ID) and not interaction.user.guild_permissions.administrator:
        await interaction.response.send_message("❌ Du hast keine Berechtigung für diesen Befehl!", ephemeral=True)
        return
    if amount <= 0:
        await interaction.response.send_message("❌ Bitte gib eine positive Anzahl an XP ein!", ephemeral=True)
        return

    current = user_xp.get(user.id, 0)
    new_val = max(0, current - amount)
    user_xp[user.id] = new_val
    save_data()
    await log_xp_action(interaction.guild, user, -amount, "Manuell entfernt", f"Entfernt von {interaction.user.mention}")
    await log_xp_general_action(interaction.guild, "XP Entfernt", f"Teammitglied {user.mention} wurden `{amount} XP` von {interaction.user.mention} abgezogen.")
    await refresh_leaderboard_in_channel()
    await interaction.response.send_message(f"✅ Dem Teammitglied {user.mention} wurden **-{amount} XP** abgezogen (Aktuell: {new_val} XP).", ephemeral=True)


@bot.tree.command(name="xp-lock", description="Sperre die XP-Einnahme eines Teammitglieds für eine bestimmte Zeit.")
@app_commands.describe(user="Das Teammitglied", duration="Dauer (z.B. 30m, 2h, 1d)", grund="Grund für den XP-Lock")
async def xp_lock(interaction: discord.Interaction, user: discord.Member, duration: str, grund: str):
    if not has_role(interaction.user, XP_BOOST_LOCK_ROLLE_ID) and not interaction.user.guild_permissions.administrator:
        await interaction.response.send_message("❌ Du hast keine Berechtigung für diesen Befehl!", ephemeral=True)
        return

    seconds, readable = parse_duration(duration)
    if not seconds:
        await interaction.response.send_message("❌ Ungültiges Format! Nutze z.B. `30m`, `2h` oder `1d`.", ephemeral=True)
        return

    xp_locks[user.id] = time.time() + seconds
    await interaction.response.send_message(f"🔒 Die XP für {user.mention} wurden für **{readable}** gesperrt.", ephemeral=True)

    dm_embed = discord.Embed(
        title="🔒 Deine XP wurden gesperrt",
        description=f"Du wurdest von einem Teammitglied für **{readable}** für den Erhalt von XP gesperrt.\n\n**Grund:** {grund}",
        color=discord.Color.red()
    )
    try:
        await user.send(embed=dm_embed)
    except discord.Forbidden:
        pass

    await log_xp_general_action(interaction.guild, "XP Lock", f"Benutzer {user.mention} wurde von {interaction.user.mention} für `{readable}` gesperrt.\n**Grund:** {grund}")


@bot.tree.command(name="xp-unlock", description="Entsperre die XP-Einnahme eines Teammitglieds manuell.")
@app_commands.describe(user="Das Teammitglied", grund="Grund für das Entsperren")
async def xp_unlock(interaction: discord.Interaction, user: discord.Member, grund: str):
    if not has_role(interaction.user, XP_BOOST_LOCK_ROLLE_ID) and not interaction.user.guild_permissions.administrator:
        await interaction.response.send_message("❌ Du hast keine Berechtigung für diesen Befehl!", ephemeral=True)
        return

    if user.id in xp_locks:
        xp_locks.pop(user.id, None)
        await interaction.response.send_message(f"🔓 Die XP-Sperre für {user.mention} wurde erfolgreich aufgehoben.", ephemeral=True)
        try:
            await user.send(embed=discord.Embed(title="🔓 Deine XP wurden entsperrt", description=f"Deine XP-Sperre wurde vorzeitig aufgehoben.\n\n**Grund:** {grund}", color=discord.Color.green()))
        except discord.Forbidden:
            pass
        await log_xp_general_action(interaction.guild, "XP Unlock", f"Sperre für {user.mention} wurde von {interaction.user.mention} aufgehoben.\n**Grund:** {grund}")
    else:
        await interaction.response.send_message(f"ℹ️ {user.mention} hat aktuell keine aktive XP-Sperre.", ephemeral=True)


@bot.tree.command(name="xp-boost", description="Aktiviere einen XP Boost für unsere Teammitglieder.")
@app_commands.describe(percentage="Prozentzahl des Boosts (z.B. 50 for +50%)", duration="Dauer (z.B. 2h, 1d)")
async def xp_boost(interaction: discord.Interaction, percentage: int, duration: str):
    if not has_role(interaction.user, XP_BOOST_LOCK_ROLLE_ID) and not interaction.user.guild_permissions.administrator:
        await interaction.response.send_message("❌ Du hast keine Berechtigung für diesen Befehl!", ephemeral=True)
        return

    global active_xp_boost
    if active_xp_boost and time.time() < active_xp_boost['end_timestamp']:
        await interaction.response.send_message("❌ Es ist bereits ein XP Boost aktiv! Du kannst erst einen neuen aktivieren, wenn der alte abgelaufen ist oder mit `/boost-stop` gestoppt wurde.", ephemeral=True)
        return

    seconds, readable = parse_duration(duration)
    if not seconds:
        await interaction.response.send_message("❌ Ungültiges Format! Nutze z.B. `30m`, `2h` oder `1d`.", ephemeral=True)
        return

    active_xp_boost = {
        'percentage': percentage,
        'end_timestamp': time.time() + seconds
    }

    await interaction.response.send_message(f"🚀 XP-Boost von **+{percentage}%** für **{readable}** aktiviert!", ephemeral=True)

    boost_channel = bot.get_channel(XP_BOOST_ANNOUNCEMENT_KANAL_ID)
    if boost_channel:
        ann_embed = discord.Embed(
            title="XP Boost aktiv 🚀",
            description=(
                f"**Es ist ab sofort ein +{percentage}% XP-Boost für {readable} aktiv! Nutze die Zeit, um extra XP zu sammeln.**\n\n"
                f"-# aktiviert von {interaction.user.mention}"
            ),
            color=discord.Color.green()
        )
        await boost_channel.send(content=f"<@&{TEAM_ROLLE_ID}>", embed=ann_embed)

    await log_xp_general_action(interaction.guild, "XP Boost Aktiviert", f"Ein XP-Boost von `+{percentage}%` für `{readable}` wurde von {interaction.user.mention} gestartet.")


@bot.tree.command(name="boost-stop", description="Stoppe den aktuell laufenden XP-Boost.")
async def boost_stop(interaction: discord.Interaction):
    if not has_role(interaction.user, XP_BOOST_LOCK_ROLLE_ID) and not interaction.user.guild_permissions.administrator:
        await interaction.response.send_message("❌ Du hast keine Berechtigung für diesen Befehl!", ephemeral=True)
        return

    global active_xp_boost
    if not active_xp_boost or time.time() >= active_xp_boost['end_timestamp']:
        active_xp_boost = None
        await interaction.response.send_message("❌ Aktuell läuft kein XP Boost, der gestoppt werden könnte.", ephemeral=True)
        return

    active_xp_boost = None
    await interaction.response.send_message("✅ Der aktuelle XP Boost wurde erfolgreich gestoppt.", ephemeral=True)

    boost_channel = bot.get_channel(XP_BOOST_ANNOUNCEMENT_KANAL_ID)
    if boost_channel:
        stop_embed = discord.Embed(
            title="XP Boost deaktiviert 😑",
            description=(
                "**Der aktuelle XP Boost wurde deaktiviert!**\n\n"
                f"-# XP Boost gestoppt von: {interaction.user.mention}"
            ),
            color=discord.Color.red()
        )
        await boost_channel.send(embed=stop_embed)

    await log_xp_general_action(interaction.guild, "XP Boost Gestoppt", f"Der aktive XP-Boost wurde vorzeitig von {interaction.user.mention} gestoppt.")


@bot.tree.command(name="xp-stats", description="Zeige deine eigenen XP oder die eines anderen Teammitglieds an.")
@app_commands.describe(user="Das Teammitglied (optional)")
async def xp_stats(interaction: discord.Interaction, user: discord.Member = None):
    target = user or interaction.user
    if not is_team_member(target):
        await interaction.response.send_message("❌ Dieser Benutzer ist kein Teammitglied.", ephemeral=True)
        return

    val = user_xp.get(target.id, 0)
    locked = is_xp_locked(target.id)
    lock_status = "🔒 Gesperrt" if locked else "🟢 Aktiv"

    embed = discord.Embed(
        title=f"📊 XP-Statistik — {target.display_name}",
        color=discord.Color.blue()
    )
    embed.add_field(name="Punkte", value=f"**{val} XP**", inline=True)
    embed.add_field(name="Status", value=lock_status, inline=True)
    if avatar := target.display_avatar.url:
        embed.set_thumbnail(url=avatar)

    await interaction.response.send_message(embed=embed, ephemeral=True)


@bot.tree.command(name="xp-reset", description="Setze die XP aller Teammitglieder komplett zurück.")
async def xp_reset(interaction: discord.Interaction):
    if not interaction.user.guild_permissions.administrator:
        await interaction.response.send_message("❌ Nur Administratoren können das gesamte Leaderboard zurücksetzen!", ephemeral=True)
        return

    user_xp.clear()
    save_data()
    await log_xp_general_action(interaction.guild, "XP Reset", f"Das gesamte XP-Leaderboard wurde von {interaction.user.mention} zurückgesetzt.")
    await refresh_leaderboard_in_channel()
    await interaction.response.send_message("🗑️ Das gesamte XP-Leaderboard wurde erfolgreich zurückgesetzt.", ephemeral=True)


@bot.tree.command(name="dizzykontrolle", description="Führe eine Dizzykontrolle für ein Mitglied durch.")
@app_commands.describe(user="Wähle das Mitglied aus, das kontrolliert wurde")
async def dizzykontrolle(interaction: discord.Interaction, user: discord.Member):
    if not is_team_member(interaction.user):
        await interaction.response.send_message("❌ Keine Berechtigung!", ephemeral=True)
        return

    if interaction.channel_id != DIZZY_KANAL_ID:
        await interaction.response.send_message(f"❌ Nur im Kanal <#{DIZZY_KANAL_ID}> erlaubt!", ephemeral=True)
        return

    mod_id = interaction.user.id
    target_id = user.id

    if mod_id == target_id:
        await interaction.response.send_message("❌ Du kannst dich nicht selbst dizzy kontrollieren!", ephemeral=True)
        return

    if (mod_id, target_id) in durchgefuehrte_kontrollen:
        await interaction.response.send_message(f"❌ Du hast die Dizzykontrolle für {user.mention} bereits durchgeführt! Du erhältst keine XP mehr dafür.", ephemeral=True)
        return

    durchgefuehrte_kontrollen.add((mod_id, target_id))
    save_data()

    received_xp = add_xp(mod_id, 15)
    if received_xp > 0:
        await log_xp_action(
            interaction.guild,
            interaction.user,
            received_xp,
            "Dizzykontrolle XP",
            f"Erfolgreiche Durchführung einer Dizzykontrolle an {user.mention}"
        )
    await refresh_leaderboard_in_channel()

    boost_info = ""
    if active_xp_boost and time.time() < active_xp_boost['end_timestamp']:
        boost_info = f" *(inkl. +{active_xp_boost['percentage']}% Boost)*"

    embed = discord.Embed(
        title="Dizzykontrolle durchgeführt ✅",
        description=f"**Teammitglied:** {interaction.user.mention}\n**Kontrollierte Person:** {user.mention}\n\n🎁 **Belohnung:** `+{received_xp} XP`{boost_info}",
        color=discord.Color.green()
    )
    
    # Nachricht im Dizzy-Kanal (1527349819742355624) senden, die nach 1 Minute verschwindet
    await interaction.response.send_message(embed=embed)
    try:
        original_msg = await interaction.original_response()
        await original_msg.delete(delay=60)
    except Exception:
        pass

    # Nachricht im Logs-Kanal (1532348593573199872) senden (bleibt dauerhaft erhalten)
    dizzy_log_kanal = interaction.guild.get_channel(DIZZY_LOG_KANAL_ID)
    if dizzy_log_kanal:
        log_embed = discord.Embed(
            title="🔍 Dizzykontrolle Log",
            description="Eine neue Dizzykontrolle wurde registriert.",
            color=discord.Color.blue()
        )
        log_embed.add_field(name="🛡️ Teammitglied", value=interaction.user.mention, inline=True)
        log_embed.add_field(name="👤 Kontrollierte Person", value=user.mention, inline=True)
        log_embed.add_field(name="✨ Vergebene XP", value=f"`+{received_xp} XP`{boost_info}", inline=False)
        log_embed.set_footer(text="Sirius RP • Dizzykontroll-System")

        await dizzy_log_kanal.send(embed=log_embed)


@bot.command(name="setupbewerbung")
@commands.has_permissions(administrator=True)
async def setup_bewerbung(ctx):
    try:
        await ctx.message.delete()
    except Exception:
        pass

    embed = discord.Embed(
        title="📋 Bewerbungsgespräch Auswertung",
        description="Klicke auf den Button unten, um das digitale Protokoll für ein Bewerbungsgespräch zu starten.\n\n*Hinweis: Nur autorisierte Teamausbilder können diesen Button verwenden.*",
        color=discord.Color.gold()
    )

    view = StartBewerbungView()
    await ctx.send(embed=embed, view=view)


@bot.command()
@commands.has_permissions(administrator=True)
async def setupverify(ctx):
    kanal = bot.get_channel(VERIFY_KANAL_ID)
    if not kanal:
        await ctx.send("❌ Verify-Kanal wurde nicht gefunden!")
        return

    embed = discord.Embed(
        title="🔐 Server-Verifizierung • Sirius RP",
        description=(
            "Herzlich willkommen auf **Sirius RP**! 🛡️\n\n"
            "Um vollen Zugriff auf alle Kanäle, Kategorien und Funktionen unseres Servers zu erhalten, "
            "musst du dich kurz verifizieren.\n\n"
            "**Was ist die Verifizierung?**\n"
            "Die Verifizierung dient als Schutz vor Bots, Spam und ungebetenen Gästen. Sie stellt sicher, "
            "dass du ein echtes Community-Mitglied bist.\n\n"
            "**Wie funktioniert es?**\n"
            "Klicke einfach auf den unteren Button (**\"Verifizieren\"**). Dadurch wird dir automatisch "
            "die verifizierte Rolle zugewiesen und die unvoreingenommene Einstiegsrolle entfernt."
        ),
        color=discord.Color.blue()
    )
    embed.set_footer(text="Sirius RP • Sicherheitssystem")

    await kanal.send(embed=embed, view=VerifyView())
    await ctx.send("✅ Verify-Panel erfolgreich im Zielkanal gesendet!")


@bot.command()
@commands.has_permissions(administrator=True)
async def setupeintrag(ctx):
    kanal = bot.get_channel(EINTRAG_PANEL_KANAL_ID)
    if not kanal:
        await ctx.send("❌ Eintrag-Kanal nicht gefunden!")
        return

    embed = discord.Embed(
        title="🛡️ Moderations-Einträge — Sirius RP",
        description="Klicke unten auf **\"Moderate\"**, um einen Eintrag (Bann, Kick, Ban Bolo oder Warn) zu erstellen.\nÜber **\"Einträge abfragen\"** kannst du alle Historien einsehen.",
        color=discord.Color.blue()
    )
    await kanal.send(embed=embed, view=SetupEintragView())
    await ctx.send("✅ Eintrag-Panel gesendet!")


@bot.command()
@commands.has_permissions(administrator=True)
async def setupbanbolo(ctx):
    kanal = bot.get_channel(BAN_BOLO_KANAL_ID)
    if not kanal:
        await ctx.send("❌ Ban Bolo Kanal nicht gefunden!")
        return

    embed = discord.Embed(
        title="⚠️ Ban Bolos",
        description="**Sehe hier die Offenen Ban Bolos**\n\n-------------------\n**Was ist eine Ban Bolo?**\nEine Ban Bolo wird automatisch vom Bot gestellt sobald ein Spieler 3, 6 oder 9 Warns hat.",
        color=discord.Color.red()
    )
    await kanal.send(embed=embed, view=BanBoloMainView())
    await ctx.send("✅ Ban Bolo Panel gesendet!")


@bot.command()
@commands.has_permissions(administrator=True)
async def setupleaderboard(ctx):
    kanal = bot.get_channel(LEADERBOARD_KANAL_ID)
    if not kanal:
        await ctx.send("❌ Leaderboard-Kanal nicht gefunden!")
        return

    embed = build_leaderboard_embed(ctx.guild)
    view = LeaderboardTop30View()
    msg = await kanal.send(embed=embed, view=view)
    
    global leaderboard_message_id
    leaderboard_message_id = msg.id
    await ctx.send("✅ Leaderboard gesendet!")


@bot.command()
@commands.has_permissions(administrator=True)
async def setupfeedback(ctx):
    kanal = bot.get_channel(FEEDBACK_PANEL_KANAL_ID)
    if not kanal:
        await ctx.send("❌ Feedback-Kanal nicht gefunden!")
        return
    embed = discord.Embed(
        title="⭐ Feedback geben - Sirius RP 💛",
        description="Drücke unten auf **\"Feedback geben\"** und bewerte die Leistung eines Teammitglieds.",
        color=discord.Color.gold()
    )
    await kanal.send(embed=embed, view=StartFeedbackView())
    await ctx.send("✅ Feedback-Panel gesendet!")


@bot.command()
@commands.has_permissions(administrator=True)
async def setupadmin(ctx):
    embed = discord.Embed(
        title="Admin Rufen (Ingame Support)",
        description="> Du brauchst Ingame einen Administrator?\n> Fülle das Formular unter der Nachricht aus.",
        color=discord.Color.red()
    )
    await ctx.send(embed=embed, view=StartCallAdminView())
    await ctx.send("✅ Admin-Rufen Panel gesendet!")


@bot.command()
@commands.has_permissions(administrator=True)
async def setuptimeleaderboard(ctx):
    embed = discord.Embed(
        title="⏰ Zeitauswahl & Leaderboard",
        description="Klicke unten auf den Button, um deine Wunschzeit (Stunden & Minuten) einzutragen, oder betrachte das aktuelle Leaderboard.",
        color=discord.Color.blue()
    )
    await ctx.send(embed=embed, view=TimeLeaderboardView())
    await ctx.send("✅ Zeitauswahl-Leaderboard Panel gesendet!")


# ==========================================
# BOT STARTEN
# ==========================================
bot.run(os.getenv("DISCORD_TOKEN"))
