"""
🌙 Wholesale Dialer Agent 📞🏠
Skip Tracer + Dialer for real estate wholesaling 🏠

The second half of the wholesaling pipeline. Reads the skip-traced queue from
skip_tracer_agent.py and works the leads, hottest (most motivated) first.

Two modes:
    TESTING_MODE = True  → practice mode in your terminal. The AI plays the
                           acquisitions rep, YOU type the seller's responses.
                           Great for training and refining the script. No calls
                           are placed, no Twilio needed.

    TESTING_MODE = False → live mode. Places real outbound calls via Twilio,
                           streaming a natural AI cold-call opener + gather.

Every conversation gets:
    - AI-driven acquisitions script (built on a solid wholesaling framework)
    - live opt-out capture ("do not call me") → writes to dnc_list.csv so the
      skip tracer scrubs that number forever
    - a disposition (interested / not_interested / callback / dnc / no_answer)
    - deal-qualifying notes (asking price, condition, timeline, motivation)

Input:  src/data/skip_tracer/traced_leads.csv  (from skip_tracer_agent.py)
Output: src/data/skip_tracer/call_log.csv       (dispositions + notes)
        src/data/skip_tracer/dnc_list.csv        (opt-outs, shared with tracer)

Requires in .env:
    ANTHROPIC_KEY (or another provider) for the AI rep
    TWILIO_ACCOUNT_SID / TWILIO_AUTH_TOKEN / TWILIO_PHONE_NUMBER  (live mode only)

Preflight before dialing:
    python src/agents/wholesale_dialer_agent.py --verify-setup
    → green/red checklist of env vars, webhook reachability (live mode), and
      whether the traced queue has callable leads. Exits non-zero on any failure.

⚠️ COMPLIANCE: Live outbound dialing is regulated. Follow the TCPA, honor the
national DNC registry, respect calling-hours windows, and identify yourself.
This agent enforces calling hours and honors opt-outs, but you are responsible
for lawful use.
"""

import sys
from pathlib import Path

project_root = str(Path(__file__).parent.parent)
if project_root not in sys.path:
    sys.path.append(project_root)

import os
import json
from datetime import datetime

import pandas as pd
from termcolor import cprint
from dotenv import load_dotenv

from agents.base_agent import BaseAgent

# ═══════════════════════════════════════════════════════════
# 🎯 Configuration
# ═══════════════════════════════════════════════════════════

TESTING_MODE = True  # True = practice in terminal, False = live Twilio calls

# AI acquisitions rep
AI_MODEL_TYPE = "claude"
AI_MODEL_NAME = "claude-haiku-4-5"  # cheap + fast; the project default haiku-3.5 was retired Feb 2026
AI_TEMPERATURE = 0.7
AI_MAX_TOKENS = 150   # keep it conversational and short on the phone

# Dialing rules
MIN_MOTIVATION_TO_CALL = 40   # skip dead leads below this score
CALLING_HOURS_START = 9       # hour in the LEAD'S local time, 24h. TCPA safe harbor is 8am-9pm
CALLING_HOURS_END = 20
ENFORCE_CALLING_HOURS = True

