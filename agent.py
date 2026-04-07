"""
agent.py – LLM-Agent mit Groq Tool Calling

Groq bietet eine OpenAI-kompatible API mit kostenlosem Tool Calling.
Modell: llama-3.3-70b-versatile – hervorragende Tool-Call-Zuverlässigkeit.

Ablauf:
  1. Nutzer-Text → Groq API mit Tool-Definitionen
  2. Groq/Llama entscheidet welches Tool aufgerufen wird
  3. Tool-Ergebnis → Groq → natürlichsprachliche Antwort
"""

import json
import logging
from typing import Optional

from groq import Groq

from config import GROQ_API_KEY, GROQ_MODEL
from tools import get_server_status, create_ticket, TOOL_DEFINITIONS

logger = logging.getLogger(__name__)

SYSTEM_PROMPT = """Du bist ein präziser Voice-Agent für interne IT- und CRM-Systeme.

DEINE AUFGABEN:
- Serverstatus abfragen: Wenn der Nutzer nach dem Status eines Servers fragt → rufe IMMER get_server_status auf.
- Ticket erstellen: Wenn der Nutzer ein Problem melden oder eine Notiz diktieren möchte → rufe IMMER create_ticket auf.

REGELN:
1. Antworte IMMER auf Deutsch.
2. Rufe IMMER eines der Tools auf wenn die Anfrage passt. Antworte NIE direkt ohne Tool über Serverstatus.
3. Wenn die Server-ID unklar ist, frage nach – rate keine Argumente.
4. Fehlermeldungen immer freundlich und ohne technischen Jargon.
5. Maximal 3 Sätze – der Nutzer fährt Auto.
6. Andere Anfragen: "Das kann ich leider nicht verarbeiten. Ich bin nur für Serverabfragen und Ticketerstellung zuständig."

FEW-SHOT-BEISPIELE:
- "Wie läuft web-01?" → get_server_status(server_id="web-01")
- "Erstell ein Ticket: Login funktioniert nicht." → create_ticket(issue="Login funktioniert nicht", priority="normal")
"""

