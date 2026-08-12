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
# KONFIGURATION & IDS
# ==========================================
TEAM_ROLLE_ID = 1527349817708122189
RELOAD_COMMAND_ROLLE_ID = 1527739219907449022
KLEINER_WAFFENSCHEIN_ROLLE_ID = 1527349817586483220
GROSSER_WAFFENSCHEIN_ROLLE_ID = 1527349817586483221

# --- ROLLEN-KONFIGURATION (TEAMLISTE) ---
HAUPT_ROLLEN = [
    1527739219907449022,  # ♛ || Discord Inhaber
    1527349818068959301,  # 👑 || Inhaber
    1527349818068959300,  # 👑 || Stv. Inhaber
    1527349818068959299,  # 💠 || Projektleitung
    1527349818068959298,  # 💠 || Stv. Projektleitung
    1527349818068959297,  # 🔘 || Projektverwaltung
    1527349818068959296,  # 🪙 || Serverleitung
    1527349818068959295,  # 🪙 || Stv. Serverleitung
    1527349818068959293,  # 🗿 || Teamleitung
    1527349818068959292,  # 🗿 || Stv. Teamleitung
    1527349818031214721,  # 🏅 || Manager
    1527349818031214720,  # 🏅 || Stv. Manager
    1527349818031214719,  # ✨️ || Supervisor
    1527349817875890355,  # 🤖 || Developer
    1527349817800523855,  # 🪖 || Sr. Admin
    1527349817800523854,  # 🪖 || Admin
    1527349817800523853,  # 🪖 || Jr. Admin
    1527349817800523851,  # ⚔️ || Sr. Moderator
    1527349817800523850,  # ⚔️ || Moderator
    1527349817800523849,  # ⚔️ || Jr. Moderator
    1527349817800523847,  # 🔰 || Sr. Supporter
    1527349817708122191,  # 🔰 || Supporter
    1527349817708122190,  # 🔰 || Test Supporter
]

NEBEN_ROLLEN = [
    1528123954659590154,  # 🌟 || Teamausbilder
    1527427465436205187,  # 🏭 || Fraktionsverwaltung
    1527427414907687022,  # 🎉 || Event Manager
    1527426915214950550,  # 💜 || Community Managment
]

TEAM_NACHRICHTEN = {}
benutzte_nachrichten = set()

async def pruefe_und_kontrolliere(channel, user):
    gueltige_nachricht = None

    async for message in channel.history(limit=100):
        if message.author == user:
            if message.id not in benutzte_nachrichten:
                gueltige_nachricht = message
                break

    if not gueltige_nachricht:
        return "Die Person has keine verfügbare Nachricht im Chat! Sie muss erst etwas Neues schreiben."

    benutzte_nachrichten.add(gueltige_nachricht.id)
    return "Kontrolle erfolgreich durchgeführt!"

# ==========================================
# WAFFENSCHEIN SYSTEM
# ==========================================
# Dieses System läuft getrennt von der normalen Bot-Datenbank, damit
# bestehende Daten und Systeme des Bots nicht verändert werden.
WAFFENSCHEIN_BEARBEITUNG_ROLLE_ID = 1527349818031214718
WAFFENSCHEIN_Bewerbung_KANAL_ID = 1527616749011337306
WAFFENSCHEIN_LOG_KANAL_ID = 1537073461615141014

KLEINER_WAFFENSCHEIN_KATEGORIE_ID = 1528372504375332915
GROSSER_WAFFENSCHEIN_KATEGORIE_ID = 1528371868069789786

KLEINER_WAFFENSCHEIN_ROLLE_ID = 1527349817586483220
GROSSER_WAFFENSCHEIN_ROLLE_ID = 1527349817586483221

WAFFENSCHEIN_DATA_FILE = "waffenschein_bewerbungen.json"

GROSS_WAFFENSCHEIN_FRAGEN = [
    "Warum möchtest du einen Großen Waffenschein besitzen?",
    "Welche Verantwortung trägst du als Besitzer eines großen Waffenscheins?",
    "In welcher RP-Situation darf eine Langwaffe überhaupt mitgeführt oder eingesetzt werden?",
    "Was ist der Unterschied zwischen Notwehr und unnötiger Gewalt?",
    "Was solltest du nach einer Notwehr mit Waffen gebrauch machen?"
]

KLEIN_WAFFENSCHEIN_FRAGEN = [
    "Warum möchtest du einen Kleinen Waffenschein besitzen?",
    "Wie verhältst du dich wenn ein Polizist deine Waffe findet?",
    "Darfst du deine Waffe in der Öffentlichkeit nutzen/zeigen um Aufsehen zu kriegen?",
    "In welcher Situation darfst du deine Waffe nutzen?",
    "Warum kann dir der Waffenschein wieder entzogen werden?"
]

# application_id -> Bewerbungsdaten
waffenschein_bewerbungen = {}

# verhindert doppelte Ticket-Erstellung bei fast gleichzeitigem Klick
waffenschein_ticket_locks = set()
# Zusätzliche atomare Sperre: verhindert doppelte Ticket-Erstellung bei
# gleichzeitig ausgelösten Button-Interaktionen oder mehrfach registrierten Views.
waffenschein_ticket_creation_lock = asyncio.Lock()
waffenschein_views_registered = False


def load_waffenschein_data():
    if not os.path.exists(WAFFENSCHEIN_DATA_FILE):
        return {}

    try:
        with open(WAFFENSCHEIN_DATA_FILE, "r", encoding="utf-8") as f:
            data = json.load(f)

        if isinstance(data, dict):
            return data
    except Exception as e:
        print(f"❌ Fehler beim Laden der Waffenschein-Daten: {e}")

    return {}


def save_waffenschein_data():
    temp_file = f"{WAFFENSCHEIN_DATA_FILE}.tmp"

    try:
        with open(temp_file, "w", encoding="utf-8") as f:
            json.dump(
                waffenschein_bewerbungen,
                f,
                ensure_ascii=False,
                indent=4
            )
            f.flush()
            os.fsync(f.fileno())

        os.replace(temp_file, WAFFENSCHEIN_DATA_FILE)
    except Exception as e:
        print(f"❌ Fehler beim Speichern der Waffenschein-Daten: {e}")
        try:
            if os.path.exists(temp_file):
                os.remove(temp_file)
        except OSError:
            pass


waffenschein_bewerbungen = load_waffenschein_data()


def waffenschein_get_application_from_embed(message: discord.Message):
    """Findet die Bewerbung zuverlässig über Embed-Text, Felder oder Buttons."""
    if not message.embeds:
        return None

    embed = message.embeds[0]

    # 1. ID aus der Description suchen.
    description = embed.description or ""
    match = re.search(
        r"Bewerbungs-ID\s*:\s*`([^`]+)`",
        description,
        re.IGNORECASE
    )

    if match:
        application = waffenschein_bewerbungen.get(match.group(1))
        if application:
            return application

    # 2. ID aus den Embed-Feldern suchen.
    for field in embed.fields:
        combined = f"{field.name}\n{field.value}"
        match = re.search(
            r"Bewerbungs-ID\s*:\s*`([^`]+)`",
            combined,
            re.IGNORECASE
        )
        if match:
            application = waffenschein_bewerbungen.get(match.group(1))
            if application:
                waffenschein_repair_stale_paid_status(application)
            if application:
                return application

        # Falls nur der Feldwert die ID enthält.
        match = re.fullmatch(r"`([^`]+)`", str(field.value).strip())
        if match and field.name.strip().lower() in {
            "bewerbungs-id",
            "bewerbung-id",
            "application-id"
        }:
            application = waffenschein_bewerbungen.get(match.group(1))
            if application:
                return application

    # 3. Fallback: alle sichtbaren Embed-Texte nach einer bekannten ID
    visible_text = " ".join([
        description,
        str(embed.title or ""),
        *[
            f"{field.name} {field.value}"
            for field in embed.fields
        ]
    ])

    for application_id, application in waffenschein_bewerbungen.items():
        if str(application_id) in visible_text:
            return application

    # 4. WICHTIGER Fallback für bereits vorhandene Bewerbungen:
    # Ältere Bewerbungsnachrichten können noch keine Bewerbungs-ID
    # enthalten. Deshalb lesen wir den Bewerber direkt aus dem Embed
    # und suchen seine offene Bewerbung in der JSON-Datenbank.
    user_match = re.search(
        r"Bewerber\s*:\s*<@!?([0-9]+)>",
        visible_text,
        re.IGNORECASE
    )

    if user_match:
        user_id = int(user_match.group(1))
        license_key = None
        lower_text = visible_text.lower()
        if "großer waffenschein" in lower_text:
            license_key = "gross"
        elif "kleiner waffenschein" in lower_text:
            license_key = "klein"

        candidates = [
            app for app in waffenschein_bewerbungen.values()
            if int(app.get("user_id", 0)) == user_id
            and (license_key is None or app.get("license_key") == license_key)
        ]

        # NIEMALS eine bereits bezahlte Bewerbung als Fallback auswählen.
        # Sonst kann eine alte bezahlte Bewerbung eine neue offene Bewerbung
        # desselben Users überschreiben.
        active_candidates = [
            app for app in candidates
            if app.get("status") in {"dm_started", "pending", "ticket_creating", "ticket_open"}
        ]

        if active_candidates:
            return max(
                active_candidates,
                key=lambda app: float(app.get("completed_at") or app.get("started_at") or 0)
            )

    return None


def waffenschein_user_has_license_role(member):
    """Prüft, ob der Benutzer bereits irgendeinen Waffenschein besitzt."""
    if member is None:
        return False

    return any(
        role.id in {
            KLEINER_WAFFENSCHEIN_ROLLE_ID,
            GROSSER_WAFFENSCHEIN_ROLLE_ID
        }
        for role in member.roles
    )


def waffenschein_user_has_specific_license(member, license_key: str):
    """
    Prüft nur, ob der Benutzer genau den Waffenschein besitzt,
    für den er sich gerade bewerben möchte.

    Wichtig:
    - Kleiner vorhanden -> Großer darf beantragt werden.
    - Großer vorhanden -> Kleiner darf beantragt werden.
    - Derselbe Waffenschein vorhanden -> darf NICHT erneut beantragt werden.
    """
    if member is None:
        return False

    wanted_role_id = (
        GROSSER_WAFFENSCHEIN_ROLLE_ID
        if license_key == "gross"
        else KLEINER_WAFFENSCHEIN_ROLLE_ID
    )

    return any(role.id == wanted_role_id for role in member.roles)