# US state -> IANA timezone (dominant zone per state). Used to enforce calling
# hours in the property owner's local time, not the server's. States that span
# two zones use the dominant one; AZ uses Phoenix (no DST).
STATE_TIMEZONES = {
    "AL": "America/Chicago",    "AK": "America/Anchorage",  "AZ": "America/Phoenix",
    "AR": "America/Chicago",    "CA": "America/Los_Angeles","CO": "America/Denver",
    "CT": "America/New_York",   "DE": "America/New_York",   "DC": "America/New_York",
    "FL": "America/New_York",   "GA": "America/New_York",   "HI": "Pacific/Honolulu",
    "IA": "America/Chicago",    "ID": "America/Denver",     "IL": "America/Chicago",
    "IN": "America/New_York",   "KS": "America/Chicago",    "KY": "America/New_York",
    "LA": "America/Chicago",    "MA": "America/New_York",   "MD": "America/New_York",
    "ME": "America/New_York",   "MI": "America/New_York",   "MN": "America/Chicago",
    "MO": "America/Chicago",    "MS": "America/Chicago",    "MT": "America/Denver",
    "NC": "America/New_York",   "ND": "America/Chicago",    "NE": "America/Chicago",
    "NH": "America/New_York",   "NJ": "America/New_York",   "NM": "America/Denver",
    "NV": "America/Los_Angeles","NY": "America/New_York",   "OH": "America/New_York",
    "OK": "America/Chicago",    "OR": "America/Los_Angeles","PA": "America/New_York",
    "RI": "America/New_York",   "SC": "America/New_York",   "SD": "America/Chicago",
    "TN": "America/Chicago",    "TX": "America/Chicago",    "UT": "America/Denver",
    "VA": "America/New_York",   "VT": "America/New_York",   "WA": "America/Los_Angeles",
    "WI": "America/Chicago",    "WV": "America/New_York",   "WY": "America/Denver",
    "PR": "America/Puerto_Rico",
}

# Your company info (used in the script) - EDIT THESE 🌙
COMPANY_NAME = "Home Buyers"
CALLER_NAME = "Alex"

# Data locations
DATA_DIR = Path(project_root) / "data" / "skip_tracer"
TRACED_CSV = DATA_DIR / "traced_leads.csv"
CALL_LOG_CSV = DATA_DIR / "call_log.csv"
DNC_CSV = DATA_DIR / "dnc_list.csv"

DISPOSITIONS = ["interested", "not_interested", "callback", "dnc", "no_answer", "wrong_number"]

ACQUISITIONS_PROMPT = f"""You are {CALLER_NAME}, a friendly real estate acquisitions specialist for {COMPANY_NAME}. 🌙

You cold-call property owners to see if they'd consider a cash offer on their property. You are NOT pushy - you are curious, warm, and respectful. If they aren't interested, you thank them and let them go.

YOUR GOALS on the call, in order:
1. Confirm you're speaking with the owner and be transparent: you buy houses for cash.
2. Ask if they'd ever consider selling {{property_address}}.
3. If open: qualify the deal by naturally working in these 4 questions -
   - Condition of the property?
   - Why would they consider selling? (motivation/timeline)
   - What kind of price do they have in mind?
   - How soon would they want to close?
4. If interested, set up a follow-up / offer.

RULES:
- Keep every response to 1-2 short sentences - this is a phone call.
- Sound human, not scripted. React to what they actually say.
- If they say ANY version of "stop calling", "not interested", "take me off your list", "do not call" - respond politely with "Absolutely, I'll take you off our list. Sorry to bother you, take care." and nothing more.
- Never be aggressive or argue. Never make guarantees about price.
- Use plain language a homeowner understands.

Property on file: {{property_address}}
Owner name on file: {{owner_name}}
Motivation signals from our research: {{notes}}"""

DISPOSITION_PROMPT = """You are call analyst. 🌙
Based on the call transcript below, output ONLY a JSON object (no other text):
{
  "disposition": "interested|not_interested|callback|dnc|no_answer|wrong_number",
  "asking_price": "<price they mentioned, or empty>",
  "condition": "<property condition, or empty>",
  "timeline": "<how soon they'd sell, or empty>",
  "motivation": "<why they'd sell, or empty>",
  "summary": "<one sentence recap>"
}
Use "dnc" if they asked to not be called. Use "callback" if they said to call back later."""


