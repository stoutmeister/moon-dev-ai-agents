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

## System Components

- **`agents/skip_tracer_agent.py`** — reads your property list, pulls owner phones/emails
  from a skip-trace API (BatchData), scrubs your do-not-call list, and uses AI to score
  seller motivation so the hottest leads get called first.
- **`agents/wholesale_dialer_agent.py`** — works the traced queue with an AI acquisitions
  rep. Two modes:
  - **Practice** (`TESTING_MODE = True`, default): rehearse in terminal — you type seller replies, AI responds. No cost.
  - **Live** (`TESTING_MODE = False`): real outbound calls via Twilio + AI rep.
- **`agents/wholesale_dialer_webhook.py`** — the live-call brain. Flask web server that Twilio
  talks to during real calls, holds two-way AI conversation.
- **`web_dashboard.py`** — web interface to view leads queue, call history, and system stats.

## Quick Start (Practice Mode)

1. **Install**:
   ```bash
   python -m pip install -r requirements.txt
   ```

2. **Configure**:
   ```bash
   copy .env_example .env
   # Edit .env and paste your ANTHROPIC_KEY (free from https://console.anthropic.com)
   ```

3. **Verify setup**:
   ```bash
   python agents/wholesale_dialer_agent.py --verify-setup
   ```
   Should show green checkmarks.

4. **Try practice mode** (sample lead included):
   ```bash
   python agents/wholesale_dialer_agent.py
   ```
   Type seller's replies; `hangup` to end call.

5. **View results** (optional):
   ```bash
   python launch_dashboard.py
   ```
   Opens web dashboard at `http://localhost:5000`.

## Getting Real Leads

1. Sign up at https://batchdata.com (skip-trace API)
2. Add `BATCHDATA_API_KEY` to `.env`
3. Create `data/skip_tracer/leads.csv` with property addresses
4. Run tracer:
   ```bash
   python agents/skip_tracer_agent.py
   ```
   Outputs `data/skip_tracer/traced_leads.csv` sorted by motivation score.

5. View in dashboard and dial!

## Live Calls (Twilio)

For real phone calls, see **[TWILIO_SETUP.md](TWILIO_SETUP.md)** for complete instructions.

Quick summary:
- Get Twilio account (~$15–20 setup)
- Buy a phone number (~$1/month)
- Download ngrok (exposes localhost publicly)
- Update `.env` with credentials
- Run three servers: ngrok, webhook, dialer

See **[LIVE_MODE_CHECKLIST.md](LIVE_MODE_CHECKLIST.md)** to track progress.

## Web Dashboard

Launch the dashboard to monitor leads and calls:

```bash
python launch_dashboard.py
```

Or double-click `launch_dashboard.bat` on Windows.

Features:
- 📋 Lead queue with motivation scores
- 📞 Call history with dispositions
- 📊 Real-time stats (total leads, pending calls, avg motivation)
- 🔍 Search and filter by owner, property, status
- ⚙️ System status and API key checker

See **[DASHBOARD_README.md](DASHBOARD_README.md)** for full documentation.

## Configuration (`.env`)

**Required:**
- `ANTHROPIC_KEY` — Claude API key (free from https://console.anthropic.com)

**For real skip tracing:**
- `BATCHDATA_API_KEY` — from https://batchdata.com

**For live calls only:**
- `TWILIO_ACCOUNT_SID` — from Twilio console
- `TWILIO_AUTH_TOKEN` — from Twilio console
- `TWILIO_PHONE_NUMBER` — your Twilio phone number
- `DIALER_WEBHOOK_URL` — your ngrok public URL
- `TESTING_MODE=False` — enable live mode

See `.env_example` for all options.

## Data Files

- `data/skip_tracer/leads.csv` — your raw property list (you fill in)
- `data/skip_tracer/traced_leads.csv` — leads after skip tracing (system generated)
- `data/skip_tracer/call_log.csv` — call results (system generated)
- `data/skip_tracer/dnc_list.csv` — do-not-call list (opt-outs auto-captured)

## Workflow

```
1. Fill leads.csv with properties
   ↓
2. Run skip_tracer_agent.py
   ↓ (fetches phones from BatchData)
   ↓
3. View traced_leads.csv in dashboard
   ↓
4. Run wholesale_dialer_agent.py
   ↓ (practice mode: type in terminal)
   ↓ (live mode: Twilio calls real sellers)
   ↓
5. Results written to call_log.csv
   ↓
6. View calls in dashboard
```

## ⚠️ Compliance & Legal

Outbound dialing is regulated. **You are responsible for**:
- Scrubbing the **national Do-Not-Call registry** (not just local list)
- Following **TCPA** regulations (calling hours, identification, etc.)
- Identifying yourself to sellers
- Honoring opt-out requests immediately

This tool enforces:
- Local calling hours (9am–8pm per seller's timezone)
- Local `dnc_list.csv` scrub
- Litigator number flagging

But these are **guardrails only** — a real DNC registry scrub is your responsibility.

---

Built with the help of Claude Code. 🌙
