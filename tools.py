"""
tools.py – Mock-API für den Voice Agent

Enthält:
  - get_server_status(server_id, user)  → Serversystem-Abfrage + Audit-Log
  - create_ticket(issue, priority, user) → CRM/Ticketsystem + Audit-Log
  - list_tickets()                       → Alle gespeicherten Tickets

Jede Aktion wird im Audit-Log mit Benutzer + Zeitstempel erfasst.
"""

import random
import json
import os
from datetime import datetime
from pathlib import Path
from config import KNOWN_SERVERS, TICKET_COUNTER_START, AUDIT_LOG_FILE

# ── Persistenter Ticket-Speicher ───────────────────────────────────────────────
TICKETS_FILE = Path(__file__).parent / "tickets.json"
AUDIT_FILE   = Path(__file__).parent / AUDIT_LOG_FILE


def _write_audit(user: str, action: str, detail: str, success: bool):
    """Schreibt einen Eintrag ins Audit-Log."""
    status = "OK" if success else "FEHLER"
    entry = (
        f"{datetime.now().isoformat(timespec='seconds')} "
        f"| {status} | Benutzer: {user} | Aktion: {action} | {detail}\n"
    )
    try:
        with open(AUDIT_FILE, "a", encoding="utf-8") as f:
            f.write(entry)
    except IOError:
        pass  # Audit-Fehler darf System nicht stoppen


def _load_tickets() -> dict:
    if TICKETS_FILE.exists():
        try:
            with open(TICKETS_FILE, "r", encoding="utf-8") as f:
                return json.load(f)
        except (json.JSONDecodeError, IOError):
            pass
    return {"tickets": [], "last_id": TICKET_COUNTER_START - 1}


def _save_tickets(data: dict) -> bool:
    try:
        with open(TICKETS_FILE, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
        return True
    except IOError as e:
        print(f"[WARNUNG] Tickets konnten nicht gespeichert werden: {e}")
        return False


_ticket_data = _load_tickets()
_ticket_counter = _ticket_data["last_id"]


def get_server_status(server_id: str, user: str = "Unbekannt") -> dict:
    """
    Fragt den Status eines Servers ab und loggt wer gefragt hat.

    Args:
        server_id: Server-Bezeichner, z. B. "web-01"
        user:      Anfragender Benutzer (für Audit-Log)
    """
    normalized_id = server_id.strip().lower()

    if normalized_id not in KNOWN_SERVERS:
        _write_audit(user, "SERVER_STATUS", f"server_id={server_id} → nicht gefunden", False)
        return {
            "success": False,
            "server_id": server_id,
            "error": (
                f"Server '{server_id}' nicht gefunden. "
                f"Bekannte Server: {', '.join(sorted(KNOWN_SERVERS.keys()))}."
            ),
        }

    data = KNOWN_SERVERS[normalized_id].copy()
    if data["status"] != "offline":
        data["cpu"] = max(0, min(100, data["cpu"] + random.randint(-3, 3)))
        data["ram"] = max(0, min(100, data["ram"] + random.randint(-3, 3)))

    _write_audit(user, "SERVER_STATUS", f"server_id={normalized_id} status={data['status']}", True)

    return {
        "success": True,
        "server_id": normalized_id,
        "status": data["status"],
        "cpu": data["cpu"],
        "ram": data["ram"],
        "uptime_h": data["uptime_h"],
        "region": data["region"],
        "alert": data.get("alert"),
        "queried_by": user,
        "error": None,
    }


def create_ticket(issue: str, priority: str = "normal", user: str = "Unbekannt") -> dict:
    """
    Erstellt ein Ticket und speichert es persistent. Loggt den Ersteller.

    Args:
        issue:    Freitextbeschreibung
        priority: "niedrig" | "normal" | "hoch" | "kritisch"
        user:     Ersteller (für Audit-Log und Ticket)
    """
    global _ticket_counter, _ticket_data

    MAX_ISSUE_LENGTH = 1000
    if not issue or not issue.strip():
        _write_audit(user, "CREATE_TICKET", "Fehlgeschlagen – kein Text", False)
        return {
            "success": False,
            "ticket_id": None,
            "error": "Kein Problemtext übermittelt. Bitte Problembeschreibung angeben.",
        }
    issue = issue.strip()[:MAX_ISSUE_LENGTH]

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
        "created_by": user,
        "created_at": created_at,
        "estimated_response": response_time_map[priority_normalized],
        "status": "open",
    }

    _ticket_data["tickets"].append(ticket)
    _ticket_data["last_id"] = _ticket_counter
    saved = _save_tickets(_ticket_data)

    _write_audit(user, "CREATE_TICKET", f"ticket_id={ticket_id} priority={priority_normalized}", True)

    return {
        "success": True,
        "ticket_id": ticket_id,
        "issue": issue.strip(),
        "priority": priority_normalized,
        "created_by": user,
        "created_at": created_at,
        "estimated_response": response_time_map[priority_normalized],
        "saved_to": str(TICKETS_FILE) if saved else None,
        "error": None,
    }


def list_tickets(user: str = "Unbekannt") -> dict:
    """Gibt alle gespeicherten Tickets zurück."""
    data = _load_tickets()
    _write_audit(user, "LIST_TICKETS", f"total={len(data['tickets'])}", True)
    return {
        "success": True,
        "total": len(data["tickets"]),
        "tickets": data["tickets"],
        "file": str(TICKETS_FILE),
    }


# ── Tool-Definitionen für das Groq Tool-Calling-Schema ────────────────────────
# Einzige Quelle der Wahrheit – wird direkt in agent.py importiert.
TOOL_DEFINITIONS = [
    {
        "type": "function",
        "function": {
            "name": "get_server_status",
            "description": (
                "Fragt den aktuellen Status eines internen Servers ab. "
                "Gibt Betriebsstatus, CPU, RAM, Uptime und Region zurück."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "server_id": {
                        "type": "string",
                        "description": "ID des Servers, z.B. 'web-01', 'db-02', 'cache-01'.",
                    }
                },
                "required": ["server_id"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "create_ticket",
            "description": (
                "Erstellt ein neues Support-Ticket oder eine Notiz im CRM-System."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "issue": {
                        "type": "string",
                        "description": "Freitextbeschreibung des Problems oder der Notiz (max. 1000 Zeichen).",
                    },
                    "priority": {
                        "type": "string",
                        "enum": ["niedrig", "normal", "hoch", "kritisch"],
                        "description": "Priorität des Tickets. Standard: normal.",
                    },
                },
                "required": ["issue"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "list_tickets",
            "description": (
                "Listet alle bisher erstellten Support-Tickets auf. "
                "Aufrufen wenn der Nutzer fragt welche Tickets existieren oder den Überblick möchte."
            ),
            "parameters": {
                "type": "object",
                "properties": {},
                "required": [],
            },
        },
    },
]
