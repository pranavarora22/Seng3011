# influenza_spike_detector.py

import json
from collections import defaultdict
from datetime import datetime


def classify_level(n):
    if n < 1.5:
        return "LOW"
    elif n < 2.5:
        return "MEDIUM"
    else:
        return "HIGH"


def interpret_signal(level, trend):
    """
    Maps the two classifications into the final signal.
    """

    signal_map = {

        ("HIGH", "HIGH"): "High and getting higher",
        ("HIGH", "MEDIUM"): "High and staying consistently high",
        ("HIGH", "LOW"): "High but now getting lower",

        ("MEDIUM", "HIGH"): "Medium but getting high recently",
        ("MEDIUM", "MEDIUM"): "Medium and staying there consistently",
        ("MEDIUM", "LOW"): "Medium but getting lower from the past weeks",

        ("LOW", "HIGH"): "Low but getting higher",
        ("LOW", "MEDIUM"): "Low but approaching medium level",
        ("LOW", "LOW"): "Low and staying low / declining"
    }

    return signal_map.get((level, trend), "Unknown")


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

        group_records.sort(key=lambda r: r["payload"]["epi_week"])

        all_cases = [r["payload"]["cases_detected"] for r in group_records]

        long_term_avg = sum(all_cases) / len(all_cases) if all_cases else 0

        for i in range(len(group_records)):

            if i < 4:
                continue

            record = group_records[i]
            payload = record["payload"]

            current_cases = payload["cases_detected"]

            prev_4 = group_records[i-4:i]
            prev_cases = [r["payload"]["cases_detected"] for r in prev_4]

            recent_avg = sum(prev_cases) / len(prev_cases)

            n1 = current_cases / long_term_avg if long_term_avg > 0 else 1
            n2 = current_cases / recent_avg if recent_avg > 0 else 1

            level = classify_level(n1)
            trend = classify_level(n2)

            signal = interpret_signal(level, trend)

            analysed_event = {
                "event_id": f"influenza-{country}-{payload['epi_week']}-signal",
                "timestamp": datetime.utcnow().isoformat() + "Z",
                "event_type": "PUBLIC_HEALTH_SIGNAL",
                "domain": "HEALTH",
                "payload": {
                    "disease": "influenza",
                    "country": country,
                    "epi_week": payload["epi_week"],
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

    analysed = build_analytical_model(records)

    with open("analysed_events.json", "w", encoding="utf-8") as f:
        json.dump(analysed, f, indent=2)

    print(f"Generated {len(analysed)} analysed events.")