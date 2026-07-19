# Live Mode Setup: Twilio + ngrok

Convert from practice mode (terminal) to real phone calls.

## What You'll Have

- ✅ Outbound calls to sellers via Twilio
- ✅ AI acquisitions rep talks to real sellers
- ✅ Live opt-outs captured to DNC list
- ✅ Call results logged automatically
- ✅ Calling hours enforced (9am–8pm by property timezone)

## Costs

- **Twilio**: ~$15–20 setup + ~$0.014/minute per call
  - Example: 100 calls × 5 min avg = $7
  - Reasonable for testing
- **ngrok**: Free (or $5/month for static URL, optional)

## Step 1: Create Twilio Account

1. Go to **https://www.twilio.com/try-twilio**
2. Sign up with email
3. Verify phone number (they'll text you)
4. Create account
5. Keep the free credits for testing (~$15)

**Don't buy a phone number yet** — we'll do that in Step 3.

## Step 2: Get Your Twilio Credentials

After signup, you'll be in the Twilio Console:

1. Look for **Account SID** and **Auth Token** (visible on dashboard)
2. Copy both — you'll need them for `.env`

Example:
```
Account SID: ACxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx
Auth Token: xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx
```

⚠️ **Keep these secret!** Never commit them to git.

## Step 3: Buy a Twilio Phone Number

1. In Twilio Console, click **Phone Numbers** (left sidebar)
2. Click **Get Started** or **Buy a Number**
3. Search for a number (US, area code doesn't matter)
4. Select one (~$1/month)
5. Save the full number with country code (e.g., `+1-555-123-4567`)

## Step 4: Install ngrok

ngrok exposes your local Flask server publicly so Twilio can send webhooks.

**Download ngrok**: https://ngrok.com/download

1. Download for Windows
2. Extract to a folder (e.g., `C:\ngrok`)
3. Open PowerShell and run:
   ```powershell
   cd C:\ngrok
   .\ngrok http 5001
   ```

You'll see:
```
Forwarding  https://xxxx-yy-zzz-www.ngrok.io -> http://localhost:5001
```

**Copy the `https://xxxx-yy-zzz-www.ngrok.io` URL** — you'll need this next.

## Step 5: Configure `.env`

Add these to your `.env` file:

```
# Twilio Live Mode
TESTING_MODE=False
TWILIO_ACCOUNT_SID=ACxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx
TWILIO_AUTH_TOKEN=xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx
TWILIO_PHONE_NUMBER=+1-555-123-4567
DIALER_WEBHOOK_URL=https://xxxx-yy-zzz-www.ngrok.io/dialer/gather
```

**Important:**
- Replace `ACCOUNT_SID` with your Twilio Account SID
- Replace `AUTH_TOKEN` with your Twilio Auth Token
- Replace `TWILIO_PHONE_NUMBER` with your Twilio number
- Replace `DIALER_WEBHOOK_URL` with your ngrok URL

## Step 6: Update Twilio Webhook (One Time)

In Twilio Console, go to your phone number settings:

1. **Phone Numbers** → Select your number
2. Scroll to **Voice & Fax**
3. Find **A Call Comes In**
4. Set it to:
   - **Webhook URL**: `https://xxxx-yy-zzz-www.ngrok.io/dialer/gather`
   - **Method**: HTTP POST

Save!

## Step 7: Start the Webhook Server

Open PowerShell in your `skip-tracer-dialer` folder and run:

```powershell
python agents/wholesale_dialer_webhook.py
```

You'll see:
```
🌙 Moon Dev's Wholesale Dialer Webhook starting... 📞🏠
✅ DIALER_WEBHOOK_URL set to: https://xxxx-yy-zzz-www.ngrok.io/dialer/gather
🚀 Listening on http://0.0.0.0:5001 (routes: /dialer/gather, /dialer/status, /dialer/health)
```

⚠️ **Keep this running!** Ctrl+C stops it.

## Step 8: Start ngrok (Keep Running)

In a separate PowerShell, keep ngrok running:

```powershell
cd C:\ngrok
.\ngrok http 5001
```

ngrok must stay running for Twilio to reach your webhook.

## Step 9: Test the System

Before calling real leads:

1. **Verify setup**:
   ```powershell
   python agents/wholesale_dialer_agent.py --verify-setup
   ```
   
   Should show:
   ```
   ✅ AI model key (ANTHROPIC_KEY) - found
   ✅ Twilio - configured and reachable
   ✅ Webhook health - 200 OK
   ✅ Traced lead queue - X callable leads
   ```

2. **Test webhook health** (from any browser):
   ```
   https://xxxx-yy-zzz-www.ngrok.io/dialer/health
   ```
   
   Should return JSON with status "ok"

## Step 10: Make Your First Live Call

Once verified, run the dialer:

```powershell
python agents/wholesale_dialer_agent.py
```

The system will:
1. Pick the hottest lead (highest motivation)
2. Dial them via Twilio
3. AI acquisitions rep answers and qualifies the deal
4. Seller responses are transcribed
5. AI replies in real time
6. Call results logged to `data/skip_tracer/call_log.csv`
7. Opt-outs added to DNC list automatically

## Full Live Mode Flow

```
ngrok (running)
    ↓
Webhook Server (running) ← Twilio sends seller speech here
    ↓
Dialer → Calls Lead → Twilio dials → Seller picks up
    ↓
AI Rep (Claude) talks to seller in real time
    ↓
Call ends → Webhook logs results to call_log.csv
    ↓
Dashboard shows new call results
```

## Monitoring Live Calls

**In PowerShell (webhook server):**
```
🤖 Rep: "Hi, I'm calling about your property at 123 Main St..."
🏠 Seller: "Uh, yes, who's this?"
🤖 Rep: "I'm with a local investment company..."
```

**In Dashboard:**
1. Refresh the Calls tab
2. See new call with disposition
3. View deal summary and seller motivation

## Troubleshooting

### "Webhook not reachable" error
- Is ngrok running? (`.\ngrok http 5001`)
- Is the webhook server running? (`python agents/wholesale_dialer_webhook.py`)
- Did you update Twilio webhook URL to match ngrok URL?

### No calls being placed
- Run `--verify-setup` first
- Check that `TESTING_MODE=False` in `.env`
- Verify Twilio account has credits
- Check that you have leads in `traced_leads.csv`

### Seller can't hear AI
- Check microphone/speaker settings
- Restart webhook server
- Verify `VOICE_NAME=Polly.Matthew` in webhook.py (or try `Polly.Joanna`)

### ngrok URL keeps changing
- Free ngrok changes URL every session
- For permanent URL, buy ngrok Pro (~$5/month)
- Or use ngrok auth token: `ngrok authtoken YOUR_TOKEN` then `ngrok http 5001`

## TCPA Compliance

⚠️ **You are responsible for:**
- Scrubbing the national DNC registry (not just local list)
- Calling only between 9am–8pm in seller's timezone
- Identifying yourself as required by law
- Honoring opt-out requests immediately

The system enforces local calling hours and captures opt-outs, but a real DNC registry scrub is your responsibility.

## Next: Get Leads

Once live mode is tested, populate leads:

```powershell
python agents/skip_tracer_agent.py
```

Needs `BATCHDATA_API_KEY` in `.env`.

Then dial!

## Cost Estimate

- Twilio account setup: $15–20 (free credits)
- Twilio number: ~$1/month
- ngrok (optional static URL): $5/month
- Calls: ~$0.014/minute
  - 100 calls × 5 min = $7
  - 1000 calls × 5 min = $70

Reasonable for testing before full deployment.

---

**Questions?** See `README.md` and `DASHBOARD_README.md` for more details.
