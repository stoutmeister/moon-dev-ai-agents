#!/usr/bin/env python3
"""
Launcher for the Skip Tracer Dashboard.
Opens the web dashboard in your default browser and keeps the server running.
"""

import os
import sys
import webbrowser
import time
from pathlib import Path

# Change to the script directory
script_dir = Path(__file__).parent
os.chdir(script_dir)

# Add to path
if str(script_dir) not in sys.path:
    sys.path.insert(0, str(script_dir))

print("\n" + "="*60)
print("🌙 Skip Tracer Dashboard Launcher")
print("="*60)
print("\nStarting web dashboard...")
print("📊 Dashboard will open in your browser shortly...")
print("\nPress Ctrl+C to stop the server\n")

# Give browser a moment to open
time.sleep(2)

# Open browser to dashboard
dashboard_url = "http://localhost:5000"
try:
    webbrowser.open(dashboard_url)
    print(f"✅ Opened browser to {dashboard_url}\n")
except Exception as e:
    print(f"⚠️  Could not open browser automatically. Visit {dashboard_url} manually\n")

# Import and run the Flask app
try:
    from web_dashboard import app
    print("🚀 Dashboard server starting on http://localhost:5000\n")
    app.run(host="127.0.0.1", port=5000, debug=False, use_reloader=False)
except KeyboardInterrupt:
    print("\n\n👋 Shutting down dashboard...")
except Exception as e:
    print(f"\n❌ Error starting dashboard: {e}")
    print("\nMake sure you have installed the requirements:")
    print("  python -m pip install -r requirements.txt")
    sys.exit(1)