def waffenschein_extract_user_id_from_message(message: discord.Message):
    """Liest eine Bewerber-ID aus Embed/Content einer Bewerbungsnachricht."""
    texts = [message.content or ""]

    for embed in message.embeds:
        texts.append(embed.title or "")
        texts.append(embed.description or "")
        for field in embed.fields:
            texts.append(str(field.name))
            texts.append(str(field.value))

    visible_text = "\n".join(texts)

    # Discord-Mention: <@123> oder <@!123>
    match = re.search(r"<@!?([0-9]{15,25})>", visible_text)
    if match:
        return int(match.group(1))

    # Fallback für ältere/angepasste Embeds: Bewerber: 123
    match = re.search(
        r"(?:Bewerber|Benutzer|User)\s*:?\s*`?([0-9]{15,25})`?",
        visible_text,
        re.IGNORECASE
    )
    if match:
        return int(match.group(1))

    return None


def waffenschein_extract_license_key_from_message(message: discord.Message):
    """Erkennt Groß/Klein aus einer Bewerbungsnachricht."""
    texts = [message.content or ""]

    for embed in message.embeds:
        texts.append(embed.title or "")
        texts.append(embed.description or "")
        for field in embed.fields:
            texts.append(str(field.name))
            texts.append(str(field.value))

    text = "\n".join(texts).lower()

    if "großer waffenschein" in text:
        return "gross"
    if "kleiner waffenschein" in text:
        return "klein"

    return None


def waffenschein_payment_is_confirmed(application: dict):
    """
    Liefert nur dann True, wenn die Zahlung tatsächlich bestätigt wurde.

    Ältere/fehlerhafte Daten können noch status="paid" enthalten, obwohl
    nie auf den Bezahl-Button gedrückt wurde. Deshalb wird zusätzlich ein
    echter Zahlungsnachweis verlangt (paid_at + paid_by/paid_role_id).
    """
    if application.get("status") != "paid":
        return False

    paid_at = application.get("paid_at")
    paid_by = application.get("paid_by")
    paid_role_id = application.get("paid_role_id")

    return bool(paid_at and (paid_by or paid_role_id))


def waffenschein_repair_stale_paid_status(application: dict):
    """
    Repariert einen alten/stale paid-Status, wenn kein echter
    Zahlungsnachweis vorhanden ist. Gibt True zurück, wenn repariert wurde.
    """
    if application.get("status") == "paid" and not waffenschein_payment_is_confirmed(application):
        application["status"] = "pending"
        application.pop("paid_at", None)
        application.pop("paid_by", None)
        application.pop("paid_role_id", None)
        application.pop("ticket_closed_at", None)
        save_waffenschein_data()
        return True
    return False


async def waffenschein_resolve_application_from_message(message: discord.Message):
    """Ermittelt die Bewerbung zuverlässig für Ticket/Ablehnen-Buttons.

    Reihenfolge:
    1. Gespeicherte application_message_id
    2. Bewerbungs-ID/Embed-Daten
    3. Fallback aus Bewerber + Lizenz aus dem Embed

    Bei älteren Bewerbungen wird der fehlende JSON-Eintrag automatisch ergänzt.
    """
    for stored_application in waffenschein_bewerbungen.values():
        try:
            if int(stored_application.get("application_message_id") or 0) == int(message.id):
                return stored_application
        except (TypeError, ValueError):
            continue

    application = waffenschein_get_application_from_embed(message)
    if application:
        # Auch gefundene alte Einträge dauerhaft mit der Nachricht verknüpfen.
        application["application_message_id"] = message.id
        application["application_channel_id"] = message.channel.id

        # Falls ein alter Datensatz fälschlicherweise "paid" enthält, aber
        # keinen echten Zahlungsnachweis besitzt, wird er wieder auf offen
        # gesetzt. So wird eine neue unbezahlte Bewerbung nicht blockiert.
        waffenschein_repair_stale_paid_status(application)
        save_waffenschein_data()
        return application

    recovered_user_id = waffenschein_extract_user_id_from_message(message)
    recovered_license_key = waffenschein_extract_license_key_from_message(message)

    if not recovered_user_id or not recovered_license_key:
        return None

    # Bereits vorhandene Einträge des Users + Lizenz bevorzugen.
    candidates = [
        app for app in waffenschein_bewerbungen.values()
        if int(app.get("user_id", 0)) == int(recovered_user_id)
        and app.get("license_key") == recovered_license_key
    ]

    active_candidates = [
        app for app in candidates
        if app.get("status") in {"dm_started", "pending", "ticket_creating", "ticket_open"}
    ]

    if active_candidates:
        app = max(
            active_candidates,
            key=lambda item: float(item.get("completed_at") or item.get("started_at") or 0)
        )
        app["application_message_id"] = message.id
        app["application_channel_id"] = message.channel.id
        save_waffenschein_data()
        return app

    recovered_id = f"legacy-{message.id}"
    application = waffenschein_make_fallback_application(
        recovered_user_id,
        recovered_license_key,
        recovered_id
    )
    application["application_message_id"] = message.id
    application["application_channel_id"] = message.channel.id
    waffenschein_bewerbungen[recovered_id] = application
    save_waffenschein_data()
    return application


async def waffenschein_send_dm_status(application: dict, status: str):
    """Sendet dem Bewerber eine schöne private Status-DM."""
    user_id = int(application.get("user_id", 0))
    try:
        user = bot.get_user(user_id)
        if user is None:
            user = await bot.fetch_user(user_id)
    except Exception as e:
        print(f"❌ Bewerber für Waffenschein-DM nicht gefunden: {e}")
        return False

    lizenz = application.get("lizenz", "Waffenschein")

    if status == "rejected":
        embed = discord.Embed(
            title="🛡️ Waffenschein-Bewerbung",
            description=(
                f"Deine Bewerbung für den **{lizenz}** wurde von der "
                "Waffenschein-Behörde **abgelehnt**.\n\n"
                "Du kannst dich zu einem späteren Zeitpunkt erneut bewerben, "
                "sofern du die Voraussetzungen erfüllst."
            ),
            color=discord.Color.red(),
            timestamp=discord.utils.utcnow()
        )
        embed.add_field(
            name="📋 Status",
            value="🔴 **Abgelehnt**",
            inline=False
        )
        embed.add_field(
            name="💡 Hinweis",
            value=(
                "Bitte überprüfe bei einer zukünftigen Bewerbung deine "
                "Antworten und die Voraussetzungen für den gewünschten Waffenschein."
            ),
            inline=False
        )
        embed.set_footer(text="Sirius RP • Waffenschein-Behörde")
    else:
        embed = discord.Embed(
            title="🛡️ Waffenschein erfolgreich erteilt",
            description=(
                f"Herzlichen Glückwunsch! Deine Bewerbung für den **{lizenz}** "
                "wurde erfolgreich abgeschlossen.\n\n"
                "Die Zahlung wurde bestätigt und dein Waffenschein wurde dir "
                "offiziell erteilt."
            ),
            color=discord.Color.green(),
            timestamp=discord.utils.utcnow()
        )
        embed.add_field(
            name="📋 Status",
            value="🟢 **Bezahlt & genehmigt**",
            inline=False
        )
        embed.add_field(
            name="⚠️ Wichtig",
            value=(
                "Halte dich im RP weiterhin an die geltenden Regeln und "
                "verwende deinen Waffenschein nur entsprechend seinem vorgesehenen Zweck."
            ),
            inline=False
        )
        embed.set_footer(text="Sirius RP • Waffenschein-Behörde")

    try:
        await user.send(embed=embed)
        return True
    except discord.Forbidden:
        print(f"⚠️ Konnte dem Bewerber {user_id} keine Waffenschein-DM senden.")
    except Exception as e:
        print(f"❌ Fehler beim Senden der Waffenschein-DM: {e}")
    return False


def waffenschein_make_fallback_application(
    user_id: int,
    license_key: str,
    application_id: str
):
    """Erzeugt eine minimale Bewerbung für alte Daten ohne JSON-Eintrag."""
    return {
        "id": application_id,
        "user_id": int(user_id),
        "username": f"User {user_id}",
        "license_key": license_key,
        "lizenz": (
            "Großer Waffenschein"
            if license_key == "gross"
            else "Kleiner Waffenschein"
        ),
        "fragen": [],
        "antworten": [],
        "question_index": 0,
        "status": "pending",
        "started_at": time.time(),
        "completed_at": time.time(),
        "ticket_channel_id": None,
    }


async def waffenschein_find_existing_ticket(
    guild: discord.Guild,
    user_id: int,
    license_key: str
):
    """Findet ein bereits vorhandenes Waffenschein-Ticket für einen Benutzer."""
    prefix = (
        "waffenschein-gross-"
        if license_key == "gross"
        else "waffenschein-klein-"
    )

    for channel in guild.text_channels:
        topic = getattr(channel, "topic", "") or ""

        if (
            channel.name.startswith(prefix)
            or (
                "Waffenschein-Bewerbung" in topic
                and re.search(rf"User\s+{user_id}(?:\D|$)", topic)
            )
        ):
            return channel

    return None


def waffenschein_user_has_active_application(user_id: int):
    for application in waffenschein_bewerbungen.values():
        if int(application.get("user_id", 0)) != int(user_id):
            continue

        if application.get("status") in {
            "dm_started",
            "pending",
            "ticket_creating",
            "ticket_open"
        }:
            return application

    return None


async def waffenschein_log(
    application: dict,
    action: str,
    moderator=None,
    ticket_channel=None,
    extra: str = "",
    color=None
):
    """Zentrales Waffenschein-Logging."""
    channel = bot.get_channel(WAFFENSCHEIN_LOG_KANAL_ID)

    if channel is None:
        try:
            channel = await bot.fetch_channel(WAFFENSCHEIN_LOG_KANAL_ID)
        except Exception as e:
            print(f"❌ Waffenschein-Logkanal nicht gefunden: {e}")
            return

    user_id = int(application.get("user_id", 0))
    user_mention = f"<@{user_id}>"

    if color is None:
        color = discord.Color.blue()

    embed = discord.Embed(
        title="🛡️ Waffenschein — Log",
        color=color,
        timestamp=discord.utils.utcnow()
    )

    embed.add_field(
        name="Aktion",
        value=f"**{action}**",
        inline=False
    )
    embed.add_field(
        name="Bewerber",
        value=f"{user_mention}\n`{application.get('username', 'Unbekannt')}`",
        inline=True
    )
    embed.add_field(
        name="Lizenz",
        value=f"**{application.get('lizenz', 'Unbekannt')}**",
        inline=True
    )
    embed.add_field(
        name="Bewerbungs-ID",
        value=f"`{application.get('id', 'Unbekannt')}`",
        inline=True
    )

    if moderator:
        embed.add_field(
            name="Bearbeitet von",
            value=f"{moderator.mention}\n`{moderator}`",
            inline=True
        )

    if ticket_channel:
        embed.add_field(
            name="Ticket",
            value=f"`{ticket_channel.name}`\n`{ticket_channel.id}`",
            inline=True
        )

    if extra:
        embed.add_field(
            name="Information",
            value=extra[:1024],
            inline=False
        )

    embed.set_footer(text="Sirius RP • Waffenschein-Log")

    try:
        await channel.send(embed=embed)
    except Exception as e:
        print(f"❌ Fehler beim Waffenschein-Logging: {e}")


