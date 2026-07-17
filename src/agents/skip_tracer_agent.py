"""
🌙 Moon Dev's Skip Tracer Agent 🏠
Built with love by Moon Dev 🚀

Skip traces real estate wholesaling leads: takes a CSV of property addresses
and owner names, pulls owner phone numbers + emails from a skip trace API,
scrubs them against your do-not-call list, and uses AI to score seller
motivation so the dialer works the hottest leads first.

Pipeline position:
    leads.csv → [THIS AGENT] → traced_leads.csv → wholesale_dialer_agent.py

Input:  src/data/skip_tracer/leads.csv
        Required columns: property_street, property_city, property_state, property_zip
        Optional columns: owner_first_name, owner_last_name, mailing_street,
                          mailing_city, mailing_state, mailing_zip, notes
        (run this agent once with no leads.csv and it creates a template for you)

Output: src/data/skip_tracer/traced_leads.csv (dialer-ready queue)

Requires in .env:
    BATCHDATA_API_KEY - skip trace data provider (https://batchdata.com)
    ANTHROPIC_KEY     - only if USE_AI_SCORING is True

⚠️ COMPLIANCE: You are responsible for following the TCPA, the national
Do-Not-Call registry, and your state's telemarketing laws. This agent scrubs
against your local dnc_list.csv and flags litigator numbers when the data
provider reports them, but that does NOT replace a real DNC registry scrub.
"""

import sys
from pathlib import Path

# Add project root to Python path for imports
project_root = str(Path(__file__).parent.parent.parent)
if project_root not in sys.path:
    sys.path.append(project_root)

import os
import re
import time
import json
from datetime import datetime

import pandas as pd
import requests
from termcolor import cprint
from dotenv import load_dotenv

from src.agents.base_agent import BaseAgent

# ═══════════════════════════════════════════════════════════
# 🎯 Configuration - tweak these to your liking
# ═══════════════════════════════════════════════════════════

# Skip trace provider settings
BATCHDATA_URL = "https://api.batchdata.com/api/v1/property/skip-trace"
SECONDS_BETWEEN_API_CALLS = 1  # be nice to the API 🙏
MAX_PHONES_PER_LEAD = 3        # how many phone numbers to keep per owner

# AI motivation scoring
USE_AI_SCORING = True          # set False to skip LLM scoring (no ANTHROPIC_KEY needed)
AI_MODEL_TYPE = "claude"       # claude, openai, deepseek, groq, ollama
AI_TEMPERATURE = 0.3           # low temp = consistent scoring
AI_MAX_TOKENS = 300

# Data locations
DATA_DIR = Path(project_root) / "src" / "data" / "skip_tracer"
LEADS_CSV = DATA_DIR / "leads.csv"
TRACED_CSV = DATA_DIR / "traced_leads.csv"
DNC_CSV = DATA_DIR / "dnc_list.csv"

LEAD_TEMPLATE_COLUMNS = [
    "owner_first_name", "owner_last_name",
    "property_street", "property_city", "property_state", "property_zip",
    "mailing_street", "mailing_city", "mailing_state", "mailing_zip",
    "notes",
]

MOTIVATION_PROMPT = """You are Moon Dev's real estate wholesaling analyst. 🌙

You score how motivated a property owner likely is to sell to a cash buyer,
based only on the lead data provided (absentee ownership, notes about
distress like probate/pre-foreclosure/tax liens/vacancy, etc).

Respond with ONLY a JSON object, no other text:
{"score": <0-100 integer>, "reasoning": "<one short sentence>"}

Scoring guide:
- 80-100: strong distress signal (probate, pre-foreclosure, tax delinquent, fire damage)
- 60-79: absentee owner or vacancy, tired-landlord signals
- 40-59: mild signals only
- 0-39: no meaningful motivation signal in the data"""


