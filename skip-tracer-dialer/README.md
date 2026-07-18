# 🏠 Skip Tracer + Wholesale Dialer

An AI-assisted lead-to-call pipeline for **real estate wholesaling**. It takes a list of
property addresses, finds the owners' phone numbers, scores how motivated each seller
likely is, and then works the list with an AI acquisitions rep that qualifies the deal.

```
leads.csv ─▶ skip_tracer_agent.py ─▶ traced_leads.csv ─▶ wholesale_dialer_agent.py ─▶ call_log.csv
                                                                  ▲
                                                                  │ (live calls)
                                                        wholesale_dialer_webhook.py
```

## What each piece does

- **`agents/skip_tracer_agent.py`** — reads your property list, pulls owner phones/emails
  from a skip-trace API (BatchData), scrubs your do-not-call list, and uses AI to score
  seller motivation so the hottest leads get called first.
- **`agents/wholesale_dialer_agent.py`** — works the traced queue with an AI acquisitions
  rep. Two modes:
  - **Practice** (`TESTING_MODE = True`, the default): rehearse in your terminal — the AI
    is the rep, you type the seller. No phone service needed, no cost.
  - **Live** (`TESTING_MODE = False`): real outbound calls via Twilio.
- **`agents/wholesale_dialer_webhook.py`** — the live-call brain. A small web server Twilio
  talks to during a real call so the AI can hold a two-way conversation.

## Setup

```bash
# 1. Install the (small) set of dependencies
pip install -r requirements.txt

# 2. Add your keys
cp .env_example .env      # then open .env and paste your keys

# 3. Check everything is wired up (green/red checklist)
python agents/wholesale_dialer_agent.py --verify-setup
```

`.env` keys: `ANTHROPIC_KEY` (the AI) is required. `BATCHDATA_API_KEY` is needed to look up
real phone numbers. The `TWILIO_*` keys and `DIALER_WEBHOOK_URL` are only for live calls.

## Try it now (practice mode — only needs ANTHROPIC_KEY)

A sample lead already ships in `data/skip_tracer/traced_leads.csv`, so you can rehearse the
AI rep immediately:

```bash
python agents/wholesale_dialer_agent.py
```

You type the seller's replies; type `hangup` to end. The AI writes a call summary
(interest, price, timeline, motivation) to `data/skip_tracer/call_log.csv`.

> Tip: for a rehearsal at any time of day, set `ENFORCE_CALLING_HOURS = False` near the top
> of `wholesale_dialer_agent.py` (it otherwise only dials 9am–8pm in the lead's timezone).

## Real skip tracing

Run the tracer with no `leads.csv` and it drops a template for you to fill in:

```bash
python agents/skip_tracer_agent.py     # creates data/skip_tracer/leads.csv, then run again
```

## Live calls (advanced)

1. `python agents/wholesale_dialer_webhook.py` (serves on port 5001)
2. Expose it publicly: `ngrok http 5001`
3. Put the public URL in `.env`: `DIALER_WEBHOOK_URL=https://xxxx.ngrok.io/dialer/gather`
4. Set `TESTING_MODE = False` in `wholesale_dialer_agent.py`, then run it.

## ⚠️ Compliance

Outbound dialing is regulated. Follow the **TCPA**, scrub the **national Do-Not-Call
registry**, respect calling hours, and identify yourself. This tool enforces per-lead
local calling hours, a local `dnc_list.csv` scrub, and litigator flags — but those are
guardrails, **not** a substitute for a real DNC-registry scrub. Lawful use is your
responsibility.

---

Built with the help of Claude Code. 🌙