async def waffenschein_update_application_message(
    application: dict,
    *,
    status_text: str = None,
    color: discord.Color = None,
    disable_buttons: bool = False,
    button_label: str = None
):
    """Aktualisiert die ursprüngliche Bewerbungsnachricht."""
    channel_id = application.get("application_channel_id") or WAFFENSCHEIN_Bewerbung_KANAL_ID
    message_id = application.get("application_message_id")

    if not message_id:
        return False

    try:
        channel = bot.get_channel(int(channel_id))
        if channel is None:
            channel = await bot.fetch_channel(int(channel_id))
        message = await channel.fetch_message(int(message_id))
        if not message.embeds:
            return False

        embed = message.embeds[0].copy()
        if color is not None:
            embed.color = color

        description = embed.description or ""
        description = re.sub(r"\n\*\*Status:\*\*[^\n]*", "", description, flags=re.IGNORECASE).rstrip()
        if status_text:
            description += f"\n**Status:** {status_text}"
        embed.description = description

        view = None
        if disable_buttons:
            view = WaffenscheinApplicationView()
            for item in view.children:
                if isinstance(item, ui.Button):
                    item.disabled = True
                    if button_label and item.custom_id == "waffenschein_ticket_open":
                        item.label = button_label
                        item.emoji = "✅"

        await message.edit(embed=embed, view=view)
        return True
    except discord.NotFound:
        return False
    except Exception as e:
        print(f"❌ Fehler beim Aktualisieren der Waffenschein-Bewerbung: {e}")
        return False


async def waffenschein_find_ticket_by_exact_name(guild: discord.Guild, application: dict):
    """Findet ein vorhandenes Ticket über den eindeutigen Ticketnamen."""
    license_part = "gross" if application.get("license_key") == "gross" else "klein"
    user_id = str(application.get("user_id", ""))
    expected_name = f"waffenschein-{license_part}-{user_id[-6:]}"
    for channel in guild.text_channels:
        if channel.name == expected_name:
            return channel
    return None


async def waffenschein_finish_application(user: discord.User, application: dict):
    """Postet die fertige Bewerbung im Bewerbungs-Kanal."""
    channel = bot.get_channel(WAFFENSCHEIN_Bewerbung_KANAL_ID)

    if channel is None:
        try:
            channel = await bot.fetch_channel(WAFFENSCHEIN_Bewerbung_KANAL_ID)
        except Exception:
            return False

    timestamp = int(application.get("completed_at", time.time()))

    embed = discord.Embed(
        title=f"🛡️ Neue Waffenschein-Bewerbung — {application['lizenz']}",
        description=(
            f"**Bewerber:** {user.mention}\n"
            f"**Benutzername:** `{application['username']}`\n"
            f"**Lizenz:** **{application['lizenz']}**\n"
            f"**Bewerbung abgeschickt:** <t:{timestamp}:F>\n"
            f"**Status:** 🟡 Offen"
        ),
        color=discord.Color.yellow()
    )

    embed.add_field(
        name="Bewerbungs-ID",
        value=f"`{application['id']}`",
        inline=False
    )

    for index, (question, answer) in enumerate(
        zip(application["fragen"], application["antworten"]),
        start=1
    ):
        answer = str(answer)
        if len(answer) > 900:
            answer = answer[:897] + "..."

        embed.add_field(
            name=f"{index}. Frage",
            value=f"**{question}**\n> {answer}",
            inline=False
        )

    embed.set_footer(text="Sirius RP • Waffenschein-Behörde")

    message = await channel.send(
        content=f"<@&{WAFFENSCHEIN_BEARBEITUNG_ROLLE_ID}>",
        embed=embed,
        view=WaffenscheinApplicationView(),
        allowed_mentions=discord.AllowedMentions(
            roles=True,
            users=False,
            everyone=False
        )
    )

    # Nachricht dauerhaft mit der Bewerbung verknüpfen.
    application["application_message_id"] = message.id
    application["application_channel_id"] = channel.id
    save_waffenschein_data()

    return True


class WaffenscheinSelect(ui.Select):
    def __init__(self):
        options = [
            discord.SelectOption(
                label="Großer Waffenschein",
                value="gross",
                emoji="🧨",
                description="Streng regulierter Waffenschein für besondere RP-Situationen."
            ),
            discord.SelectOption(
                label="Kleiner Waffenschein",
                value="klein",
                emoji="🔫",
                description="Waffenschein für den zivilen Selbstschutz."
            )
        ]

        super().__init__(
            placeholder="Wähle den Waffenschein aus...",
            min_values=1,
            max_values=1,
            options=options,
            custom_id="waffenschein_lizenz_auswahl"
        )

    async def callback(self, interaction: discord.Interaction):
        license_key = self.values[0]

        # Nur derselbe Waffenschein darf nicht erneut beantragt werden.
        # Der jeweils andere Waffenschein darf trotz vorhandener Lizenz
        # beantragt werden.
        if waffenschein_user_has_specific_license(
            interaction.user,
            license_key
        ):
            vorhandener = (
                "Großen Waffenschein"
                if license_key == "gross"
                else "Kleinen Waffenschein"
            )
            await interaction.response.send_message(
                f"❌ Du besitzt bereits den **{vorhandener}**. "
                "Diesen kannst du nicht erneut beantragen. "
                "Den jeweils anderen Waffenschein kannst du weiterhin beantragen.",
                ephemeral=True
            )
            return

        active = waffenschein_user_has_active_application(interaction.user.id)
        if active:
            await interaction.response.send_message(
                "❌ Du hast bereits eine aktive Waffenschein-Bewerbung. "
                "Du kannst erst wieder eine neue Bewerbung starten, wenn die aktuelle "
                "Bewerbung abgeschlossen, abgelehnt oder abgebrochen wurde.",
                ephemeral=True
            )
            return

        lizenz = (
            "Großer Waffenschein"
            if license_key == "gross"
            else "Kleiner Waffenschein"
        )

        await interaction.response.send_message(
            f"Du hast **{lizenz}** ausgewählt.\n\n"
            "Möchtest du die Bewerbung wirklich starten?\n"
            "Die Fragen werden dir anschließend **privat per DM** gestellt.",
            view=WaffenscheinStartView(license_key),
            ephemeral=True
        )


class WaffenscheinView(ui.View):
    def __init__(self):
        super().__init__(timeout=None)
        self.add_item(WaffenscheinSelect())


class WaffenscheinStartView(ui.View):
    def __init__(self, license_key: str):
        super().__init__(timeout=300)
        self.license_key = license_key

    @ui.button(
        label="Bewerbung starten",
        style=discord.ButtonStyle.success,
        emoji="✅"
    )
    async def start(
        self,
        interaction: discord.Interaction,
        button: ui.Button
    ):
        # Erneute Prüfung direkt vor dem Start:
        # Nur derselbe Waffenschein blockiert die Bewerbung.
        if waffenschein_user_has_specific_license(
            interaction.user,
            self.license_key
        ):
            vorhandener = (
                "Großen Waffenschein"
                if self.license_key == "gross"
                else "Kleinen Waffenschein"
            )
            await interaction.response.send_message(
                f"❌ Du besitzt bereits den **{vorhandener}**. "
                "Diesen kannst du nicht erneut beantragen.",
                ephemeral=True
            )
            return

        active = waffenschein_user_has_active_application(interaction.user.id)

        if active:
            await interaction.response.send_message(
                "❌ Du hast bereits eine aktive Bewerbung.",
                ephemeral=True
            )
            return

        fragen = (
            GROSS_WAFFENSCHEIN_FRAGEN
            if self.license_key == "gross"
            else KLEIN_WAFFENSCHEIN_FRAGEN
        )

        application_id = f"{interaction.user.id}-{int(time.time() * 1000)}"

        application = {
            "id": application_id,
            "user_id": interaction.user.id,
            "username": str(interaction.user),
            "license_key": self.license_key,
            "lizenz": (
                "Großer Waffenschein"
                if self.license_key == "gross"
                else "Kleiner Waffenschein"
            ),
            "fragen": list(fragen),
            "antworten": [],
            "question_index": 0,
            "status": "dm_started",
            "started_at": time.time(),
            "completed_at": None,
            "ticket_channel_id": None
        }

        waffenschein_bewerbungen[application_id] = application
        save_waffenschein_data()

        try:
            dm = await interaction.user.create_dm()
            await dm.send(
                embed=discord.Embed(
                    title="🛡️ Waffenschein-Bewerbung",
                    description=(
                        f"Deine Bewerbung für den **{application['lizenz']}** beginnt jetzt.\n\n"
                        "Ich stelle dir die Fragen **nacheinander**. "
                        "Bitte antworte jeweils direkt auf meine Nachricht.\n\n"
                        "Du kannst jederzeit `abbrechen` schreiben, um die Bewerbung zu beenden."
                    ),
                    color=discord.Color.red()
                )
            )

            await dm.send(
                f"**Frage 1 von {len(fragen)}:**\n\n{fragen[0]}"
            )

        except discord.Forbidden:
            waffenschein_bewerbungen.pop(application_id, None)
            save_waffenschein_data()

            await interaction.response.send_message(
                "❌ Ich konnte dir keine DM schicken. "
                "Bitte aktiviere deine Direktnachrichten für diesen Server und versuche es erneut.",
                ephemeral=True
            )
            return

        await interaction.response.send_message(
            "✅ Die Bewerbung wurde gestartet. Ich habe dir die erste Frage per DM geschickt.",
            ephemeral=True
        )


