"""
🌙 Moon Dev's Wholesale Dialer Webhook 📞🏠
Built with love by Moon Dev 🚀

The live-call brain for wholesale_dialer_agent.py. When the dialer places a
real Twilio call in live mode, Twilio needs a public URL to POST the seller's
spoken words to and get the AI rep's next line back. This Flask server is that
URL - it holds a full two-way AI acquisitions conversation, captures opt-outs
into the shared DNC list, and writes a disposition + deal notes to call_log.csv
when the call ends.

FLOW:
    dialer places call --> Twilio dials seller --> seller speaks -->
    Twilio POSTs speech here --> AI rep replies (TwiML) --> repeat -->
    call ends --> Twilio POSTs /dialer/status --> we analyze + log

SETUP (live mode):
    1. pip install flask twilio  (already in requirements.txt)
    2. Run this server:            python src/agents/wholesale_dialer_webhook.py
    3. Expose it publicly:         ngrok http 5001
    4. Put the public URL in .env: DIALER_WEBHOOK_URL=https://xxxx.ngrok.io/dialer/gather
    5. Set TESTING_MODE=False in wholesale_dialer_agent.py and run the dialer.

The dialer already passes DIALER_WEBHOOK_URL as the <Gather> action, so the
first seller response lands at /dialer/gather and the loop takes over from there.

⚠️ COMPLIANCE: live outbound dialing is regulated (TCPA, DNC registry, calling
hours, identification). This handler honors opt-outs live, but lawful use is
your responsibility.
"""

import sys
from pathlib import Path

project_root = str(Path(__file__).parent.parent.parent)
if project_root not in sys.path:
    sys.path.append(project_root)

import os
from datetime import datetime

import pandas as pd
from flask import Flask, request
from termcolor import cprint
from dotenv import load_dotenv
from twilio.twiml.voice_response import VoiceResponse, Gather

from src.agents.wholesale_dialer_agent import (
    WholesaleDialerAgent,
    ACQUISITIONS_PROMPT,
    CALLER_NAME,
    COMPANY_NAME,
    CALL_LOG_CSV,
    DATA_DIR,
    format_phone,
)

# ═══════════════════════════════════════════════════════════
# 🎯 Configuration
# ═══════════════════════════════════════════════════════════

WEBHOOK_PORT = 5001
VOICE_NAME = "Polly.Matthew"   # Twilio neural voice; try Polly.Joanna for female
SPEECH_TIMEOUT = "auto"

load_dotenv(dotenv_path=Path(project_root) / ".env")

app = Flask(__name__)

# One shared dialer instance gives us the AI model, analyze_call, DNC + logging
dialer = WholesaleDialerAgent.__new__(WholesaleDialerAgent)  # skip __init__ (no queue load)


def _boot_dialer():
    """Initialize just the model + Twilio bits the webhook needs, once."""
    from src.models.model_factory import model_factory
    from src.agents.wholesale_dialer_agent import AI_MODEL_TYPE

    DATA_DIR.mkdir(parents=True, exist_ok=True)
    dialer.type = "wholesale_dialer_webhook"
    dialer.start_time = datetime.now()
    dialer.model = model_factory.get_model(AI_MODEL_TYPE)
    if not dialer.model:
        raise ValueError(f"🚨 Could not initialize {AI_MODEL_TYPE} model for the webhook AI rep!")
    dialer.twilio = None
    dialer.twilio_number = None


# In-memory conversation state, keyed by Twilio CallSid.
# For a single-box deployment this is fine; swap for Redis if you scale out.
CALLS = {}


def _get_lead_context(call_sid, to_number):
    """Look up the lead we're calling so the AI has property context.

    The dialer stamps context into CALLS before dialing when it can; if this is
    a cold hit (server restarted mid-campaign) we fall back to the traced queue.
    """
    if call_sid in CALLS:
        return CALLS[call_sid]

    from src.agents.wholesale_dialer_agent import TRACED_CSV
    from src.agents.skip_tracer_agent import normalize_phone

    context = {
        "system_prompt": ACQUISITIONS_PROMPT.format(
            property_address="your property", owner_name="there", notes="none"
        ),
        "history": [],
        "to_number": normalize_phone(to_number),
        "owner": "there",
        "address": "your property",
    }

    if TRACED_CSV.exists():
        df = pd.read_csv(TRACED_CSV, dtype=str).fillna("")
        target = normalize_phone(to_number)
        for _, row in df.iterrows():
            nums = {normalize_phone(row.get(f"phone_{s}", "")) for s in range(1, 4)}
            if target in nums:
                owner = f"{row.get('owner_first_name','')} {row.get('owner_last_name','')}".strip() or "there"
                address = f"{row['property_street']}, {row['property_city']} {row['property_state']}"
                context["system_prompt"] = ACQUISITIONS_PROMPT.format(
                    property_address=address, owner_name=owner, notes=row.get("notes", "none") or "none"
                )
                context["owner"] = owner
                context["address"] = address
                break

    CALLS[call_sid] = context
    return context


