"""
tools.py – Mock-API für den Voice Agent

Enthält:
  - get_server_status(server_id)  → Serversystem-Abfrage
  - create_ticket(issue)          → CRM/Ticketsystem-Eintrag

Beide Funktionen sind bewusst "defensive" implementiert:
Sie geben immer ein strukturiertes Dict zurück – nie Exceptions –
damit der LLM-Layer immer eine interpretierbare Antwort erhält.
"""

import random
import time
import json
import os
from datetime import datetime
from pathlib import Path
from config import KNOWN_SERVERS, TICKET_COUNTER_START

# ── Persistenter Ticket-Speicher ───────────────────────────────────────────────
TICKETS_FILE = Path(__file__).parent / "tickets.json"

def _load_tickets() -> dict:
    """Lädt Tickets aus der JSON-Datei. Erstellt leere Datei wenn nicht vorhanden."""
    if TICKETS_FILE.exists():
        try:
            with open(TICKETS_FILE, "r", encoding="utf-8") as f:
                return json.load(f)
        except (json.JSONDecodeError, IOError):
            pass
    return {"tickets": [], "last_id": TICKET_COUNTER_START - 1}

def _save_tickets(data: dict) -> bool:
    """Speichert Tickets in die JSON-Datei."""
    try:
        with open(TICKETS_FILE, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
        return True
    except IOError as e:
        print(f"[WARNUNG] Tickets konnten nicht gespeichert werden: {e}")
        return False

# Ticket-Daten beim Start laden
_ticket_data = _load_tickets()
_ticket_counter = _ticket_data["last_id"]


def get_server_status(server_id: str) -> dict:
    """
    Fragt den Status eines Servers ab.

    Args:
        server_id: Server-Bezeichner, z. B. "web-01", "db-02"

    Returns:
        dict mit Feldern:
          - success (bool)
          - server_id (str)
          - status (str): "online" | "degraded" | "offline"
          - cpu (int): CPU-Auslastung in Prozent
          - ram (int): RAM-Auslastung in Prozent
          - uptime_h (int): Uptime in Stunden
          - region (str)
          - alert (str | None): optionale Warnung
          - error (str | None): Fehlermeldung, falls Server unbekannt
    """
    # Normalisierung: Leerzeichen, Groß-/Kleinschreibung
    normalized_id = server_id.strip().lower()

    if normalized_id not in KNOWN_SERVERS:
        return {
            "success": False,
            "server_id": server_id,
            "error": f"Server '{server_id}' nicht gefunden. "
                     f"Bekannte Server: {', '.join(sorted(KNOWN_SERVERS.keys()))}.",
        }

    data = KNOWN_SERVERS[normalized_id].copy()

    # Leichte Simulation von Messrauschen bei CPU/RAM (±3 %)
    if data["status"] != "offline":
        data["cpu"] = max(0, min(100, data["cpu"] + random.randint(-3, 3)))
        data["ram"] = max(0, min(100, data["ram"] + random.randint(-3, 3)))

    return {
        "success": True,
        "server_id": normalized_id,
        "status": data["status"],
        "cpu": data["cpu"],
        "ram": data["ram"],
        "uptime_h": data["uptime_h"],
        "region": data["region"],
        "alert": data.get("alert"),
        "error": None,
    }


def create_ticket(issue: str, priority: str = "normal") -> dict:
    """
    Erstellt ein neues Support-Ticket im CRM und speichert es persistent.

    Args:
        issue:    Freitextbeschreibung des Problems / der Notiz
        priority: "niedrig" | "normal" | "hoch" | "kritisch"

    Returns:
        dict mit Feldern:
          - success (bool)
          - ticket_id (str)
          - issue (str)
          - priority (str)
          - created_at (str): ISO-Zeitstempel
          - estimated_response (str): erwartete Reaktionszeit
          - saved_to (str): Pfad zur Ticket-Datei
          - error (str | None)
    """
    global _ticket_counter, _ticket_data

    if not issue or not issue.strip():
        return {
            "success": False,
            "ticket_id": None,
            "error": "Kein Problemtext übermittelt. Bitte Problembeschreibung angeben.",
        }

    # Priority-Mapping DE → EN
    priority_map = {
        "niedrig": "low", "normal": "normal", "hoch": "high", "kritisch": "critical",
        "low": "low", "medium": "normal", "high": "high", "critical": "critical",
    }
    priority_normalized = priority_map.get(priority.lower(), "normal")

    response_time_map = {
        "low": "3 Werktage", "normal": "1 Werktag",
        "high": "4 Stunden", "critical": "30 Minuten",
    }

    _ticket_counter += 1
    ticket_id = f"TKT-{_ticket_counter}"
    created_at = datetime.now().isoformat(timespec="seconds")

    ticket = {
        "ticket_id": ticket_id,
        "issue": issue.strip(),
        "priority": priority_normalized,
        "created_at": created_at,
        "estimated_response": response_time_map[priority_normalized],
        "status": "open",
    }

    # Persistent speichern
    _ticket_data["tickets"].append(ticket)
    _ticket_data["last_id"] = _ticket_counter
    saved = _save_tickets(_ticket_data)

    return {
        "success": True,
        "ticket_id": ticket_id,
        "issue": issue.strip(),
        "priority": priority_normalized,
        "created_at": created_at,
        "estimated_response": response_time_map[priority_normalized],
        "saved_to": str(TICKETS_FILE) if saved else None,
        "error": None,
    }


def list_tickets() -> dict:
    """
    Gibt alle gespeicherten Tickets zurück.
    Nützlich für Diagnose und Anzeige aller offenen Tickets.
    """
    data = _load_tickets()
    return {
        "success": True,
        "total": len(data["tickets"]),
        "tickets": data["tickets"],
        "file": str(TICKETS_FILE),
    }


# ── Tool-Definitionen für das Groq/Anthropic Tool-Calling-Schema ───────────────
# Diese Liste wird direkt an die Claude API übergeben.

TOOL_DEFINITIONS = [
    {
        "name": "get_server_status",
        "description": (
            "Fragt den aktuellen Status eines internen Servers ab. "
            "Gibt Informationen zu Betriebsstatus, CPU-Auslastung, RAM-Auslastung, "
            "Uptime und Region zurück. Zu verwenden, wenn der Nutzer nach dem Zustand, "
            "der Verfügbarkeit oder der Last eines Servers fragt."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "server_id": {
                    "type": "string",
                    "description": (
                        "ID des Servers, z. B. 'web-01', 'db-02', 'cache-01'. "
                        "Groß-/Kleinschreibung wird ignoriert."
                    ),
                }
            },
            "required": ["server_id"],
        },
    },
    {
        "name": "create_ticket",
        "description": (
            "Erstellt ein neues Support-Ticket oder eine Notiz im CRM-System. "
            "Zu verwenden, wenn der Nutzer ein Problem melden, eine Aufgabe erfassen "
            "oder eine Notiz diktieren möchte."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "issue": {
                    "type": "string",
                    "description": "Freitextbeschreibung des Problems oder der Notiz.",
                },
                "priority": {
                    "type": "string",
                    "enum": ["niedrig", "normal", "hoch", "kritisch"],
                    "description": "Priorität des Tickets. Standard: 'normal'.",
                },
            },
            "required": ["issue"],
        },
    },
]