class WaffenscheinApplicationView(ui.View):
    def __init__(self):
        super().__init__(timeout=None)

    @ui.button(
        label="Ticket Öffnen",
        style=discord.ButtonStyle.primary,
        emoji="🎫",
        custom_id="waffenschein_ticket_open"
    )
    async def ticket_open(
        self,
        interaction: discord.Interaction,
        button: ui.Button
    ):
        if not has_role(
            interaction.user,
            WAFFENSCHEIN_BEARBEITUNG_ROLLE_ID
        ):
            await interaction.response.send_message(
                "❌ Nur Mitglieder der Waffenschein-Behörde dürfen ein Ticket öffnen.",
                ephemeral=True
            )
            return

        guild = interaction.guild
        if guild is None:
            await interaction.response.send_message(
                "❌ Dieser Button kann nur auf dem Server benutzt werden.",
                ephemeral=True
            )
            return

        application = await waffenschein_resolve_application_from_message(
            interaction.message
        )

        if not application:
            await interaction.response.send_message(
                "❌ Die Bewerbung konnte nicht gefunden werden.",
                ephemeral=True
            )
            return

        # Nur ein Ticket-Erstellungsvorgang darf gleichzeitig laufen.
        # Dadurch kann ein doppelter Button-Callback nicht zwei Channels erzeugen.
        await waffenschein_ticket_creation_lock.acquire()
        try:
            # Eine abgelehnte oder bereits bezahlte Bewerbung kann nicht mehr geöffnet werden.
            if application.get("status") == "rejected":
                await interaction.response.send_message(
                    "❌ Diese Bewerbung wurde bereits abgelehnt.",
                    ephemeral=True
                )
                return

            if application.get("status") == "paid":
                if waffenschein_payment_is_confirmed(application):
                    await interaction.response.send_message(
                        "❌ Diese Bewerbung wurde bereits abgeschlossen und bezahlt.",
                        ephemeral=True
                    )
                    return

                # Alter/stale Status: Noch keine echte Zahlung bestätigt.
                # Bewerbung wieder auf offen setzen und Ticket normal erstellen.
                waffenschein_repair_stale_paid_status(application)

            # WICHTIG: Hier wird NICHT mehr geprüft, ob der Bewerber irgendeinen
            # Waffenschein besitzt. Ein vorhandener kleiner Schein darf z.B. die
            # Bewerbung für den großen Schein nicht blockieren und umgekehrt.
            # Entscheidend ist nur der Status dieser konkreten Bewerbung.

            application_id = application["id"]

            # Bereits gespeichertes Ticket bevorzugen.
            if application.get("ticket_channel_id"):
                existing_ticket = guild.get_channel(
                    int(application["ticket_channel_id"])
                )
                if existing_ticket:
                    ticket_link = f"https://discord.com/channels/{guild.id}/{existing_ticket.id}"
                    button.disabled = True
                    button.label = "Ticket bereits geöffnet"
                    button.emoji = "✅"
                    await interaction.message.edit(view=self)
                    await interaction.response.send_message(
                        "ℹ️ **Das Ticket wurde bereits eröffnet.**\n"
                        f"🎫 [Zum Ticket](<{ticket_link}>)",
                        ephemeral=True
                    )
                    return

                application["ticket_channel_id"] = None
                if application.get("status") == "ticket_open":
                    application["status"] = "pending"
                save_waffenschein_data()

            if application.get("status") == "ticket_creating":
                existing_ticket = await waffenschein_find_existing_ticket(
                    guild,
                    int(application["user_id"]),
                    application["license_key"]
                )
                if existing_ticket:
                    application["ticket_channel_id"] = existing_ticket.id
                    application["status"] = "ticket_open"
                    save_waffenschein_data()
                    button.disabled = True
                    button.label = "Ticket bereits geöffnet"
                    button.emoji = "✅"
                    await interaction.message.edit(view=self)
                    ticket_link = f"https://discord.com/channels/{guild.id}/{existing_ticket.id}"
                    await interaction.response.send_message(
                        "ℹ️ **Das Ticket wurde bereits eröffnet.**\n"
                        f"🎫 [Zum Ticket](<{ticket_link}>)",
                        ephemeral=True
                    )
                    return
                # Falls kein Ticket mehr existiert, darf die Erstellung erneut versucht werden.
                application["status"] = "pending"
                save_waffenschein_data()

            if application.get("status") != "pending":
                await interaction.response.send_message(
                    "❌ Diese Bewerbung ist aktuell nicht für ein Ticket freigegeben.",
                    ephemeral=True
                )
                return

            if application_id in waffenschein_ticket_locks:
                existing_ticket = await waffenschein_find_existing_ticket(
                    guild,
                    int(application["user_id"]),
                    application["license_key"]
                )
                if existing_ticket:
                    application["ticket_channel_id"] = existing_ticket.id
                    application["status"] = "ticket_open"
                    save_waffenschein_data()
                    button.disabled = True
                    button.label = "Ticket bereits geöffnet"
                    button.emoji = "✅"
                    await interaction.message.edit(view=self)
                    ticket_link = f"https://discord.com/channels/{guild.id}/{existing_ticket.id}"
                    await interaction.response.send_message(
                        "ℹ️ **Das Ticket wurde bereits eröffnet.**\n"
                        f"🎫 [Zum Ticket](<{ticket_link}>)",
                        ephemeral=True
                    )
                    return

                await interaction.response.send_message(
                    "⏳ Das Ticket wird gerade bereits erstellt. Bitte einen Moment warten.",
                    ephemeral=True
                )
                return

            category_id = (
                GROSSER_WAFFENSCHEIN_KATEGORIE_ID
                if application["license_key"] == "gross"
                else KLEINER_WAFFENSCHEIN_KATEGORIE_ID
            )
            category = guild.get_channel(category_id)
            authority_role = guild.get_role(WAFFENSCHEIN_BEARBEITUNG_ROLLE_ID)

            if category is None:
                await interaction.response.send_message(
                    "❌ Die konfigurierte Ticket-Kategorie wurde nicht gefunden.",
                    ephemeral=True
                )
                return

            if authority_role is None:
                await interaction.response.send_message(
                    "❌ Die Waffenschein-Behördenrolle wurde nicht gefunden.",
                    ephemeral=True
                )
                return

            try:
                applicant = guild.get_member(int(application["user_id"]))
                if applicant is None:
                    applicant = await guild.fetch_member(int(application["user_id"]))
            except Exception:
                applicant = None

            # Exakte Prüfung direkt vor create_text_channel.
            existing_ticket = await waffenschein_find_existing_ticket(
                guild,
                int(application["user_id"]),
                application["license_key"]
            )
            if existing_ticket:
                application["ticket_channel_id"] = existing_ticket.id
                application["status"] = "ticket_open"
                save_waffenschein_data()
                button.disabled = True
                button.label = "Ticket bereits geöffnet"
                button.emoji = "✅"
                await interaction.message.edit(view=self)
                ticket_link = f"https://discord.com/channels/{guild.id}/{existing_ticket.id}"
                await interaction.response.send_message(
                    "ℹ️ **Das Ticket wurde bereits eröffnet.**\n"
                    f"🎫 [Zum Ticket](<{ticket_link}>)",
                    ephemeral=True
                )
                return

            waffenschein_ticket_locks.add(application_id)

            try:
                application["status"] = "ticket_creating"
                save_waffenschein_data()

                # Zweite Prüfung nach dem Lock, um Race Conditions zu vermeiden.
                existing_ticket = await waffenschein_find_existing_ticket(
                    guild,
                    int(application["user_id"]),
                    application["license_key"]
                )
                if existing_ticket:
                    application["ticket_channel_id"] = existing_ticket.id
                    application["status"] = "ticket_open"
                    save_waffenschein_data()
                    button.disabled = True
                    button.label = "Ticket bereits geöffnet"
                    button.emoji = "✅"
                    await interaction.message.edit(view=self)
                    ticket_link = f"https://discord.com/channels/{guild.id}/{existing_ticket.id}"
                    await interaction.response.send_message(
                        "ℹ️ **Das Ticket wurde bereits eröffnet.**\n"
                        f"🎫 [Zum Ticket](<{ticket_link}>)",
                        ephemeral=True
                    )
                    return

                overwrites = {
                    guild.default_role: discord.PermissionOverwrite(view_channel=False),
                    authority_role: discord.PermissionOverwrite(
                        view_channel=True,
                        send_messages=True,
                        read_message_history=True,
                        embed_links=True,
                        attach_files=True
                    )
                }

                if applicant:
                    overwrites[applicant] = discord.PermissionOverwrite(
                        view_channel=True,
                        send_messages=True,
                        read_message_history=True,
                        embed_links=True,
                        attach_files=True
                    )

                channel_name = (
                    f"waffenschein-{'gross' if application['license_key'] == 'gross' else 'klein'}-"
                    f"{str(application['user_id'])[-6:]}"
                )

                ticket = await guild.create_text_channel(
                    name=channel_name,
                    category=category,
                    overwrites=overwrites,
                    topic=(
                        f"Waffenschein-Bewerbung {application_id} | "
                        f"User {application['user_id']}"
                    )
                )

                applicant_mention = applicant.mention if applicant else f"<@{application['user_id']}>"
                applicant_name = applicant.display_name if applicant else application.get("username", "Bewerber")

                annahme_embed = discord.Embed(
                    title="🛡️ Waffenschein-Antrag angenommen",
                    description=(
                        f"**{applicant_name}** hat einen **{application['lizenz']}** beantragt.\n\n"
                        "Bitte bezahle jetzt nur noch den Waffenschein ab. "
                        "Nach bestätigter Zahlung wird dir die entsprechende Rolle vergeben."
                    ),
                    color=discord.Color.blue()
                )

                # Nur der Bewerber wird gepingt – niemals die Behördenrolle.
                await ticket.send(
                    content=applicant_mention,
                    embed=annahme_embed,
                    view=WaffenscheinPaidView(),
                    allowed_mentions=discord.AllowedMentions(
                        users=True,
                        roles=False,
                        everyone=False,
                        replied_user=False
                    )
                )

                preis = "6000€" if application["license_key"] == "gross" else "3000€"
                zahlung_embed = discord.Embed(
                    title="💶 Bezahlen",
                    description=(
                        f"**Bitte bezahle {preis} an SiriusRPManagment.**\n\n"
                        "***⚠️ Vergesse das Beweisbild/Video nicht! Ohne Beweis = Kein Waffenschein ⚠️***"
                    ),
                    color=discord.Color.red()
                )
                await ticket.send(embed=zahlung_embed)

                application["ticket_channel_id"] = ticket.id
                application["ticket_opened_at"] = time.time()
                application["status"] = "ticket_open"
                save_waffenschein_data()

                button.disabled = True
                button.label = "Ticket bereits geöffnet"
                button.emoji = "✅"
                await interaction.message.edit(view=self)

                ticket_link = f"https://discord.com/channels/{guild.id}/{ticket.id}"
                await interaction.response.send_message(
                    "✅ **Das Ticket wurde erfolgreich eröffnet!**\n"
                    f"🎫 [Zum Ticket](<{ticket_link}>)",
                    ephemeral=True
                )

                await waffenschein_log(
                    application,
                    "TICKET ERÖFFNET",
                    moderator=interaction.user,
                    ticket_channel=ticket,
                    extra=f"Ticket für **{application['lizenz']}** erstellt.",
                    color=discord.Color.blue()
                )

            except Exception as e:
                application["status"] = "pending"
                application["ticket_channel_id"] = None
                save_waffenschein_data()
                print(f"❌ Fehler beim Erstellen des Waffenschein-Tickets: {e}")

                if not interaction.response.is_done():
                    await interaction.response.send_message(
                        "❌ Beim Erstellen des Tickets ist ein Fehler aufgetreten. Bitte versuche es erneut.",
                        ephemeral=True
                    )
                else:
                    await interaction.followup.send(
                        "❌ Beim Erstellen des Tickets ist ein Fehler aufgetreten.",
                        ephemeral=True
                    )
            finally:
                waffenschein_ticket_locks.discard(application_id)
        finally:
            waffenschein_ticket_creation_lock.release()

    @ui.button(
        label="Ablehnen",
        style=discord.ButtonStyle.danger,
        emoji="❌",
        custom_id="waffenschein_application_reject"
    )
    async def reject(
        self,
        interaction: discord.Interaction,
        button: ui.Button
    ):
        if not has_role(
            interaction.user,
            WAFFENSCHEIN_BEARBEITUNG_ROLLE_ID
        ):
            await interaction.response.send_message(
                "❌ Nur Mitglieder der Waffenschein-Behörde dürfen Bewerbungen ablehnen.",
                ephemeral=True
            )
            return

        application = await waffenschein_resolve_application_from_message(
            interaction.message
        )

        if not application:
            await interaction.response.send_message(
                "❌ Die Bewerbung konnte nicht gefunden werden.",
                ephemeral=True
            )
            return

        if application.get("status") == "rejected":
            await interaction.response.send_message(
                "❌ **Die Bewerbung wurde bereits abgelehnt.**",
                ephemeral=True
            )
            return

        if application.get("status") == "paid":
            await interaction.response.send_message(
                "❌ Diese Bewerbung ist bereits abgeschlossen und bezahlt.",
                ephemeral=True
            )
            return

        if application.get("ticket_channel_id") or application.get("status") in {"ticket_creating", "ticket_open"}:
            await interaction.response.send_message(
                "❌ Diese Bewerbung hat bereits ein geöffnetes Ticket und kann deshalb nicht mehr abgelehnt werden.",
                ephemeral=True
            )
            return

        if application.get("status") != "pending":
            await interaction.response.send_message(
                "❌ Diese Bewerbung kann aktuell nicht abgelehnt werden.",
                ephemeral=True
            )
            return

        # Status zuerst speichern, damit ein zweiter Klick/Race-Condition sofort blockiert wird.
        application["status"] = "rejected"
        application["rejected_at"] = time.time()
        application["rejected_by"] = interaction.user.id
        application["ticket_channel_id"] = None
        save_waffenschein_data()

        embed = interaction.message.embeds[0].copy()
        embed.color = discord.Color.red()

        clean_description = re.sub(
            r"\n\*\*Status:\*\*[^\n]*",
            "",
            embed.description or "",
            flags=re.IGNORECASE
        ).rstrip()
        embed.description = (
            f"{clean_description}\n"
            "**Status:** 🔴 Abgelehnt\n\n"
            "━━━━━━━━━━━━━━━━━━━━\n"
            "❌ **BEWERBUNG ABGELEHNT**\n"
            f"**Abgelehnt von:** {interaction.user.mention}\n"
            f"**Zeitpunkt:** <t:{int(application['rejected_at'])}:F>"
        )

        # Beide Buttons dauerhaft deaktivieren.
        for item in self.children:
            if isinstance(item, ui.Button):
                item.disabled = True

        # Nur die Ablehnen-Beschriftung ändern.
        button.label = "Bewerbung abgelehnt"
        button.emoji = "❌"

        await interaction.response.edit_message(
            embed=embed,
            view=self
        )

        # Bewerber bekommt zusätzlich eine private DM.
        await waffenschein_send_dm_status(application, "rejected")

        await waffenschein_log(
            application,
            "BEWERBUNG ABGELEHNT",
            moderator=interaction.user,
            extra="Die Bewerbung wurde abgelehnt. Der Bewerber wurde privat informiert.",
            color=discord.Color.red()
        )