class WholesaleDialerAgent(BaseAgent):
    """📞 Works the skip-traced lead queue with an AI acquisitions rep"""

    def __init__(self):
        super().__init__("wholesale_dialer")
        load_dotenv(dotenv_path=Path(project_root) / ".env")

        mode = "🧪 PRACTICE" if TESTING_MODE else "📞 LIVE"
        cprint(f"\n🌙 Wholesale Dialer starting up... {mode} mode 🏠", "cyan")
        DATA_DIR.mkdir(parents=True, exist_ok=True)

        from models.claude_model import get_claude_model
        self.model = get_claude_model(AI_MODEL_NAME)
        if not self.model:
            raise ValueError(f"🚨 Could not initialize {AI_MODEL_TYPE} model for the AI rep!")

        self.twilio = None
        self.twilio_number = None
        if not TESTING_MODE:
            self._init_twilio()

        cprint("✅ Dialer ready to work some leads! 🌙", "green")

    def _init_twilio(self):
        """Set up the Twilio client for live calls"""
        from twilio.rest import Client
        sid = os.getenv("TWILIO_ACCOUNT_SID")
        token = os.getenv("TWILIO_AUTH_TOKEN")
        self.twilio_number = os.getenv("TWILIO_PHONE_NUMBER")
        if not all([sid, token, self.twilio_number]):
            raise ValueError("🚨 Live mode needs TWILIO_ACCOUNT_SID, TWILIO_AUTH_TOKEN, and TWILIO_PHONE_NUMBER in .env!")
        self.twilio = Client(sid, token)

    @staticmethod
    def _lead_now(state):
        """Current datetime in the lead's local timezone (by property state).
        Falls back to server local time when the state is unknown/unmapped."""
        tz_name = STATE_TIMEZONES.get((state or "").strip().upper())
        if not tz_name:
            return datetime.now(), False
        try:
            from zoneinfo import ZoneInfo
            return datetime.now(ZoneInfo(tz_name)), True
        except Exception:
            # zoneinfo missing (very old Python) or tz db unavailable - fail safe to server time
            return datetime.now(), False

    def within_calling_hours(self, state=None):
        """TCPA safe-harbor check in the LEAD'S local time, not the server's."""
        if not ENFORCE_CALLING_HOURS:
            return True
        now, _ = self._lead_now(state)
        return CALLING_HOURS_START <= now.hour < CALLING_HOURS_END

    def load_queue(self):
        """Load pending leads, hottest first, above the motivation floor"""
        if not TRACED_CSV.exists():
            cprint(f"🚨 No traced leads found at {TRACED_CSV}", "red")
            cprint("   Run skip_tracer_agent.py first to build your dialer queue! 🌙", "yellow")
            return None

        df = pd.read_csv(TRACED_CSV, dtype=str).fillna("")
        df["motivation_score"] = pd.to_numeric(df["motivation_score"], errors="coerce").fillna(0)

        dnc = self._load_dnc_numbers()
        queue = df[
            (df["call_status"] == "pending")
            & (df["motivation_score"] >= MIN_MOTIVATION_TO_CALL)
        ].sort_values("motivation_score", ascending=False)

        # Drop leads whose only numbers are all on the DNC list
        callable_rows = []
        for _, row in queue.iterrows():
            if self._first_callable_number(row, dnc):
                callable_rows.append(row)
        cprint(f"📋 {len(callable_rows)} callable leads in the queue (motivation ≥ {MIN_MOTIVATION_TO_CALL})", "cyan")
        return df, callable_rows, dnc

    def _load_dnc_numbers(self):
        if not DNC_CSV.exists():
            return set()
        dnc_df = pd.read_csv(DNC_CSV, dtype=str)
        from agents.skip_tracer_agent import normalize_phone
        return set(normalize_phone(p) for p in dnc_df["phone"].dropna())

    def _first_callable_number(self, row, dnc):
        """Return the best phone for this lead that isn't on the DNC list"""
        from agents.skip_tracer_agent import normalize_phone
        for slot in range(1, 4):
            number = normalize_phone(row.get(f"phone_{slot}", ""))
            if number and number not in dnc:
                return number
        return None

    def run(self):
        """🚀 Work the queue"""
        loaded = self.load_queue()
        if loaded is None:
            return
        full_df, queue, dnc = loaded

        if not queue:
            cprint("😴 No callable leads right now. Trace more leads or lower MIN_MOTIVATION_TO_CALL. 🌙", "yellow")
            return

        calls_made = 0
        skipped_hours = 0
        for i, row in enumerate(queue):
            state = row.get("property_state", "")

            # TCPA calling-hours check in the LEAD'S local time
            if not self.within_calling_hours(state):
                now, resolved = self._lead_now(state)
                where = f"{state.upper()}" if resolved else "server (state unknown)"
                cprint(f"⏰ [{i+1}/{len(queue)}] Skipping {row['property_street']} - {now.strftime('%H:%M')} local in {where}, "
                       f"outside {CALLING_HOURS_START}:00-{CALLING_HOURS_END}:00. 🙏", "yellow")
                skipped_hours += 1
                continue

            number = self._first_callable_number(row, dnc)
            owner = f"{row.get('owner_first_name', '')} {row.get('owner_last_name', '')}".strip() or row.get("owner_name_traced", "there")
            address = f"{row['property_street']}, {row['property_city']} {row['property_state']}"

            calls_made += 1
            cprint(f"\n{'═'*55}", "cyan")
            cprint(f"📞 [{i+1}/{len(queue)}] Calling {owner} @ {address}", "cyan")
            cprint(f"   🌡️ Motivation: {int(row['motivation_score'])}/100 | ☎️  {format_phone(number)}", "cyan")
            if row.get("litigator_flag") in ("True", "true", True):
                cprint("   ⚠️ Litigator flag on this lead - proceed with extra caution!", "red")
            cprint(f"{'═'*55}", "cyan")

            transcript, disposition_data = self.run_call(number, owner, address, row.get("notes", ""))
            self._record_call(full_df, row, number, transcript, disposition_data)

            # In practice mode we know the disposition now; in live mode the webhook
            # captures the real opt-out on hangup and writes DNC itself.
            if not TESTING_MODE:
                continue

            # If they opted out, add to DNC immediately so we never call again
            if disposition_data.get("disposition") == "dnc":
                self._add_to_dnc(number, "opted out on call")
                dnc.add(number)

        if calls_made == 0 and skipped_hours:
            cprint(f"\n🌙 All {skipped_hours} callable lead(s) are outside their local calling hours right now. "
                   f"Come back later - respect the TCPA! 🙏", "yellow")
            return

        summary = f"\n🌙 Session done! {calls_made} call(s) made"
        if skipped_hours:
            summary += f", {skipped_hours} skipped for calling hours"
        cprint(f"{summary}. Logged to {CALL_LOG_CSV.name}. Peace and love. ✌️", "green")

    def run_call(self, number, owner, address, notes):
        """Route to live or practice call handling"""
        system_prompt = ACQUISITIONS_PROMPT.format(
            property_address=address,
            owner_name=owner,
            notes=notes or "none",
        )
        if TESTING_MODE:
            return self._practice_call(system_prompt, owner)
        return self._live_call(number, system_prompt)

    def _practice_call(self, system_prompt, owner):
        """🧪 Terminal role-play: AI is the rep, you type the seller"""
        cprint("   (Practice mode - type what the SELLER says. Type 'hangup' to end.) 🎭\n", "yellow")

        conversation = [{"role": "system", "content": system_prompt}]
        opener = f"Hi, is this {owner}? My name's {CALLER_NAME} with {COMPANY_NAME} - I'll be quick. I actually buy houses for cash in the area and was curious, would you ever consider an offer on your place?"
        cprint(f"🤖 {CALLER_NAME}: {opener}", "green")
        conversation.append({"role": "assistant", "content": opener})

        while True:
            try:
                seller = input("🏠 Seller: ").strip()
            except EOFError:
                break
            if not seller or seller.lower() in ("hangup", "quit", "exit"):
                break

            conversation.append({"role": "user", "content": seller})
            reply = self._ai_reply(conversation)
            cprint(f"🤖 {CALLER_NAME}: {reply}", "green")
            conversation.append({"role": "assistant", "content": reply})

            if self._is_optout(seller):
                cprint("   ⛔ Seller opted out - closing politely and marking DNC.", "yellow")
                break

        transcript = self._format_transcript(conversation)
        return transcript, self.analyze_call(transcript)

    def _live_call(self, number, system_prompt):
        """📞 Place a real Twilio call. Requires a public webhook for full duplex AI;
        here we place the call with an AI-generated opener via TwiML <Say>/<Gather>."""
        from twilio.twiml.voice_response import VoiceResponse, Gather

        opener = self._ai_reply([
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": "Generate ONLY your opening line for the cold call. One or two sentences."},
        ])

        gather_url = os.getenv("DIALER_WEBHOOK_URL", "")
        if not gather_url:
            cprint("   ⚠️ DIALER_WEBHOOK_URL not set - the seller's first reply has nowhere to go!", "red")
            cprint("      Start wholesale_dialer_webhook.py, expose it (ngrok), and set DIALER_WEBHOOK_URL. 🌙", "yellow")

        response = VoiceResponse()
        gather = Gather(input="speech", speechTimeout="auto", action=gather_url, method="POST")
        gather.say(opener, voice="Polly.Matthew")
        response.append(gather)

        # Route call-lifecycle events to the webhook so it can analyze + log on completion.
        status_url = gather_url.replace("/dialer/gather", "/dialer/status") if gather_url else None
        create_kwargs = {"to": f"+1{number}", "from_": self.twilio_number, "twiml": str(response)}
        if status_url:
            create_kwargs["status_callback"] = status_url
            create_kwargs["status_callback_event"] = ["completed"]

        call = self.twilio.calls.create(**create_kwargs)
        cprint(f"   ☎️ Live call placed (SID {call.sid}). Opener: {opener}", "green")
        cprint("   💬 Two-way AI conversation handled by wholesale_dialer_webhook.py; disposition logs on hangup.", "blue")

        transcript = f"{CALLER_NAME}: {opener}\n[live call - full transcript captured by webhook]"
        return transcript, {"disposition": "no_answer", "summary": "live call placed, webhook owns the transcript + disposition"}

    def _ai_reply(self, conversation):
        """Get the AI rep's next line"""
        system = conversation[0]["content"]
        history = "\n".join(
            f"{'Seller' if m['role'] == 'user' else CALLER_NAME}: {m['content']}"
            for m in conversation[1:]
        )
        response = self.model.generate_response(
            system_prompt=system,
            user_content=f"Conversation so far:\n{history}\n\nGive your next reply as {CALLER_NAME} (1-2 sentences):",
            temperature=AI_TEMPERATURE,
            max_tokens=AI_MAX_TOKENS,
        )
        text = response.content if hasattr(response, "content") else str(response)
        return text.strip()

    def analyze_call(self, transcript):
        """🧠 Extract disposition + deal notes from the transcript"""
        response = self.model.generate_response(
            system_prompt=DISPOSITION_PROMPT,
            user_content=f"Call transcript:\n{transcript}",
            temperature=0.2,
            max_tokens=300,
        )
        text = response.content if hasattr(response, "content") else str(response)
        import re
        match = re.search(r"\{.*\}", text, re.DOTALL)
        if not match:
            return {"disposition": "not_interested", "summary": "could not analyze"}
        try:
            data = json.loads(match.group())
        except json.JSONDecodeError:
            return {"disposition": "not_interested", "summary": "could not parse analysis"}
        if data.get("disposition") not in DISPOSITIONS:
            data["disposition"] = "not_interested"
        return data

    def _record_call(self, full_df, row, number, transcript, data):
        """Append to call log and update the lead's status in the queue"""
        log_row = {
            "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            "owner": f"{row.get('owner_first_name', '')} {row.get('owner_last_name', '')}".strip(),
            "property": f"{row['property_street']}, {row['property_city']} {row['property_state']}",
            "phone": number,
            "disposition": data.get("disposition", ""),
            "asking_price": data.get("asking_price", ""),
            "condition": data.get("condition", ""),
            "timeline": data.get("timeline", ""),
            "motivation": data.get("motivation", ""),
            "summary": data.get("summary", ""),
            "transcript": transcript.replace("\n", " | "),
        }
        # In live mode the webhook owns the authoritative call_log row (written on
        # hangup). The dialer only marks the lead "dialing" so we don't re-queue it.
        if not TESTING_MODE:
            mask = (full_df["property_street"] == row["property_street"])
            full_df.loc[mask, "call_status"] = "dialing"
            full_df.to_csv(TRACED_CSV, index=False)
            cprint("   ⏳ Marked 'dialing' - webhook will log the disposition on hangup.", "blue")
            return

        log_df = pd.DataFrame([log_row])
        if CALL_LOG_CSV.exists():
            log_df = pd.concat([pd.read_csv(CALL_LOG_CSV, dtype=str), log_df], ignore_index=True)
        log_df.to_csv(CALL_LOG_CSV, index=False)

        # Update lead status in traced_leads.csv (match on street + phone)
        mask = (full_df["property_street"] == row["property_street"])
        full_df.loc[mask, "call_status"] = data.get("disposition", "called")
        full_df.to_csv(TRACED_CSV, index=False)

        cprint(f"   💾 Logged: {data.get('disposition', '?')} - {data.get('summary', '')}", "green")

    def _add_to_dnc(self, number, reason):
        """Add a number to the shared do-not-call list"""
        entry = pd.DataFrame([{
            "phone": number,
            "added_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            "reason": reason,
        }])
        if DNC_CSV.exists():
            entry = pd.concat([pd.read_csv(DNC_CSV, dtype=str), entry], ignore_index=True)
        entry.to_csv(DNC_CSV, index=False)
        cprint(f"   ⛔ Added {format_phone(number)} to DNC list - won't call again 🌙", "yellow")

    @staticmethod
    def _is_optout(text):
        text = text.lower()
        triggers = ["stop calling", "do not call", "don't call", "take me off",
                    "not interested", "remove me", "leave me alone"]
        return any(t in text for t in triggers)

    @staticmethod
    def _format_transcript(conversation):
        return "\n".join(
            f"{'Seller' if m['role'] == 'user' else CALLER_NAME}: {m['content']}"
            for m in conversation if m["role"] != "system"
        )


