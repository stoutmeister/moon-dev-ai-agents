# Live Mode Setup Checklist

Follow this checklist to go from practice mode to live phone calls.

## Prerequisites

- [ ] Practice mode tested (`python agents/wholesale_dialer_agent.py` works)
- [ ] Dashboard running (`python launch_dashboard.py`)
- [ ] Anthropic API key configured

## Twilio Account Setup

- [ ] Created Twilio account (https://twilio.com/try-twilio)
- [ ] Verified phone number
- [ ] Have free credits (~$15)
- [ ] Found Account SID in console
- [ ] Found Auth Token in console

## Twilio Phone Number

- [ ] Bought Twilio phone number (~$1/month)
- [ ] Number saved with country code (e.g., `+1-555-123-4567`)
- [ ] Number active in Twilio console

## ngrok Setup

- [ ] Downloaded ngrok (https://ngrok.com/download)
- [ ] Extracted to folder (e.g., `C:\ngrok`)
- [ ] Tested ngrok: `.\ngrok http 5001`
- [ ] ngrok URL obtained (https://xxxx-yyyy-zzzz.ngrok.io)

## Configuration

- [ ] Updated `.env` with:
  - `TESTING_MODE=False`
  - `TWILIO_ACCOUNT_SID=AC...`
  - `TWILIO_AUTH_TOKEN=...`
  - `TWILIO_PHONE_NUMBER=+1-555-123-4567`
  - `DIALER_WEBHOOK_URL=https://xxxx-yyyy-zzzz.ngrok.io/dialer/gather`

- [ ] Updated Twilio webhook in console:
  - Phone number settings
  - Voice & Fax → A Call Comes In → Webhook URL
  - Method: HTTP POST

## Server Startup

- [ ] ngrok running: `.\ngrok http 5001` (in PowerShell, folder 1)
- [ ] Webhook server running: `python agents/wholesale_dialer_webhook.py` (in PowerShell, folder 2)
- [ ] Dashboard running: `python launch_dashboard.py` (optional, for monitoring)

## Testing

- [ ] Ran `--verify-setup`:
  ```powershell
  python agents/wholesale_dialer_agent.py --verify-setup
  ```
  
  Expected output:
  ```
  ✅ AI model key (ANTHROPIC_KEY) - found
  ✅ Twilio - configured and reachable
  ✅ Webhook health - 200 OK
  ✅ Traced lead queue - X callable leads
  ```

- [ ] Tested webhook health (in browser):
  ```
  https://xxxx-yyyy-zzzz.ngrok.io/dialer/health
  ```
  
  Expected: JSON with `"status": "ok"`

## Getting Leads

- [ ] Created BatchData account (https://batchdata.com)
- [ ] Have `BATCHDATA_API_KEY`
- [ ] Added to `.env`: `BATCHDATA_API_KEY=...`
- [ ] Ran skip tracer: `python agents/skip_tracer_agent.py`
- [ ] Have leads in `data/skip_tracer/traced_leads.csv`
- [ ] Dashboard Leads tab shows callable leads

## First Live Call

- [ ] Started dialer: `python agents/wholesale_dialer_agent.py`
- [ ] Dialer picked hottest lead
- [ ] Twilio placed call
- [ ] Seller answered
- [ ] AI rep talked to seller
- [ ] Call completed
- [ ] Results visible in Dashboard → Calls tab

## Ongoing Operation

- [ ] Keep ngrok running while dialing
- [ ] Keep webhook server running while dialing
- [ ] Monitor calls in Dashboard
- [ ] Check `call_log.csv` for results
- [ ] Opt-outs added to `dnc_list.csv` automatically

## Optional Enhancements

- [ ] Set up ngrok auth token for permanent URL
- [ ] Configure SMS notifications for qualified deals
- [ ] Set up CRM integration for leads
- [ ] Monitor call quality (Twilio recordings)

---

## Troubleshooting Reference

If something doesn't work:

1. **Webhook not reachable?**
   - Check ngrok is running
   - Check webhook server is running
   - Verify Twilio webhook URL matches ngrok URL
   - See TWILIO_SETUP.md → Troubleshooting

2. **Calls not placing?**
   - Run `--verify-setup` to diagnose
   - Check Twilio account has credits
   - Verify `TESTING_MODE=False` in `.env`
   - Check for errors in webhook server console

3. **Seller can't hear AI?**
   - Restart webhook server
   - Try different `VOICE_NAME` in `wholesale_dialer_webhook.py`
   - Check Twilio account settings

See `TWILIO_SETUP.md` for full troubleshooting guide.

---

## Quick Reference

**Three Servers Running (Must Have All Three):**

Terminal 1:
```
cd C:\ngrok
.\ngrok http 5001
```

Terminal 2 (skip-tracer-dialer):
```
python agents/wholesale_dialer_webhook.py
```

Terminal 3 (skip-tracer-dialer, optional):
```
python launch_dashboard.py
```

**Then Dial:**
```
python agents/wholesale_dialer_agent.py
```

---

**Estimated Time:** 30–45 minutes for full setup
**Estimated Cost:** $15–20 (Twilio free credits) + calls @ $0.014/minute

Ready to get started?