class WaffenscheinPaidView(ui.View):
    def __init__(self):
        super().__init__(timeout=None)

    @ui.button(
        label="Waffenschein Abbezahlt",
        style=discord.ButtonStyle.success,
        emoji="💶",
        custom_id="waffenschein_paid"
    )
    async def paid(
        self,
        interaction: discord.Interaction,
        button: ui.Button
    ):
        if not has_role(
            interaction.user,
            WAFFENSCHEIN_BEARBEITUNG_ROLLE_ID
        ):
            await interaction.response.send_message(
                "❌ Nur Mitglieder der Waffenschein-Behörde dürfen die Zahlung bestätigen.",
                ephemeral=True
            )
            return

        application = None

        # Das Ticket-Topic enthält die Bewerbungs-ID und funktioniert
        # dadurch auch nach einem Bot-Neustart.
        topic = getattr(interaction.channel, "topic", "") or ""
        match = re.search(
            r"Waffenschein-Bewerbung\s+([^ ]+)",
            topic
        )

        if match:
            application = waffenschein_bewerbungen.get(match.group(1))

        # Fallback: Falls ein älteres Ticket kein korrektes Topic besitzt,
        # suchen wir die Bewerbung zusätzlich über die gespeicherte Ticket-ID.
        if not application:
            channel_id = getattr(interaction.channel, "id", None)
            for stored_application in waffenschein_bewerbungen.values():
                if int(stored_application.get("ticket_channel_id") or 0) == int(channel_id or 0):
                    application = stored_application
                    break

        # Letzter Fallback: Bewerbungs-ID oder Benutzer-ID aus dem
        # Ticketnamen. Damit funktionieren auch ältere Tickets.
        if not application:
            channel_name = getattr(interaction.channel, "name", "") or ""

            # Neue Tickets heißen z.B.:
            # waffenschein-gross-123456
            # waffenschein-klein-123456
            suffix_match = re.search(
                r"waffenschein-(?:gross|klein)-([0-9]+)$",
                channel_name,
                re.IGNORECASE
            )

            if suffix_match:
                suffix = suffix_match.group(1)

                candidates = [
                    stored_application
                    for stored_application in waffenschein_bewerbungen.values()
                    if str(stored_application.get("user_id", "")).endswith(suffix)
                ]

                # Ein Ticket mit bereits gesetzter ticket_channel_id
                # hat immer Vorrang.
                for stored_application in candidates:
                    if int(stored_application.get("ticket_channel_id") or 0) == int(interaction.channel.id):
                        application = stored_application
                        break

                if not application:
                    active_candidates = [
                        candidate
                        for candidate in candidates
                        if candidate.get("status") in {"pending", "ticket_creating", "ticket_open"}
                    ]
                    if active_candidates:
                        application = max(
                            active_candidates,
                            key=lambda item: float(item.get("completed_at") or item.get("started_at") or 0)
                        )

            # Zusätzlich nach der Bewerbungs-ID suchen.
            if not application:
                for application_id, stored_application in waffenschein_bewerbungen.items():
                    if str(application_id) in channel_name:
                        application = stored_application
                        break

        if not application:
            # Als weiterer Fallback: User-ID aus dem Ticket-Topic.
            user_match = re.search(
                r"User\s+([0-9]+)",
                topic,
                re.IGNORECASE
            )

            ticket_user_id = (
                int(user_match.group(1))
                if user_match
                else None
            )

            if ticket_user_id:
                candidates = [
                    stored_application
                    for stored_application in waffenschein_bewerbungen.values()
                    if int(stored_application.get("user_id", 0)) == ticket_user_id
                ]
                if candidates:
                    # Bereits mit diesem Ticket verknüpfte Bewerbung bevorzugen.
                    for candidate in candidates:
                        if int(candidate.get("ticket_channel_id") or 0) == int(interaction.channel.id):
                            application = candidate
                            break

                    if not application:
                        application = candidates[-1]

            # Letzter Fallback für Tickets, deren JSON-Eintrag fehlt:
            # license_key direkt aus dem Kanalnamen lesen.
            if not application and ticket_user_id:
                channel_name = (
                    getattr(interaction.channel, "name", "") or ""
                ).lower()

                if channel_name.startswith("waffenschein-gross-"):
                    license_key = "gross"
                elif channel_name.startswith("waffenschein-klein-"):
                    license_key = "klein"
                else:
                    license_key = None

                if license_key:
                    recovered_id = f"legacy-ticket-{interaction.channel.id}"
                    application = waffenschein_make_fallback_application(
                        ticket_user_id,
                        license_key,
                        recovered_id
                    )
                    application["ticket_channel_id"] = interaction.channel.id
                    waffenschein_bewerbungen[recovered_id] = application
                    save_waffenschein_data()

        if not application:
            await interaction.response.send_message(
                "❌ Der Bewerber dieses Tickets konnte nicht ermittelt werden.",
                ephemeral=True
            )
            return

        if application.get("status") == "rejected":
            await interaction.response.send_message(
                "❌ Diese Bewerbung wurde abgelehnt.",
                ephemeral=True
            )
            return

        if application.get("status") == "paid":
            if waffenschein_payment_is_confirmed(application):
                await interaction.response.send_message(
                    "❌ Dieser Waffenschein wurde bereits als bezahlt markiert.",
                    ephemeral=True
                )
                return

            # Kein echter Zahlungsnachweis vorhanden -> stale Status reparieren
            # und die Zahlung normal verarbeiten.
            waffenschein_repair_stale_paid_status(application)

        guild = interaction.guild
        if guild is None:
            await interaction.response.send_message(
                "❌ Dieser Button kann nur auf dem Server benutzt werden.",
                ephemeral=True
            )
            return

        applicant = guild.get_member(
            int(application["user_id"])
        )

        if applicant is None:
            try:
                applicant = await guild.fetch_member(
                    int(application["user_id"])
                )
            except Exception:
                applicant = None

        if applicant is None:
            await interaction.response.send_message(
                "❌ Der Bewerber konnte nicht gefunden werden. "
                "Das Ticket wurde deshalb noch nicht geschlossen.",
                ephemeral=True
            )
            return

        role_id = (
            GROSSER_WAFFENSCHEIN_ROLLE_ID
            if application["license_key"] == "gross"
            else KLEINER_WAFFENSCHEIN_ROLLE_ID
        )

        role = guild.get_role(role_id)

        if role is None:
            await interaction.response.send_message(
                "❌ Die passende Waffenschein-Rolle wurde nicht gefunden.",
                ephemeral=True
            )
            return

        try:
            await applicant.add_roles(
                role,
                reason=(
                    f"Waffenschein bezahlt | "
                    f"Bewerbung {application['id']}"
                )
            )
        except discord.Forbidden:
            await interaction.response.send_message(
                "❌ Ich kann dem Bewerber die Rolle nicht geben. "
                "Bitte überprüfe die Rollenposition des Bots.",
                ephemeral=True
            )
            return
        except Exception as e:
            await interaction.response.send_message(
                f"❌ Die Rolle konnte nicht vergeben werden: `{e}`",
                ephemeral=True
            )
            return

        ticket_channel = interaction.channel

        application["status"] = "paid"
        application["paid_at"] = time.time()
        application["paid_by"] = interaction.user.id
        application["paid_role_id"] = role.id
        application["ticket_closed_at"] = time.time()
        save_waffenschein_data()

        # Bewerbung im Bewerbungs-Kanal grün markieren und beide Buttons deaktivieren.
        await waffenschein_update_application_message(
            application,
            status_text="🟢 Bezahlt / Waffenschein erteilt",
            color=discord.Color.green(),
            disable_buttons=True,
            button_label="Bewerbung abgeschlossen"
        )

        await waffenschein_log(
            application,
            "WAFFENSCHEIN BEZAHLT",
            moderator=interaction.user,
            ticket_channel=ticket_channel,
            extra=(
                f"Der Waffenschein wurde als bezahlt bestätigt.\n"
                f"**Vergebene Rolle:** {role.mention}\n"
                "Das Ticket wird anschließend geschlossen und gelöscht."
            ),
            color=discord.Color.green()
        )

        # Bewerber bekommt nach erfolgreicher Zahlung eine private DM.
        await waffenschein_send_dm_status(application, "paid")

        try:
            # Bewusst schlicht gehalten: genau die gewünschte Meldung,
            # bevor der Channel gelöscht wird.
            await interaction.response.send_message(
                "🗑️ **Das Ticket wird jetzt geschlossen.**"
            )
        except Exception:
            pass

        # Kurze Verzögerung, damit die Nachricht noch sichtbar wird.
        await asyncio.sleep(2)

        try:
            await ticket_channel.delete(
                reason=(
                    f"Waffenschein bezahlt / Ticket geschlossen | "
                    f"Bewerbung {application['id']}"
                )
            )
        except discord.NotFound:
            pass
        except discord.Forbidden:
            await waffenschein_log(
                application,
                "TICKET KONNTE NICHT GELÖSCHT WERDEN",
                moderator=interaction.user,
                extra=(
                    "Die Waffenschein-Rolle wurde vergeben, "
                    "aber Discord hat das Löschen des Ticket-Channels verweigert."
                ),
                color=discord.Color.red()
            )
        except Exception as e:
            print(
                f"❌ Fehler beim Löschen des Waffenschein-Tickets: {e}"
            )