class SkipTracerAgent(BaseAgent):
    """🏠 Turns raw property lead lists into dialer-ready contact queues"""

    def __init__(self):
        super().__init__("skip_tracer")
        load_dotenv(dotenv_path=Path(project_root) / ".env")

        cprint("\n🌙 Moon Dev's Skip Tracer Agent starting up... 🏠", "cyan")
        DATA_DIR.mkdir(parents=True, exist_ok=True)

        self.api_key = os.getenv("BATCHDATA_API_KEY")
        if not self.api_key:
            raise ValueError("🚨 BATCHDATA_API_KEY not found in .env! Skip tracing needs real data - no fake numbers here 🌙")

        self.model = None
        if USE_AI_SCORING:
            from src.models.model_factory import model_factory
            self.model = model_factory.get_model(AI_MODEL_TYPE)
            if not self.model:
                raise ValueError(f"🚨 Could not initialize {AI_MODEL_TYPE} model for motivation scoring! Set USE_AI_SCORING = False to skip.")

        self.dnc_numbers = self._load_dnc_list()
        cprint(f"✅ Skip Tracer ready! ({len(self.dnc_numbers)} numbers on your DNC list)", "green")

    def _load_dnc_list(self):
        """Load the local do-not-call list (created/added-to by the dialer on opt-outs)"""
        if not DNC_CSV.exists():
            pd.DataFrame(columns=["phone", "added_at", "reason"]).to_csv(DNC_CSV, index=False)
            cprint(f"📝 Created empty DNC list at {DNC_CSV}", "yellow")
            return set()
        df = pd.read_csv(DNC_CSV, dtype=str)
        return set(normalize_phone(p) for p in df["phone"].dropna())

    def load_leads(self):
        """Load the raw lead list, creating a template if it doesn't exist yet"""
        if not LEADS_CSV.exists():
            pd.DataFrame(columns=LEAD_TEMPLATE_COLUMNS).to_csv(LEADS_CSV, index=False)
            cprint(f"\n📝 No leads found! Created a template at:", "yellow")
            cprint(f"   {LEADS_CSV}", "yellow")
            cprint("   Fill it with your driving-for-dollars / list-pull leads and run me again! 🌙", "yellow")
            return None

        df = pd.read_csv(LEADS_CSV, dtype=str).fillna("")
        required = ["property_street", "property_city", "property_state", "property_zip"]
        missing = [c for c in required if c not in df.columns]
        if missing:
            raise ValueError(f"🚨 leads.csv is missing required columns: {missing}")

        cprint(f"📋 Loaded {len(df)} leads from {LEADS_CSV.name}", "cyan")
        return df

    def skip_trace_lead(self, lead):
        """🔍 Hit the skip trace API for one lead and return contact info"""
        request_body = {
            "requests": [{
                "propertyAddress": {
                    "street": lead["property_street"],
                    "city": lead["property_city"],
                    "state": lead["property_state"],
                    "zip": lead["property_zip"],
                }
            }]
        }

        # Owner name helps match accuracy when we have it
        first = lead.get("owner_first_name", "")
        last = lead.get("owner_last_name", "")
        if first or last:
            request_body["requests"][0]["name"] = {"first": first, "last": last}

        response = requests.post(
            BATCHDATA_URL,
            headers={
                "Authorization": f"Bearer {self.api_key}",
                "Content-Type": "application/json",
            },
            json=request_body,
            timeout=30,
        )

        if response.status_code != 200:
            cprint(f"❌ Skip trace API error {response.status_code}: {response.text[:200]}", "red")
            return None

        return self._parse_trace_response(response.json())

    def _parse_trace_response(self, data):
        """Pull phones + emails out of the provider response"""
        persons = data.get("results", {}).get("persons", [])
        if not persons:
            return None

        person = persons[0]
        contact = {"phones": [], "emails": [], "litigator": False, "owner_name": ""}

        name = person.get("name", {})
        contact["owner_name"] = f"{name.get('first', '')} {name.get('last', '')}".strip()

        for phone in person.get("phoneNumbers", []):
            number = normalize_phone(phone.get("number", ""))
            if not number:
                continue
            if phone.get("dnc") or phone.get("litigator"):
                contact["litigator"] = contact["litigator"] or bool(phone.get("litigator"))
                cprint(f"   ⛔ Skipping flagged number ending {number[-4:]} (dnc/litigator)", "yellow")
                continue
            contact["phones"].append({
                "number": number,
                "type": phone.get("type", "unknown"),
                "score": phone.get("score", 0),
            })

        # Best numbers first (provider confidence score), mobiles are gold for wholesaling
        contact["phones"].sort(key=lambda p: (p["type"] == "Mobile", p["score"]), reverse=True)
        contact["phones"] = contact["phones"][:MAX_PHONES_PER_LEAD]

        for email in person.get("emails", []):
            address = email.get("email") if isinstance(email, dict) else email
            if address:
                contact["emails"].append(address)

        return contact

    def score_motivation(self, lead):
        """🧠 Ask the AI how motivated this seller probably is"""
        if not self.model:
            return 50, "AI scoring disabled"

        lead_summary = json.dumps({k: v for k, v in lead.items() if v}, indent=2)
        is_absentee = (
            lead.get("mailing_street", "")
            and lead.get("mailing_street", "").strip().lower() != lead.get("property_street", "").strip().lower()
        )
        user_content = f"Lead data:\n{lead_summary}\n\nAbsentee owner (mailing != property address): {is_absentee}"

        response = self.model.generate_response(
            system_prompt=MOTIVATION_PROMPT,
            user_content=user_content,
            temperature=AI_TEMPERATURE,
            max_tokens=AI_MAX_TOKENS,
        )

        text = response.content if hasattr(response, "content") else str(response)
        match = re.search(r"\{.*\}", text, re.DOTALL)
        if not match:
            cprint(f"⚠️ Couldn't parse AI score, defaulting to 50: {text[:100]}", "yellow")
            return 50, "unparseable AI response"

        result = json.loads(match.group())
        return int(result.get("score", 50)), result.get("reasoning", "")

    def run(self):
        """🚀 Trace every untraced lead and build the dialer queue"""
        leads = self.load_leads()
        if leads is None or leads.empty:
            cprint("😴 Nothing to trace. Add leads and run again!", "yellow")
            return

        # Don't re-trace (and re-pay for) leads we already traced
        already_traced = set()
        if TRACED_CSV.exists():
            traced_df = pd.read_csv(TRACED_CSV, dtype=str).fillna("")
            already_traced = set(traced_df["property_street"].str.lower().str.strip())

        results = []
        for i, lead in leads.iterrows():
            lead = lead.to_dict()
            street_key = lead["property_street"].lower().strip()
            if not street_key:
                continue
            if street_key in already_traced:
                cprint(f"⏭️  [{i+1}/{len(leads)}] Already traced: {lead['property_street']}", "blue")
                continue

            cprint(f"\n🔍 [{i+1}/{len(leads)}] Tracing {lead['property_street']}, {lead['property_city']} {lead['property_state']}...", "cyan")
            contact = self.skip_trace_lead(lead)

            if not contact or not contact["phones"]:
                cprint("   📭 No usable phone numbers found", "yellow")
                results.append(self._build_row(lead, contact, [], 0, "no contact info found"))
                continue

            # Scrub against local DNC list
            clean_phones = [p for p in contact["phones"] if p["number"] not in self.dnc_numbers]
            scrubbed = len(contact["phones"]) - len(clean_phones)
            if scrubbed:
                cprint(f"   🧹 Scrubbed {scrubbed} number(s) on your DNC list", "yellow")

            score, reasoning = self.score_motivation(lead)
            cprint(f"   📞 Found {len(clean_phones)} phone(s) | 🌡️ Motivation: {score}/100 - {reasoning}", "green")

            results.append(self._build_row(lead, contact, clean_phones, score, reasoning))
            time.sleep(SECONDS_BETWEEN_API_CALLS)

        if not results:
            cprint("\n😴 No new leads to trace - dialer queue is up to date! 🌙", "yellow")
            return

        self._save_results(results)

    def _build_row(self, lead, contact, phones, score, reasoning):
        """Assemble one traced_leads.csv row"""
        row = {
            "owner_first_name": lead.get("owner_first_name", ""),
            "owner_last_name": lead.get("owner_last_name", ""),
            "owner_name_traced": contact["owner_name"] if contact else "",
            "property_street": lead.get("property_street", ""),
            "property_city": lead.get("property_city", ""),
            "property_state": lead.get("property_state", ""),
            "property_zip": lead.get("property_zip", ""),
            "notes": lead.get("notes", ""),
            "email": contact["emails"][0] if contact and contact["emails"] else "",
            "litigator_flag": bool(contact and contact["litigator"]),
            "motivation_score": score,
            "motivation_reasoning": reasoning,
            "call_status": "pending" if phones else "no_contact",
            "traced_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        }
        for slot in range(MAX_PHONES_PER_LEAD):
            phone = phones[slot] if slot < len(phones) else {"number": "", "type": ""}
            row[f"phone_{slot+1}"] = phone["number"]
            row[f"phone_{slot+1}_type"] = phone["type"]
        return row

    def _save_results(self, results):
        """Append new traces to the dialer queue, hottest leads first"""
        new_df = pd.DataFrame(results)
        if TRACED_CSV.exists():
            existing = pd.read_csv(TRACED_CSV, dtype=str).fillna("")
            existing["motivation_score"] = pd.to_numeric(existing["motivation_score"], errors="coerce").fillna(0)
            new_df = pd.concat([existing, new_df], ignore_index=True)

        new_df["motivation_score"] = pd.to_numeric(new_df["motivation_score"], errors="coerce").fillna(0)
        new_df = new_df.sort_values("motivation_score", ascending=False)
        new_df.to_csv(TRACED_CSV, index=False)

        with_phones = (new_df["call_status"] == "pending").sum()
        cprint(f"\n💾 Saved {len(new_df)} traced leads to {TRACED_CSV.name}", "green")
        cprint(f"🔥 {with_phones} leads ready for the dialer - run wholesale_dialer_agent.py next! 🌙", "green")


def normalize_phone(raw):
    """Normalize any phone format to bare 10-digit US number (or '' if invalid)"""
    digits = re.sub(r"\D", "", str(raw))
    if len(digits) == 11 and digits.startswith("1"):
        digits = digits[1:]
    return digits if len(digits) == 10 else ""


if __name__ == "__main__":
    try:
        agent = SkipTracerAgent()
        agent.run()
    except KeyboardInterrupt:
        cprint("\n👋 Skip Tracer shutting down gracefully... 🌙", "yellow")
