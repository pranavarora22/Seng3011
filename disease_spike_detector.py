# influenza_spike_detector.py

import json
from collections import defaultdict
from datetime import datetime


def classify_level(n):
    if n < 1.3:
        return "LOW"
    elif n < 2:
        return "MEDIUM"
    else:
        return "HIGH"


def interpret_signal(level, trend):
    # Normalize for safety (in case inputs are not exact strings)
    level_norm = str(level).upper() if level is not None else ""
    trend_norm = str(trend).upper() if trend is not None else ""

    signal_map = {
        ("HIGH", "HIGH"): "High & Accelerating",
        ("HIGH", "MEDIUM"): "High & Plateaued",
        ("HIGH", "LOW"): "High but Receding",

        ("MEDIUM", "HIGH"): "Medium & Surging",
        ("MEDIUM", "MEDIUM"): "Medium & Stable",
        ("MEDIUM", "LOW"): "Medium & Declining",

        ("LOW", "HIGH"): "Low but Emerging",
        ("LOW", "MEDIUM"): "Low & Increasing",
        ("LOW", "LOW"): "Low & Contained"
    }

    return signal_map.get((level_norm, trend_norm), "Unknown")


def build_analytical_model(records):
    grouped = defaultdict(list)

    # Group by country
    for record in records:
        payload = record.get("payload", {})
        country = payload.get("country_code")

        if country is None:
            continue

        grouped[country].append(record)

    analysed_events = []

    for country, group_records in grouped.items():
        # Safely sort by epi_week (handle missing values)
        group_records.sort(key=lambda r: r.get("payload", {}).get("epi_week", 0))

        # Need at least 5 weeks to compute 4-week trend
        if len(group_records) < 5:
            continue

        # Latest week only
        latest = group_records[-1]
        payload = latest.get("payload", {})

        current_cases = payload.get("cases_detected", 0)

        # Long-term average
        total = 0
        for r in group_records:
            total += r.get("payload", {}).get("cases_detected", 0)

        long_term_avg = total / len(group_records) if len(group_records) > 0 else 0

        # Previous 4 weeks (excluding current)
        prev_total = 0
        for r in group_records[-5:-1]:
            prev_total += r.get("payload", {}).get("cases_detected", 0)

        recent_avg = prev_total / 4 if 4 > 0 else 0

        # Ratios
        n1 = current_cases / long_term_avg if long_term_avg > 0 else 1
        n2 = current_cases / recent_avg if recent_avg > 0 else 1

        level = classify_level(n1)
        trend = classify_level(n2)

        signal = interpret_signal(level, trend)

        analysed_event = {
            "event_id": f"influenza-{country}-{payload.get('epi_week', 'unknown')}-current-signal",
            "timestamp": datetime.utcnow().isoformat() + "Z",
            "event_type": "PUBLIC_HEALTH_SIGNAL",
            "domain": "HEALTH",
            "payload": {
                "disease": "influenza",
                "country": country,
                "epi_week": payload.get("epi_week"),
                "current_cases": current_cases,
                "long_term_avg": round(long_term_avg, 2),
                "recent_4wk_avg": round(recent_avg, 2),
                "n1_ratio": round(n1, 2),
                "n2_ratio": round(n2, 2),
                "signal": signal
            }
        }

        analysed_events.append(analysed_event)

    return analysed_events


if __name__ == "__main__":

    with open("retrieval_output.json", "r", encoding="utf-8") as f:
        data = json.load(f)

    records = data["items"] if isinstance(data, dict) and "items" in data else data

    analysed_events = build_analytical_model(records)

    with open("analysed_events.json", "w", encoding="utf-8") as f:
        json.dump(analysed_events, f, indent=2)

    print(f"Generated {len(analysed_events)} analysed events.")
