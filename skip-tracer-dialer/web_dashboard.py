"""
Web dashboard for the Skip Tracer + Wholesale Dialer system.
Displays leads, call logs, and provides controls for the dialer.
"""

import os
import sys
import subprocess
from pathlib import Path
import json
from datetime import datetime

import pandas as pd
from flask import Flask, render_template, jsonify, request, send_from_directory
from dotenv import load_dotenv

# Setup paths
project_root = Path(__file__).parent
if str(project_root) not in sys.path:
    sys.path.append(str(project_root))

from agents.base_agent import BaseAgent
from models.claude_model import get_claude_model

# Configuration
DATA_DIR = project_root / "data" / "skip_tracer"
TRACED_CSV = DATA_DIR / "traced_leads.csv"
CALL_LOG_CSV = DATA_DIR / "call_log.csv"

load_dotenv(dotenv_path=project_root / ".env")

app = Flask(__name__, template_folder="templates", static_folder="static")
app.config['JSON_SORT_KEYS'] = False

# Global state
dialer_process = None


@app.route("/")
def index():
    """Main dashboard page"""
    return render_template("index.html")


@app.route("/api/leads")
def get_leads():
    """Get all traced leads with their status"""
    if not TRACED_CSV.exists():
        return jsonify({"leads": [], "total": 0})

    try:
        df = pd.read_csv(TRACED_CSV, dtype=str).fillna("")
        df["motivation_score"] = pd.to_numeric(df["motivation_score"], errors="coerce").fillna(0)

        leads = []
        for idx, row in df.iterrows():
            lead = {
                "id": idx,
                "owner": f"{row.get('owner_first_name', '')} {row.get('owner_last_name', '')}".strip(),
                "property": f"{row.get('property_street', '')}, {row.get('property_city', '')} {row.get('property_state', '')}",
                "phone_1": row.get("phone_1", ""),
                "motivation_score": int(row.get("motivation_score", 0)),
                "call_status": row.get("call_status", "pending"),
                "traced_at": row.get("traced_at", ""),
            }
            leads.append(lead)

        return jsonify({"leads": leads, "total": len(leads)})
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.route("/api/call-logs")
def get_call_logs():
    """Get call history and results"""
    if not CALL_LOG_CSV.exists():
        return jsonify({"logs": [], "total": 0})

    try:
        df = pd.read_csv(CALL_LOG_CSV, dtype=str).fillna("")
        logs = []
        for idx, row in df.iterrows():
            log = {
                "id": idx,
                "timestamp": row.get("timestamp", ""),
                "owner": row.get("owner", ""),
                "property": row.get("property", ""),
                "phone": row.get("phone", ""),
                "disposition": row.get("disposition", ""),
                "motivation": row.get("motivation", ""),
                "summary": row.get("summary", ""),
                "timeline": row.get("timeline", ""),
                "condition": row.get("condition", ""),
                "asking_price": row.get("asking_price", ""),
            }
            logs.append(log)

        # Sort by timestamp descending (most recent first)
        logs.sort(key=lambda x: x["timestamp"], reverse=True)
        return jsonify({"logs": logs, "total": len(logs)})
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.route("/api/stats")
def get_stats():
    """Get dashboard statistics"""
    stats = {
        "total_leads": 0,
        "pending_leads": 0,
        "completed_calls": 0,
        "avg_motivation": 0,
    }

    try:
        if TRACED_CSV.exists():
            df_leads = pd.read_csv(TRACED_CSV, dtype=str).fillna("")
            stats["total_leads"] = len(df_leads)
            stats["pending_leads"] = (df_leads["call_status"] == "pending").sum()
            stats["avg_motivation"] = int(
                pd.to_numeric(df_leads["motivation_score"], errors="coerce").mean() or 0
            )

        if CALL_LOG_CSV.exists():
            df_logs = pd.read_csv(CALL_LOG_CSV, dtype=str).fillna("")
            stats["completed_calls"] = len(df_logs)
    except Exception as e:
        print(f"Error calculating stats: {e}")

    return jsonify(stats)


@app.route("/api/check-api-key")
def check_api_key():
    """Verify Anthropic API key is configured"""
    model = get_claude_model("claude-haiku-4-5")
    if model:
        return jsonify({"configured": True})
    return jsonify({"configured": False})


@app.route("/api/system-info")
def get_system_info():
    """Get system configuration info"""
    return jsonify({
        "mode": "practice",
        "api_configured": bool(get_claude_model("claude-haiku-4-5")),
        "data_dir": str(DATA_DIR),
    })


@app.route("/api/start-dialer", methods=["POST"])
def start_dialer():
    """Start the wholesale dialer in the background"""
    global dialer_process

    try:
        # Check if dialer is already running
        if dialer_process and dialer_process.poll() is None:
            return jsonify({"error": "Dialer is already running"}), 400

        # Prepare command - use python to run the dialer
        dialer_script = project_root / "agents" / "wholesale_dialer_agent.py"

        # On Windows, hide the window using CREATE_NO_WINDOW
        if sys.platform == "win32":
            creationflags = 0x08000000  # CREATE_NO_WINDOW
            dialer_process = subprocess.Popen(
                [sys.executable, str(dialer_script)],
                cwd=str(project_root),
                creationflags=creationflags,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
            )
        else:
            # On Unix-like systems
            dialer_process = subprocess.Popen(
                [sys.executable, str(dialer_script)],
                cwd=str(project_root),
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                start_new_session=True,
            )

        return jsonify({
            "status": "started",
            "message": "Dialer started in background",
            "pid": dialer_process.pid
        })
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.route("/api/dialer-status", methods=["GET"])
def dialer_status():
    """Check if the dialer is running"""
    global dialer_process

    if dialer_process and dialer_process.poll() is None:
        return jsonify({"running": True, "pid": dialer_process.pid})
    else:
        dialer_process = None
        return jsonify({"running": False})


@app.route("/api/stop-dialer", methods=["POST"])
def stop_dialer():
    """Stop the dialer if running"""
    global dialer_process

    try:
        if dialer_process and dialer_process.poll() is None:
            dialer_process.terminate()
            dialer_process.wait(timeout=5)
            dialer_process = None
            return jsonify({"status": "stopped"})
        return jsonify({"status": "not running"})
    except Exception as e:
        try:
            if dialer_process:
                dialer_process.kill()
        except:
            pass
        dialer_process = None
        return jsonify({"status": "force stopped", "error": str(e)})


if __name__ == "__main__":
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    print("\n🌙 Skip Tracer Dashboard starting...")
    print("📊 Open your browser to: http://localhost:5000")
    print("Press Ctrl+C to stop\n")
    app.run(host="127.0.0.1", port=5000, debug=False)
