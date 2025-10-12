#!/usr/bin/env python3
"""
Continuous Scaphandre power collector for DeathStarBench Social Network.
Fetches localhost:18080/metrics every 2 seconds, extracts power consumption
(microwatts) for media_service, home_timeline_service, and compose_post_service,
and appends readings with timestamps to a JSONL log file.

Stop safely with `kill <pid>` from SSH or any process manager.
"""

import requests
import re
import json
import time
import signal
import sys
from datetime import datetime, timezone
import os
from pathlib import Path

HOME = Path.home()
OUTPUT_DIR = HOME / "GreenLab" / "testbed" / "experiments"
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
OUTPUT_FILE = OUTPUT_DIR / "scaphandre_energy.jsonl"

SCAPHANDRE_URL = "http://localhost:18080/metrics"
TARGET_SERVICES = ["media_service", "home_timeline_service", "compose_post_service"]
INTERVAL = 2.0  # seconds

# Graceful stop flag
RUNNING = True


def handle_sigint(sig, frame):
    global RUNNING
    print("\n[ScaphandreCollector] Stop signal received. Exiting gracefully...")
    RUNNING = False


signal.signal(signal.SIGINT, handle_sigint)
signal.signal(signal.SIGTERM, handle_sigint)


def extract_power_metrics(metrics_text: str) -> dict:
    """
    Extract power (microwatts) for target services.
    Sums across multiple PIDs for same service name.
    """
    power_pattern = re.compile(
        r'scaph_process_power_consumption_microwatts{[^}]*cmdline="(?P<cmd>[^"]+)"[^}]*pid="(?P<pid>\d+)"[^}]*}\s+(?P<value>[\d\.eE\+\-]+)'
    )

    power_data = {}
    for match in power_pattern.finditer(metrics_text):
        cmd = match.group("cmd")
        val = float(match.group("value"))
        for svc in TARGET_SERVICES:
            if svc in cmd:
                key = f"{svc}_power_uW"
                power_data[key] = power_data.get(key, 0.0) + val

    # Ensure all services appear, even if missing
    for svc in TARGET_SERVICES:
        power_data.setdefault(f"{svc}_power_uW", 0.0)

    return power_data


def fetch_metrics() -> str:
    """
    Retrieve Scaphandre metrics text from localhost endpoint.
    """
    try:
        resp = requests.get(SCAPHANDRE_URL, timeout=5)
        resp.raise_for_status()
        return resp.text
    except requests.RequestException as e:
        print(f"[ScaphandreCollector] Fetch failed: {type(e).__name__}: {e}")
        return ""


def main():
    print(f"[ScaphandreCollector] Starting. Writing to {OUTPUT_FILE}")
    with open(OUTPUT_FILE, "a", encoding="utf-8") as f:
        while RUNNING:
            metrics_text = fetch_metrics()
            if metrics_text:
                data = extract_power_metrics(metrics_text)
                data["timestamp"] = datetime.now(timezone.utc).isoformat()
                f.write(json.dumps(data) + "\n")
                f.flush()
                print(f"[{data['timestamp']}] Recorded: {data}")
            time.sleep(INTERVAL)
    print("[ScaphandreCollector] Stopped.")


if __name__ == "__main__":
    main()