async def waffenschein_process_dm(message: discord.Message):
    """Verarbeitet Antworten auf laufende Waffenschein-Bewerbungen."""
    application = waffenschein_user_has_active_application(
        message.author.id
    )

    if not application:
        return False

    if application.get("status") not in {
        "dm_started",
        "pending"
    }:
        return False

    content = message.content.strip()

    if content.lower() in {
        "abbrechen",
        "abbruch",
        "cancel",
        "stop"
    }:
        application["status"] = "cancelled"
        application["cancelled_at"] = time.time()
        save_waffenschein_data()

        await message.channel.send(
            embed=discord.Embed(
                title="❌ Bewerbung abgebrochen",
                description=(
                    "Deine Waffenschein-Bewerbung wurde abgebrochen.\n\n"
                    "Du kannst später eine neue Bewerbung starten."
                ),
                color=discord.Color.red()
            )
        )

        await waffenschein_log(
            application,
            "BEWERBUNG ABGEBROCHEN",
            extra="Der Bewerber hat die Bewerbung per DM abgebrochen.",
            color=discord.Color.orange()
        )

        return True

    index = int(application.get("question_index", 0))
    fragen = application["fragen"]

    if index >= len(fragen):
        return True

    # Antwort speichern.
    application["antworten"].append(content)
    index += 1
    application["question_index"] = index

    if index >= len(fragen):
        application["status"] = "pending"
        application["completed_at"] = time.time()
        save_waffenschein_data()

        await message.channel.send(
            embed=discord.Embed(
                title="✅ Bewerbung abgeschickt",
                description=(
                    "Vielen Dank! Du hast alle Fragen beantwortet.\n\n"
                    "Deine Bewerbung wurde an die Waffenschein-Behörde "
                    "weitergeleitet. Du erhältst eine Rückmeldung, sobald "
                    "die Behörde deine Bewerbung bearbeitet."
                ),
                color=discord.Color.green()
            )
        )

        try:
            await waffenschein_finish_application(
                message.author,
                application
            )
        except Exception as e:
            print(
                f"❌ Fehler beim Posten der Waffenschein-Bewerbung: {e}"
            )

        return True

    save_waffenschein_data()

    await message.channel.send(
        f"**Frage {index + 1} von {len(fragen)}:**\n\n"
        f"{fragen[index]}"
    )

    return True


# ==========================================
# HELPER FUNCTIONS & TEAMLISTE LOGIK
# ==========================================
async def send_private_protocol(leader_user: discord.User, protocol_content: str):
    try:
        await leader_user.send(
            f"📋 **Hier ist das Protokoll deiner letzten Sitzung:**\n\n{protocol_content}"
        )
        print("Protokoll erfolgreich privat zugestellt.")
    except discord.Forbidden:
        print("Fehler: Der Gesprächsleiter hat DMs deaktiviert.")

async def send_moderation_log(guild: discord.Guild, action_type: str, roblox_name: str, grund: str, dauer: str, moderator: str, avatar_url: str = None):
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

def formatiere_liste(mitglieder):
    if not mitglieder:
        return ""

    text = ""
    for i, member in enumerate(mitglieder):
        if i == len(mitglieder) - 1:
            text += f"└ {member.mention}\n"
        else:
            text += f"├ {member.mention}\n"
    return text

async def generiere_team_embeds(guild: discord.Guild):
    embeds = []

    leitung_ids = [
        1527739219907449022,
        1527349818068959301,
        1527349818068959300,
        1527349818068959299,
        1527349818068959298,
        1527349818068959297,
        1527349818068959296,
        1527349818068959295,
    ]
    embed_leitung = discord.Embed(
        title="Teamliste | Sirius RP 📰", color=discord.Color.blue()
    )
    content_leitung = "## ▬▬ 👑Leitungsteam ▬▬\n"
    for r_id in leitung_ids:
        role = guild.get_role(r_id)
        if role:
            gueltige_mitglieder = []
            for m in role.members:
                user_hauptrollen = [
                    guild.get_role(rid) for rid in HAUPT_ROLLEN if guild.get_role(rid) in m.roles
                ]
                if user_hauptrollen and user_hauptrollen[0] == role:
                    gueltige_mitglieder.append(m)

            content_leitung += f"**{role.name}**\n"
            formatted = formatiere_liste(gueltige_mitglieder)
            if formatted:
                content_leitung += formatted
            content_leitung += "\n"
    embed_leitung.description = content_leitung
    embeds.append(embed_leitung)

    fuehrung_ids = [
        1527349818068959293,
        1527349818068959292,
        1527349818031214721,
        1527349818031214720,
        1527349818031214719,
        1527349817875890355,
    ]
    embed_fuehrung = discord.Embed(color=discord.Color.blue())
    content_fuehrung = "## ▬▬ 👨‍💼Führungsteam ▬▬\n"
    for r_id in fuehrung_ids:
        role = guild.get_role(r_id)
        if role:
            gueltige_mitglieder = []
            for m in role.members:
                user_hauptrollen = [
                    guild.get_role(rid) for rid in HAUPT_ROLLEN if guild.get_role(rid) in m.roles
                ]
                if user_hauptrollen and user_hauptrollen[0] == role:
                    gueltige_mitglieder.append(m)

            content_fuehrung += f"**{role.name}**\n"
            formatted = formatiere_liste(gueltige_mitglieder)
            if formatted:
                content_fuehrung += formatted
            content_fuehrung += "\n"
    embed_fuehrung.description = content_fuehrung
    embeds.append(embed_fuehrung)

    admin_ids = [
        1527349817800523855,
        1527349817800523854,
        1527349817800523853,
    ]
    embed_admin = discord.Embed(color=discord.Color.blue())
    content_admin = "## ▬▬ ⚙️Admin-Team ▬▬\n"
    for r_id in admin_ids:
        role = guild.get_role(r_id)
        if role:
            gueltige_mitglieder = []
            for m in role.members:
                user_hauptrollen = [
                    guild.get_role(rid) for rid in HAUPT_ROLLEN if guild.get_role(rid) in m.roles
                ]
                if user_hauptrollen and user_hauptrollen[0] == role:
                    gueltige_mitglieder.append(m)

            content_admin += f"**{role.name}**\n"
            formatted = formatiere_liste(gueltige_mitglieder)
            if formatted:
                content_admin += formatted
            content_admin += "\n"
    embed_admin.description = content_admin
    embeds.append(embed_admin)

    mod_ids = [1527349817800523851, 1527349817800523850, 1527349817800523849]
    embed_mod = discord.Embed(color=discord.Color.blue())
    content_mod = "## ▬▬ ⚖️Moderations-Team ▬▬\n"
    for r_id in mod_ids:
        role = guild.get_role(r_id)
        if role:
            gueltige_mitglieder = []
            for m in role.members:
                user_hauptrollen = [
                    guild.get_role(rid) for rid in HAUPT_ROLLEN if guild.get_role(rid) in m.roles
                ]
                if user_hauptrollen and user_hauptrollen[0] == role:
                    gueltige_mitglieder.append(m)

            content_mod += f"**{role.name}**\n"
            formatted = formatiere_liste(gueltige_mitglieder)
            if formatted:
                content_mod += formatted
            content_mod += "\n"
    embed_mod.description = content_mod
    embeds.append(embed_mod)

    supp_ids = [
        1527349817800523847,
        1527349817708122191,
        1527349817708122190,
    ]
    embed_supp = discord.Embed(color=discord.Color.blue())
    content_supp = "## ▬▬ 🛡️Support-Team ▬▬\n"
    for r_id in supp_ids:
        role = guild.get_role(r_id)
        if role:
            gueltige_mitglieder = []
            for m in role.members:
                user_hauptrollen = [
                    guild.get_role(rid) for rid in HAUPT_ROLLEN if guild.get_role(rid) in m.roles
                ]
                if user_hauptrollen and user_hauptrollen[0] == role:
                    gueltige_mitglieder.append(m)

            content_supp += f"**{role.name}**\n"
            formatted = formatiere_liste(gueltige_mitglieder)
            if formatted:
                content_supp += formatted
            content_supp += "\n"
    embed_supp.description = content_supp
    embeds.append(embed_supp)

    embed_neben = discord.Embed(color=discord.Color.gold())
    content_neben = "## ▬▬ 🚀Nebenrollen ▬▬\n"
    for r_id in NEBEN_ROLLEN:
        role = guild.get_role(r_id)
        if role:
            content_neben += f"**{role.name}**\n"
            formatted = formatiere_liste(list(role.members))
            if formatted:
                content_neben += formatted
            content_neben += "\n"
    embed_neben.description = content_neben
    embeds.append(embed_neben)

    return embeds

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
# WEITERE KONFIGURATION (IDS & LINKS)
# ==========================================
XP_BOOST_LOCK_ROLLE_ID = 1527349817875890356
XP_GIVE_REMOVE_ROLLE_ID = 1527349818031214718