def format_phone(digits):
    """(555) 123-4567 formatting for display"""
    digits = str(digits)
    if len(digits) == 10:
        return f"({digits[:3]}) {digits[3:6]}-{digits[6:]}"
    return digits


# Model type -> the .env key the ModelFactory expects (mirrors model_factory.py)
_MODEL_KEY_NAMES = {
    "claude": "ANTHROPIC_KEY",
    "openai": "OPENAI_KEY",
    "groq": "GROQ_API_KEY",
    "deepseek": "DEEPSEEK_KEY",
    "xai": "GROK_API_KEY",
    "ollama": None,  # local, no key needed
}


def preflight():
    """🩺 Pre-dial checklist. Verifies env + reachability + queue BEFORE dialing so
    the dry run fails fast with a clear message instead of mid-call. Returns True
    if everything needed for the current mode is ready."""
    load_dotenv(dotenv_path=Path(project_root) / ".env")

    mode = "PRACTICE" if TESTING_MODE else "LIVE"
    cprint(f"\n🩺 Wholesale Dialer preflight ({mode} mode) 🌙", "cyan")
    cprint("═" * 55, "cyan")

    checks = []  # (ok: bool, label: str, detail: str)

    def check(ok, label, detail=""):
        checks.append((ok, label, detail))

    # 1) AI rep model key
    key_name = _MODEL_KEY_NAMES.get(AI_MODEL_TYPE, None)
    if AI_MODEL_TYPE == "ollama":
        check(True, f"AI model '{AI_MODEL_TYPE}'", "local - no API key needed")
    elif key_name is None:
        check(False, f"AI model '{AI_MODEL_TYPE}'", "unknown model type - check AI_MODEL_TYPE")
    else:
        has = bool(os.getenv(key_name))
        check(has, f"AI model key ({key_name})", "found" if has else f"missing - add {key_name} to .env")

    # 2) Live-mode requirements
    if not TESTING_MODE:
        for env_name in ("TWILIO_ACCOUNT_SID", "TWILIO_AUTH_TOKEN", "TWILIO_PHONE_NUMBER"):
            has = bool(os.getenv(env_name))
            check(has, env_name, "found" if has else "missing - required for live calls")

        webhook = os.getenv("DIALER_WEBHOOK_URL", "")
        if not webhook:
            check(False, "DIALER_WEBHOOK_URL", "missing - the seller's replies have nowhere to go")
        elif "/dialer/gather" not in webhook:
            check(False, "DIALER_WEBHOOK_URL", f"should end in /dialer/gather (got {webhook})")
        else:
            check(True, "DIALER_WEBHOOK_URL", webhook)
            _check_webhook_reachable(webhook, check)
    else:
        check(True, "Twilio", "not needed in practice mode")

    # 3) Traced lead queue
    _check_queue(check)

    # Render results
    cprint("", "cyan")
    all_ok = True
    for ok, label, detail in checks:
        icon, color = ("✅", "green") if ok else ("❌", "red")
        line = f"  {icon} {label}"
        if detail:
            line += f" — {detail}"
        cprint(line, color)
        all_ok = all_ok and ok

    cprint("═" * 55, "cyan")
    if all_ok:
        cprint("🚀 All checks passed — you're clear to dial! Run without --verify-setup. 🌙", "green")
    else:
        cprint("🛑 Fix the ❌ items above before dialing. 🌙", "red")
    return all_ok