def _reply_twiml(context, seller_text):
    """Build the AI rep's next line and wrap it in gather TwiML."""
    context["history"].append({"role": "user", "content": seller_text})

    conversation = [{"role": "system", "content": context["system_prompt"]}] + context["history"]
    reply = dialer._ai_reply(conversation)
    context["history"].append({"role": "assistant", "content": reply})

    cprint(f"🏠 Seller: {seller_text}", "cyan")
    cprint(f"🤖 {CALLER_NAME}: {reply}", "green")

    response = VoiceResponse()

    if WholesaleDialerAgent._is_optout(seller_text):
        # Say the closing line the AI produced (prompt tells it how to close), then hang up.
        response.say(reply, voice=VOICE_NAME)
        response.hangup()
        context["opted_out"] = True
        return str(response)

    gather = Gather(
        input="speech",
        speechTimeout=SPEECH_TIMEOUT,
        action=os.getenv("DIALER_WEBHOOK_URL", "/dialer/gather"),
        method="POST",
    )
    gather.say(reply, voice=VOICE_NAME)
    response.append(gather)
    # If the seller goes silent, gently close instead of looping forever.
    response.say("Okay, I'll let you go. Thanks for your time, take care!", voice=VOICE_NAME)
    response.hangup()
    return str(response)


@app.route("/dialer/gather", methods=["POST"])
def gather():
    """Twilio POSTs the seller's transcribed speech here each turn."""
    call_sid = request.values.get("CallSid", "unknown")
    to_number = request.values.get("To", "")
    seller_text = request.values.get("SpeechResult", "").strip()

    context = _get_lead_context(call_sid, to_number)

    if not seller_text:
        # Didn't catch anything - re-prompt once.
        response = VoiceResponse()
        g = Gather(input="speech", speechTimeout=SPEECH_TIMEOUT,
                   action=os.getenv("DIALER_WEBHOOK_URL", "/dialer/gather"), method="POST")
        g.say("Sorry, I didn't catch that. Could you say that again?", voice=VOICE_NAME)
        response.append(g)
        response.hangup()
        return str(response)

    return _reply_twiml(context, seller_text)


@app.route("/dialer/status", methods=["POST"])
def status():
    """Twilio POSTs call lifecycle events here. On completion we analyze + log."""
    call_sid = request.values.get("CallSid", "unknown")
    call_status = request.values.get("CallStatus", "")
    cprint(f"📞 Call {call_sid[:10]} status: {call_status}", "blue")

    if call_status not in ("completed", "busy", "no-answer", "failed", "canceled"):
        return "", 200

    context = CALLS.pop(call_sid, None)
    if not context:
        return "", 200

    transcript = WholesaleDialerAgent._format_transcript(
        [{"role": "system", "content": ""}] + context["history"]
    )
    if not context["history"]:
        transcript = "[no seller response captured]"

    data = dialer.analyze_call(transcript)
    if context.get("opted_out"):
        data["disposition"] = "dnc"

    _log_live_call(context, transcript, data)

    if data.get("disposition") == "dnc" and context.get("to_number"):
        dialer._add_to_dnc(context["to_number"], "opted out on live call")

    cprint(f"   💾 Live call logged: {data.get('disposition','?')} - {data.get('summary','')}", "green")
    return "", 200


def _log_live_call(context, transcript, data):
    """Write the finished live call to call_log.csv (same schema as practice mode)."""
    log_row = {
        "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "owner": context.get("owner", ""),
        "property": context.get("address", ""),
        "phone": context.get("to_number", ""),
        "disposition": data.get("disposition", ""),
        "asking_price": data.get("asking_price", ""),
        "condition": data.get("condition", ""),
        "timeline": data.get("timeline", ""),
        "motivation": data.get("motivation", ""),
        "summary": data.get("summary", ""),
        "transcript": transcript.replace("\n", " | "),
    }
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    log_df = pd.DataFrame([log_row])
    if CALL_LOG_CSV.exists():
        log_df = pd.concat([pd.read_csv(CALL_LOG_CSV, dtype=str), log_df], ignore_index=True)
    log_df.to_csv(CALL_LOG_CSV, index=False)


@app.route("/dialer/health", methods=["GET"])
def health():
    return {"status": "ok", "company": COMPANY_NAME, "active_calls": len(CALLS)}, 200


if __name__ == "__main__":
    cprint("\n🌙 Moon Dev's Wholesale Dialer Webhook starting... 📞🏠", "cyan")
    _boot_dialer()
    webhook_url = os.getenv("DIALER_WEBHOOK_URL")
    if webhook_url:
        cprint(f"✅ DIALER_WEBHOOK_URL set to: {webhook_url}", "green")
    else:
        cprint("⚠️ DIALER_WEBHOOK_URL not set in .env - expose this server with ngrok and set it!", "yellow")
        cprint("   Example: DIALER_WEBHOOK_URL=https://xxxx.ngrok.io/dialer/gather", "yellow")
    cprint(f"🚀 Listening on http://0.0.0.0:{WEBHOOK_PORT}  (routes: /dialer/gather, /dialer/status, /dialer/health)", "green")
    app.run(host="0.0.0.0", port=WEBHOOK_PORT)