FEEDBACK_PANEL_KANAL_ID = 1527349829942906995
LOG_KANAL_ID = 1532091859285966868
CALL_ADMIN_KANAL_ID = 1532102652790444123
CALL_ADMIN_TEAM_ROLLE_ID = 1532109458157862932
DIZZY_KANAL_ID = 1527349819742355624
DIZZY_COOLDOWN_SECONDS = 5 * 60
DIZZY_HISTORY_LIMIT = 200
ALLOWED_VOICE_CHANNELS = [1527349830228246701, 1527349830228246702]
LEADERBOARD_KANAL_ID = 1532118592177569822
XP_BOOST_ANNOUNCEMENT_KANAL_ID = 1527677485960007680
EINTRAG_PANEL_KANAL_ID = 1532144498317070586
BAN_BOLO_KANAL_ID = 1532144498317070586

DIZZY_LOG_KANAL_ID = 1532348593573199872
XP_LOG_KANAL_ID = 1532348632412721312
BAN_BOLO_LOG_KANAL_ID = 1532348686385025205
CALL_ADMIN_LOG_KANAL_ID = 1532348723705811016
FEEDBACK_REMOVE_LOG_KANAL_ID = 1536669127891226624

VERIFY_KANAL_ID = 1527404574430855340
UNVERIFIED_ROLLE_ID = 1527404452829466735
VERIFIED_ROLLE_ID = 1527349817586483229

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

DATA_FILE = "bot_database.json"

def load_data():
    if os.path.exists(DATA_FILE):
        try:
            with open(DATA_FILE, "r", encoding="utf-8") as f:
                data = json.load(f)
            loaded_xp = {int(k): int(v) for k, v in data.get("user_xp", {}).items()}
            loaded_dizzy = []
            for item in data.get("dizzy_kontrollen", []):
                if isinstance(item, dict):
                    try:
                        loaded_dizzy.append({"mod_id": int(item["mod_id"]), "target_id": int(item["target_id"]), "message_id": int(item.get("message_id", 0)), "timestamp": float(item.get("timestamp", 0))})
                    except (KeyError, TypeError, ValueError):
                        pass
            legacy_dizzy = set()
            for item in data.get("durchgefuehrte_kontrollen", []):
                if isinstance(item, list) and len(item) >= 2:
                    try: legacy_dizzy.add((int(item[0]), int(item[1])))
                    except (TypeError, ValueError): pass
            loaded_mod = {str(k).lower(): v for k, v in data.get("moderation_eintraege", {}).items()}
            loaded_feedbacks = {str(k): v for k, v in data.get("team_feedbacks", {}).items()}
            loaded_xp_locks = {}
            for k, v in data.get("xp_locks", {}).items():
                try: loaded_xp_locks[int(k)] = float(v)
                except (TypeError, ValueError): pass
            loaded_boost = data.get("active_xp_boost") if isinstance(data.get("active_xp_boost"), dict) else None
            loaded_dizzy_messages = {}
            for k, v in data.get("dizzy_last_message", {}).items():
                if isinstance(v, dict):
                    try: loaded_dizzy_messages[int(k)] = {"message_id": int(v.get("message_id", 0)), "timestamp": float(v.get("timestamp", 0))}
                    except (TypeError, ValueError): pass
            return loaded_xp, loaded_mod, data.get("active_ban_bolos", []), loaded_dizzy, legacy_dizzy, data.get("time_leaderboard", []), loaded_feedbacks, loaded_xp_locks, loaded_boost, loaded_dizzy_messages
        except Exception as e:
            print(f"Fehler beim Laden der Datenbank: {e}")
    return {}, {}, [], [], set(), [], {}, {}, None, {}

def save_data():
    data = {
        "user_xp": user_xp,
        "moderation_eintraege": moderation_eintraege,
        "active_ban_bolos": active_ban_bolos,
        "dizzy_kontrollen": durchgefuehrte_kontrollen,
        "durchgefuehrte_kontrollen": [[mod_id, target_id] for mod_id, target_id in legacy_dizzy_kontrollen],
        "dizzy_last_message": {str(uid): info for uid, info in dizzy_last_message.items()},
        "time_leaderboard": time_leaderboard,
        "team_feedbacks": team_feedbacks,
        "xp_locks": {str(uid): end for uid, end in xp_locks.items()},
        "active_xp_boost": active_xp_boost
    }
    temp_file=f"{DATA_FILE}.tmp"
    try:
        with open(temp_file,"w",encoding="utf-8") as f:
            json.dump(data,f,ensure_ascii=False,indent=4); f.flush(); os.fsync(f.fileno())
        os.replace(temp_file,DATA_FILE)
    except Exception as e:
        print(f"Fehler beim Speichern der Datenbank: {e}")
        try:
            if os.path.exists(temp_file): os.remove(temp_file)
        except OSError: pass

(user_xp, moderation_eintraege, active_ban_bolos, durchgefuehrte_kontrollen, legacy_dizzy_kontrollen, time_leaderboard, team_feedbacks, xp_locks, active_xp_boost, dizzy_last_message) = load_data()

text_cooldowns = {}
fullmute_timers = {}
fullmute_warned = set()
voice_join_times = {}

leaderboard_message_id = None

def get_last_dizzy_control(target_id: int):
    records=[r for r in durchgefuehrte_kontrollen if r.get("target_id")==target_id]
    return max(records,key=lambda r:r.get("timestamp",0)) if records else None

def register_dizzy_message(message: discord.Message):
    if message.guild and message.channel.id == DIZZY_KANAL_ID and not message.author.bot:
        dizzy_last_message[message.author.id]={"message_id":message.id,"timestamp":message.created_at.timestamp()}
        # Alte Kontrollen aus der vorherigen Datenbankversion werden durch
        # die erste neue Nachricht der Zielperson wieder freigegeben.
        for pair in list(legacy_dizzy_kontrollen):
            if pair[1] == message.author.id:
                legacy_dizzy_kontrollen.discard(pair)

def cleanup_expired_xp_state():
    global active_xp_boost
    changed=False; now=time.time()
    for uid,end in list(xp_locks.items()):
        if now>=end: xp_locks.pop(uid,None); changed=True
    if active_xp_boost and now>=active_xp_boost.get("end_timestamp",0):
        active_xp_boost=None; changed=True
    if changed: save_data()

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
    def __init__(self, target_user: discord.Member, sorted_feedbacks_with_orig_idx: list):
        self.target_user = target_user
        options = []
        for display_idx, (orig_idx, fb) in enumerate(sorted_feedbacks_with_orig_idx):
            stars_str = "⭐" * fb["sterne"]
            label = f"#{display_idx+1} | {stars_str} | Von: {fb['autor_name']}"
            desc = fb["kommentar"][:75] if len(fb["kommentar"]) > 75 else fb["kommentar"]
            options.append(discord.SelectOption(label=label[:100], value=str(orig_idx), description=desc[:100]))
            
        super().__init__(placeholder="Wähle das zu entfernende Feedback aus...", min_values=1, max_values=1, options=options)

    async def callback(self, interaction: discord.Interaction):
        selected_orig_idx = int(self.values[0])
        modal = FeedbackRemoveReasonModal(self.target_user, selected_orig_idx)
        await interaction.response.send_modal(modal)

class FeedbackRemoveView(ui.View):
    def __init__(self, target_user: discord.Member, sorted_feedbacks_with_orig_idx: list):
        super().__init__(timeout=120)
        self.add_item(FeedbackRemoveSelect(target_user, sorted_feedbacks_with_orig_idx))

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

    feedbacks_with_orig_idx = list(enumerate(feedbacks))
    sorted_feedbacks_with_orig_idx = sorted(feedbacks_with_orig_idx, key=lambda x: x[1]["timestamp"], reverse=True)

    view = FeedbackRemoveView(user, sorted_feedbacks_with_orig_idx)
    
    embed = discord.Embed(
        title=f"🗑️ Feedback entfernen: {user.display_name}",
        description="Wähle im Dropdown-Menü unten das Feedback aus, welches du entfernen möchtest. (Neu nach Alt sortiert)",
        color=discord.Color.red()
    )
    for idx, (orig_idx, fb) in enumerate(sorted_feedbacks_with_orig_idx[:5]):
        embed.add_field(name=f"#{idx+1} — {'⭐'*fb['sterne']}", value=f"**Kommentar:** {fb['kommentar']}\n*Datum:* <t:{int(fb['timestamp'])}:R>", inline=False)
        
    await interaction.response.send_message(embed=embed, view=view, ephemeral=True)

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
        save_data()

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
async def on_member_update(before, after):
    if before.roles != after.roles:
        guild = after.guild
        if guild.id in TEAM_NACHRICHTEN:
            try:
                msg = TEAM_NACHRICHTEN[guild.id]
                embeds = await generiere_team_embeds(guild)
                await msg.edit(embeds=embeds)
            except Exception as e:
                print(f"Fehler beim Aktualisieren der Teamliste: {e}")

@bot.event
async def on_member_remove(member):
    guild = member.guild
    if guild.id in TEAM_NACHRICHTEN:
        try:
            msg = TEAM_NACHRICHTEN[guild.id]
            embeds = await generiere_team_embeds(guild)
            await msg.edit(embeds=embeds)
        except Exception as e:
            print(f"Fehler beim Aktualisieren nach Austritt/Kick: {e}")

@bot.event
async def on_ready():
    # Persistent Views nur einmal pro Bot-Prozess registrieren. Das verhindert,
    # dass ein Discord-Reconnect dieselben Button-Handler mehrfach registriert.
    if not getattr(bot, "_persistent_views_registered", False):
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
        bot.add_view(WaffenscheinView())
        bot.add_view(WaffenscheinApplicationView())
        bot.add_view(WaffenscheinPaidView())
        bot._persistent_views_registered = True

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
    if message.author.bot:
        return

    # Waffenschein-Bewerbungen laufen ausschließlich per DM.
    if message.guild is None:
        handled = await waffenschein_process_dm(message)
        if not handled:
            await bot.process_commands(message)
        return

    if message.channel.id == DIZZY_KANAL_ID:
        register_dizzy_message(message)
        save_data()

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