def _check_webhook_reachable(webhook_url, check):
    """GET the webhook's /dialer/health and confirm it answers."""
    import requests
    health_url = webhook_url.replace("/dialer/gather", "/dialer/health")
    try:
        resp = requests.get(health_url, timeout=5)
        if resp.status_code == 200 and resp.json().get("status") == "ok":
            check(True, "Webhook reachable", f"{health_url} → ok")
        else:
            check(False, "Webhook reachable", f"{health_url} → HTTP {resp.status_code}")
    except Exception as e:
        check(False, "Webhook reachable", f"{health_url} unreachable ({type(e).__name__}) - is wholesale_dialer_webhook.py running + ngrok up?")


def _check_queue(check):
    """Confirm there's at least one callable, in-motivation, pending lead."""
    if not TRACED_CSV.exists():
        check(False, "Traced lead queue", f"{TRACED_CSV.name} not found - run skip_tracer_agent.py first")
        return

    from agents.skip_tracer_agent import normalize_phone
    df = pd.read_csv(TRACED_CSV, dtype=str).fillna("")
    df["motivation_score"] = pd.to_numeric(df["motivation_score"], errors="coerce").fillna(0)

    dnc = set()
    if DNC_CSV.exists():
        dnc = set(normalize_phone(p) for p in pd.read_csv(DNC_CSV, dtype=str)["phone"].dropna())

    pending = df[(df["call_status"] == "pending") & (df["motivation_score"] >= MIN_MOTIVATION_TO_CALL)]
    callable_count = 0
    for _, row in pending.iterrows():
        if any(normalize_phone(row.get(f"phone_{s}", "")) and normalize_phone(row.get(f"phone_{s}", "")) not in dnc
               for s in range(1, 4)):
            callable_count += 1

    if callable_count:
        check(True, "Traced lead queue", f"{callable_count} callable lead(s) ≥ motivation {MIN_MOTIVATION_TO_CALL}")
    else:
        check(False, "Traced lead queue",
              f"0 callable leads ≥ motivation {MIN_MOTIVATION_TO_CALL} - trace more or lower MIN_MOTIVATION_TO_CALL")


if __name__ == "__main__":
    import sys as _sys
    if "--verify-setup" in _sys.argv:
        ok = preflight()
        _sys.exit(0 if ok else 1)

    try:
        agent = WholesaleDialerAgent()
        agent.run()
    except KeyboardInterrupt:
        cprint("\n👋 Dialer shutting down gracefully... Peace and love! ✌️🌙", "yellow")
