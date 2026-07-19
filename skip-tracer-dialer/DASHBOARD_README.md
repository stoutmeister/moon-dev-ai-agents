# Skip Tracer Dashboard

A modern web interface for managing your real estate wholesaling leads and monitoring AI-powered calls.

## Features

✅ **Lead Queue** - View all traced leads sorted by motivation score  
✅ **Call History** - Track all calls with disposition, deal notes, and summaries  
✅ **Real-time Stats** - Dashboard showing total leads, pending calls, and avg motivation  
✅ **Search & Filter** - Find leads and calls by owner, property, phone, or status  
✅ **System Status** - Check API configuration and system readiness  

## Quick Start

### 1. Install Dependencies

If you haven't already:

```bash
python -m pip install -r requirements.txt
```

### 2. Add Your Anthropic API Key

If not already done, edit `.env` and add:

```
ANTHROPIC_KEY=sk-ant-your-key-here
```

### 3. Launch the Dashboard

**Option A: Using the Batch File (Recommended)**

Double-click `launch_dashboard.bat` to start. The web dashboard will open automatically in your browser.

**Option B: Using Python**

```bash
python launch_dashboard.py
```

**Option C: Direct Flask**

```bash
python web_dashboard.py
```

### 4. Open in Browser

Dashboard is available at: **http://localhost:5000**

The dashboard will auto-refresh stats every 30 seconds.

## Creating a Desktop Shortcut (Windows)

### Method 1: Using PowerShell (Recommended)

1. Open PowerShell **as Administrator**
2. Run this command:

```powershell
Set-ExecutionPolicy -ExecutionPolicy RemoteSigned -Scope CurrentUser
```

3. Navigate to the `skip-tracer-dialer` folder:

```powershell
cd C:\Users\YourUsername\path\to\skip-tracer-dialer
```

4. Run the shortcut creator:

```powershell
.\create_shortcut.ps1
```

The desktop shortcut `Skip Tracer Dashboard` will be created.

### Method 2: Manual Shortcut

1. Right-click on desktop → **New** → **Shortcut**
2. For the location, enter:
   ```
   C:\Users\YourUsername\path\to\skip-tracer-dialer\launch_dashboard.bat
   ```
3. Name it: `Skip Tracer Dashboard`
4. Right-click the shortcut → **Properties**
5. Set **Start in** to your `skip-tracer-dialer` folder path
6. Click **OK**

## Dashboard Sections

### 📋 Leads Tab

Shows your traced lead queue with:
- **Owner** - Property owner name
- **Property** - Address
- **Phone** - Primary contact number
- **Motivation** - Score 0-100 (higher = more likely to sell)
- **Status** - pending, completed, no_contact
- **Traced** - Date the lead was traced

**Search & Filter:**
- Type to search by owner, property, or phone
- Filter by status (Pending, Completed, No Contact)

### 📞 Calls Tab

Displays call history with:
- **Date/Time** - When the call occurred
- **Owner** - Seller's name
- **Property** - Property address
- **Disposition** - qualified, not_qualified, dnc, no_answer
- **Motivation** - Seller's motivation level from the call
- **Summary** - AI's summary of the call outcome

**Search & Filter:**
- Search by owner, property, or phone
- Filter by disposition

### ⚙️ Settings Tab

System configuration:
- **Anthropic API Key** - Status of Claude API configuration
- **Mode** - Shows "Practice (Terminal)" for current setup
- **Data Directory** - Path to lead and call data files
- **Next Steps** - Quick guide for what to do next

## Data Files

The dashboard reads from these CSV files:

**`data/skip_tracer/traced_leads.csv`**
- Contains all traced leads with contact info and motivation scores
- Sorted by motivation (highest first)
- Used as the dialer queue

**`data/skip_tracer/call_log.csv`**
- Append-only log of all completed calls
- Includes disposition, deal notes, and AI analysis
- Updated after each call ends

**`data/skip_tracer/dnc_list.csv`**
- Do-not-call list (builds automatically)
- Sellers who opted out are added automatically
- Skip tracer scrubs against this

## Workflow

```
1. Run skip_tracer_agent.py
   ↓
   Populates: data/skip_tracer/traced_leads.csv
   
2. View dashboard → Leads tab
   ↓
   See all leads sorted by motivation
   
3. Run wholesale_dialer_agent.py (practice mode)
   ↓
   Type seller responses in PowerShell
   ↓
   AI handles the call
   
4. View dashboard → Calls tab
   ↓
   See call results and deal summaries
   
5. (Optional) Go live with Twilio for real calls
   ↓
   Same dashboard shows real call results
```

## Troubleshooting

### Dashboard won't open?

1. Make sure Flask is installed:
   ```bash
   python -m pip install flask
   ```

2. Check if port 5000 is available. If not, edit `web_dashboard.py` and change:
   ```python
   app.run(host="127.0.0.1", port=5001, debug=False)
   ```
   Then access at `http://localhost:5001`

### No leads showing?

1. Run the skip tracer first:
   ```bash
   python agents/skip_tracer_agent.py
   ```

2. Make sure you have a `.env` file with `BATCHDATA_API_KEY`

### API key not recognized?

1. Verify `.env` has the correct key format: `ANTHROPIC_KEY=sk-ant-xxx`
2. Make sure there are no extra spaces or quotes
3. Restart the dashboard after changing `.env`

### Shortcut doesn't work?

1. Run PowerShell as Administrator
2. Check that the path to `launch_dashboard.bat` is correct
3. Verify the `skip-tracer-dialer` folder path exists

## Next Steps

1. **Test Practice Mode**: Use the terminal dialer to practice calls
2. **Get Real Leads**: Set up `BATCHDATA_API_KEY` and run skip tracer
3. **Monitor Results**: Use the dashboard to track deal flow
4. **Go Live (Optional)**: Set up Twilio for real phone calls

## Questions?

Check the main `README.md` for full system documentation.