@bot.command()
async def setupwaffenschein(ctx):
    if (
        not any(
            r.id == RELOAD_COMMAND_ROLLE_ID
            for r in ctx.author.roles
        )
        and not ctx.author.guild_permissions.administrator
    ):
        await ctx.send(
            "❌ Du hast keine Berechtigung dafür."
        )
        return

    embed = discord.Embed(
        title="🛡️ Waffenschein-Behörde | Lizenz-Antrag",
        description=(
            "Willkommen bei der Behörde für Waffenlizenzen! "
            "Du möchtest dich selbst schützen oder benötigst eine Waffe "
            "für deinen Beruf? Hier kannst du ganz offiziell deinen "
            "Waffenschein beantragen.\n\n"
            "Bitte lies dir genau durch, welche Lizenz für dich infrage "
            "kommt, bevor du deine Bewerbung abschickst:\n\n"
            "**🔫 1. Kleiner Waffenschein:**\n"
            "Diese Lizenz ist für Zivilisten gedacht, die sich im "
            "äußersten Notfall selbst verteidigen müssen.\n\n"
            "- **Erlaubte Waffen:** Leichte Handfeuerwaffen "
            "(z. B. Desert Eagle, Glock 17)\n"
            "- **Voraussetzungen:** Eine weitestgehend saubere Strafakte, "
            "geistige Zurechnungsfähigkeit und ein sicheres Auftreten.\n"
            "- **Zweck:** Reiner Selbstschutz im Alltag.\n\n"
            "**🧨 2. Großer Waffenschein:**\n"
            "Diese Lizenz ist streng reguliert, deutlich schwerer zu "
            "bekommen und oft an spezielle Berufe geknüpft.\n\n"
            "- **Erlaubte Waffen:** Maschinenpistolen (MP5), Sturmgewehre "
            "(M4 Karabiner, G36) und Scharfschützengewehre (Sniper).\n"
            "- **Voraussetzungen:** Eine absolut saubere Strafakte und "
            "ein triftiger Grund (z. B. eingetragener Personenschutz, "
            "Security, Werttransport).\n"
            "- **Zweck:** Professioneller Schutz in Hochrisiko-Situationen.\n\n"
            "Wähle unten die gewünschte Lizenz aus. "
            "Die Bewerbung selbst findet anschließend **privat per DM** statt."
        ),
        color=discord.Color.red()
    )

    embed.set_footer(
        text="Sirius RP • Waffenschein-Behörde"
    )

    await ctx.send(
        embed=embed,
        view=WaffenscheinView()
    )

    try:
        await ctx.message.delete()
    except Exception:
        pass


@bot.tree.command(
    name="teamliste-setup",
    description="Postet die Teamliste und hält sie automatisch aktuell.",
)
async def teamliste_setup(interaction: discord.Interaction):
    if not interaction.user.guild_permissions.administrator:
        await interaction.response.send_message("❌ Du hast keine Berechtigung für diesen Befehl!", ephemeral=True)
        return

    await interaction.response.defer(thinking=True)
    embeds = await generiere_team_embeds(interaction.guild)

    msg = await interaction.channel.send(embeds=embeds)
    TEAM_NACHRICHTEN[interaction.guild.id] = msg
    await interaction.followup.send("Teamliste erfolgreich erstellt!", ephemeral=True)

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
    save_data()
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
        save_data()
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
    save_data()

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
    save_data()
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
        await interaction.response.send_message("❌ Keine Berechtigung!", ephemeral=True); return
    if interaction.channel_id != DIZZY_KANAL_ID:
        await interaction.response.send_message(f"❌ Nur im Kanal <#{DIZZY_KANAL_ID}> erlaubt!", ephemeral=True); return
    mod_id,target_id=interaction.user.id,user.id
    if mod_id==target_id:
        await interaction.response.send_message("❌ Du kannst dich nicht selbst dizzy kontrollieren!", ephemeral=True); return

    latest=dizzy_last_message.get(target_id)
    try:
        async for msg in interaction.channel.history(limit=DIZZY_HISTORY_LIMIT):
            if msg.author.id==target_id and not msg.author.bot:
                latest={"message_id":msg.id,"timestamp":msg.created_at.timestamp()}; break
    except discord.Forbidden:
        await interaction.response.send_message("❌ Ich kann den Nachrichtenverlauf nicht prüfen. Mir fehlt die Berechtigung zum Lesen des Verlaufs.", ephemeral=True); return
    except discord.HTTPException:
        pass
    if latest is None:
        await interaction.response.send_message(f"❌ {user.mention} hat noch keine Nachricht in diesem Kanal geschrieben. Die Person muss zuerst dort eine Nachricht schreiben.", ephemeral=True); return

    last=get_last_dizzy_control(target_id); now=time.time()
    if last:
        remaining=DIZZY_COOLDOWN_SECONDS-(now-last.get("timestamp",0))
        if remaining>0:
            minutes=int(remaining//60); seconds=int(remaining%60)
            text=f"{minutes} Min. {seconds:02d} Sek." if minutes else f"{seconds} Sek."
            await interaction.response.send_message(f"⏳ {user.mention} wurde gerade erst überprüft. Du kannst diese Person erst wieder in **{text}** kontrollieren.", ephemeral=True); return
        if latest["message_id"] <= int(last.get("message_id",0)):
            await interaction.response.send_message(f"❌ {user.mention} hat seit der letzten Dizzykontrolle keine neue Nachricht im Kanal geschrieben. Die Person muss zuerst erneut dort schreiben.", ephemeral=True); return

    durchgefuehrte_kontrollen.append({"mod_id":mod_id,"target_id":target_id,"message_id":int(latest["message_id"]),"timestamp":now})
    save_data()
    received_xp=add_xp(mod_id,15)
    if received_xp>0:
        await log_xp_action(interaction.guild,interaction.user,received_xp,"Dizzykontrolle XP",f"Erfolgreiche Durchführung einer Dizzykontrolle an {user.mention}")
    await refresh_leaderboard_in_channel()
    boost_info=""
    if active_xp_boost and time.time()<active_xp_boost.get("end_timestamp",0): boost_info=f" *(inkl. +{active_xp_boost['percentage']}% Boost)*"
    embed=discord.Embed(title="Dizzykontrolle durchgeführt ✅",description=f"**Teammitglied:** {interaction.user.mention}\n**Kontrollierte Person:** {user.mention}\n\n🎁 **Belohnung:** `+{received_xp} XP`{boost_info}\n⏱️ **Erneute Kontrolle:** nach 5 Minuten und einer neuen Nachricht der Person",color=discord.Color.green())
    await interaction.response.send_message(embed=embed)
    try:
        original_msg=await interaction.original_response(); await original_msg.delete(delay=60)
    except Exception: pass
    kanal=interaction.guild.get_channel(DIZZY_LOG_KANAL_ID)
    if kanal:
        log=discord.Embed(title="🔍 Dizzykontrolle Log",description="Eine neue Dizzykontrolle wurde registriert.",color=discord.Color.blue())
        log.add_field(name="🛡️ Teammitglied",value=interaction.user.mention,inline=True)
        log.add_field(name="👤 Kontrollierte Person",value=user.mention,inline=True)
        log.add_field(name="💬 Verwendete Nachricht",value=f"`{latest['message_id']}`",inline=True)
        log.add_field(name="✨ Vergebene XP",value=f"`+{received_xp} XP`{boost_info}",inline=False)
        log.set_footer(text="Sirius RP • Dizzykontroll-System"); await kanal.send(embed=log)

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
    await ctx.send("✅ Leaderboard-Panel erfolgreich gesendet!")

@bot.command()
@commands.has_permissions(administrator=True)
async def setupfeedback(ctx):
    kanal = bot.get_channel(FEEDBACK_PANEL_KANAL_ID)
    if not kanal:
        await ctx.send("❌ Feedback-Panel-Kanal wurde nicht gefunden!")
        return

    embed = discord.Embed(
        title="⭐ Team-Feedback — Sirius RP",
        description=(
            "Bewerte hier unsere Teammitglieder!\n\n"
            "Klicke unten auf den Button, wähle das entsprechende Teammitglied sowie die Anzahl der Sterne aus "
            "und hinterlasse einen kurzen Kommentar.\n\n"
            "**Hinweis:** Teammitglieder können sich selbst kein Feedback geben und keine Feedbacks abgeben."
        ),
        color=discord.Color.gold()
    )
    embed.set_footer(text="Sirius RP • Feedback-System")

    await kanal.send(embed=embed, view=StartFeedbackView())
    await ctx.send("✅ Feedback-Panel erfolgreich gesendet!")

@bot.command()
@commands.has_permissions(administrator=True)
async def setupcalladmin(ctx):
    kanal = bot.get_channel(CALL_ADMIN_KANAL_ID)
    if not kanal:
        await ctx.send("❌ Call-Admin-Kanal nicht gefunden!")
        return

    embed = discord.Embed(
        title="📞 Admin rufen — Sirius RP",
        description=(
            "Benötigst du Unterstützung von einem Administrator im Spiel?\n\n"
            "Klicke unten auf den Button **\"Admin rufen\"**, fülle das Formular mit deinem Roblox-Namen, "
            "deinem aktuellen Ort und deinem Problem aus, damit unser Team dir schnellstmöglich helfen kann."
        ),
        color=discord.Color.red()
    )
    embed.set_footer(text="Sirius RP • Call-Admin-System")

    await kanal.send(embed=embed, view=StartCallAdminView())
    await ctx.send("✅ Call-Admin-Panel erfolgreich gesendet!")

@bot.command()
@commands.has_permissions(administrator=True)
async def setuptimeleaderboard(ctx):
    kanal = bot.get_channel(LEADERBOARD_KANAL_ID)
    if not kanal:
        await ctx.send("❌ Leaderboard-Kanal nicht gefunden!")
        return

    embed = discord.Embed(
        title="⏰ Zeitauswahl-System",
        description="Klicke auf den Button unten, um deine Uhrzeit in das Zeitauswahl-Leaderboard einzutragen oder das aktuelle Leaderboard einzusehen.",
        color=discord.Color.blue()
    )
    await kanal.send(embed=embed, view=TimeLeaderboardView())
    await ctx.send("✅ Zeitauswahl-Panel gesendet!")

# ==========================================
# BOT STARTEN
# ==========================================
bot.run(os.getenv("DISCORD_TOKEN"))