# Tool-Definitionen im OpenAI-Format (Groq-kompatibel)
GROQ_TOOLS = [
    {
        "type": "function",
        "function": {
            "name": "get_server_status",
            "description": "Fragt den aktuellen Status eines internen Servers ab. Gibt Betriebsstatus, CPU, RAM, Uptime und Region zurück.",
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
            "description": "Erstellt ein neues Support-Ticket oder eine Notiz im CRM-System.",
            "parameters": {
                "type": "object",
                "properties": {
                    "issue": {
                        "type": "string",
                        "description": "Freitextbeschreibung des Problems oder der Notiz.",
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
]


class VoiceAgent:
    """Orchestriert den Groq-Tool-Calling-Loop."""

    def __init__(self):
        if not GROQ_API_KEY:
            raise ValueError("GROQ_API_KEY nicht gesetzt. Bitte: $env:GROQ_API_KEY='gsk_...'")
        self._client = Groq(api_key=GROQ_API_KEY)
        self._tool_dispatch = {
            "get_server_status": get_server_status,
            "create_ticket": create_ticket,
        }

    def process(self, user_text: str, user: str = "Unbekannt") -> str:
        """Verarbeitet eine Nutzeranfrage und gibt die fertige Antwort zurück."""
        logger.info(f"Agent verarbeitet [{user}]: '{user_text}'")

        messages = [
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": user_text},
        ]

        # ── Runde 1: LLM → Tool-Aufruf ────────────────────────────────────────
        try:
            response = self._client.chat.completions.create(
                model=GROQ_MODEL,
                messages=messages,
                tools=GROQ_TOOLS,
                tool_choice="auto",
                max_tokens=1024,
            )
        except Exception as e:
            err_str = str(e)
            logger.error(f"Groq API Fehler: {e}")
            if "tool_use_failed" in err_str:
                logger.warning("Tool-Call-Fehler – nutze Keyword-Fallback")
                return self._intent_fallback(user_text)
            if "model_decommissioned" in err_str:
                return "Das KI-Modell ist nicht mehr verfügbar. Bitte config.py aktualisieren."
            return "Ich kann die KI-Schnittstelle gerade nicht erreichen. Bitte Verbindung prüfen."

        msg = response.choices[0].message
        logger.debug(f"Groq stop_reason: {response.choices[0].finish_reason}")

        # ── Kein Tool-Call → direkte Antwort ──────────────────────────────────
        if not msg.tool_calls:
            answer = msg.content or "Ich konnte keine Antwort generieren."
            logger.info(f"Direkte Antwort (kein Tool): '{answer}'")
            return answer

        # ── Tool-Call verarbeiten ──────────────────────────────────────────────
        tool_call = msg.tool_calls[0]
        tool_name = tool_call.function.name
        tool_args = json.loads(tool_call.function.arguments)
        tool_call_id = tool_call.id

        logger.info(f"Tool-Aufruf: {tool_name}({tool_args})")

        # ── Mock-API aufrufen ──────────────────────────────────────────────────
        tool_result = self._dispatch_tool(tool_name, tool_args, user)
        logger.info(f"Tool-Ergebnis: {tool_result}")

        # ── Runde 2: Tool-Ergebnis → finale Antwort ───────────────────────────
        messages.append({"role": "assistant", "tool_calls": msg.tool_calls})
        messages.append({
            "role": "tool",
            "tool_call_id": tool_call_id,
            "content": json.dumps(tool_result, ensure_ascii=False),
        })

        try:
            final_response = self._client.chat.completions.create(
                model=GROQ_MODEL,
                messages=messages,
                tools=GROQ_TOOLS,
                max_tokens=512,
            )
            final_text = final_response.choices[0].message.content or ""
            logger.info(f"Finale Antwort: '{final_text}'")
            # Fallback wenn Modell leere Antwort liefert
            if not final_text.strip():
                logger.warning("Leere LLM-Antwort – nutze Fallback")
                return self._fallback_response(tool_name, tool_result)
            return final_text.strip()
        except Exception as e:
            logger.error(f"Groq API Fehler (Runde 2): {e}")
            return self._fallback_response(tool_name, tool_result)

    def _dispatch_tool(self, tool_name: str, tool_args: dict, user: str = "Unbekannt") -> dict:
        fn = self._tool_dispatch.get(tool_name)
        if fn is None:
            return {"success": False, "error": f"Tool '{tool_name}' nicht gefunden."}
        try:
            # User-Context an alle Tool-Calls weitergeben
            return fn(**tool_args, user=user)
        except Exception as e:
            return {"success": False, "error": str(e)}

    def _intent_fallback(self, user_text: str) -> str:
        """
        Einfacher Keyword-Fallback wenn das LLM keinen gültigen Tool-Call generiert.
        Erkennt Intent per Keyword und ruft Mock-API direkt auf.
        """
        text_lower = user_text.lower()

        # Server-Status Erkennung
        import re
        server_match = re.search(r'\b(web|db|cache)-\d+\b', text_lower)
        if server_match:
            server_id = server_match.group(0)
            logger.info(f"Keyword-Fallback: get_server_status({server_id})")
            result = get_server_status(server_id)
            return self._fallback_response("get_server_status", result)

        # Ticket-Erkennung
        if any(w in text_lower for w in ["ticket", "notiz", "erstell", "diktier", "problem", "fehler"]):
            # Issue-Text extrahieren: alles nach ":" oder den ganzen Text
            issue = user_text.split(":", 1)[-1].strip() if ":" in user_text else user_text
            priority = "normal"
            if any(w in text_lower for w in ["kritisch", "critical"]):
                priority = "kritisch"
            elif any(w in text_lower for w in ["hoch", "high", "dringend"]):
                priority = "hoch"
            elif any(w in text_lower for w in ["niedrig", "low"]):
                priority = "niedrig"
            logger.info(f"Keyword-Fallback: create_ticket({issue[:30]}...)")
            result = create_ticket(issue, priority)
            return self._fallback_response("create_ticket", result)

        return "Ich konnte die Anfrage nicht verarbeiten. Bitte fragen Sie nach einem Server-Status oder erstellen Sie ein Ticket."

    def _fallback_response(self, tool_name: str, result: dict) -> str:
        if tool_name == "get_server_status":
            if result.get("success"):
                return f"Server {result['server_id']} ist {result['status']}. CPU: {result['cpu']}%, RAM: {result['ram']}%."
            return f"Fehler: {result.get('error', 'Unbekannt')}"
        if tool_name == "create_ticket":
            if result.get("success"):
                return f"Ticket {result['ticket_id']} wurde erstellt."
            return f"Fehler: {result.get('error', 'Unbekannt')}"
        return "Die Anfrage wurde verarbeitet."
