from flask import Flask, render_template, request, jsonify
import csv, math, os

app = Flask(__name__)
DATA_FILE = os.path.join(os.path.dirname(__file__), "wells.csv")


def load_wells():
    wells = []
    with open(DATA_FILE, newline="", encoding="utf-8") as f:
        for row in csv.DictReader(f):
            for k in ["latitude", "longitude", "depth", "formation_pressure", "mud_weight", "drilling_days"]:
                row[k] = float(row[k])
            row["risk_score"] = int(row["risk_score"])
            wells.append(row)
    return wells


def distance_km(lat1, lon1, lat2, lon2):
    R = 6371
    p1, p2 = math.radians(lat1), math.radians(lat2)
    dlat = math.radians(lat2 - lat1)
    dlon = math.radians(lon2 - lon1)
    a = math.sin(dlat / 2) ** 2 + math.cos(p1) * math.cos(p2) * math.sin(dlon / 2) ** 2
    return 2 * R * math.asin(math.sqrt(a))


def clamp(v):
    return round(max(0, min(100, v)), 1)


def similarity_breakdown(new_well, well):
    depth = clamp(100 - abs(new_well["depth"] - well["depth"]) / 500 * 100)
    pressure = clamp(100 - abs(new_well["formation_pressure"] - well["formation_pressure"]) / 0.05 * 100)
    mud = clamp(100 - abs(new_well["mud_weight"] - well["mud_weight"]) / 0.10 * 100)
    # Formation match is categorical and intentionally explicit for explainability.
    formation = 100 if well.get("formation") == new_well.get("formation", "F1") else 0
    score = 0.40 * depth + 0.25 * pressure + 0.20 * mud + 0.15 * formation
    return {
        "depth": depth,
        "pressure": pressure,
        "mud_weight": mud,
        "formation": formation,
        "overall": clamp(score),
    }


def similarity(new_well, well):
    return similarity_breakdown(new_well, well)["overall"]


def timeline_for(well):
    depth = well["depth"]
    issues = [x.strip() for x in well["problems"].split(";") if x.strip() and x.strip().lower() != "none"]
    events = [
        {"depth": round(depth * 0.70), "label": "Formation entry / normal drilling", "type": "normal"},
        {"depth": round(depth * 0.84), "label": "Stable drilling interval", "type": "normal"},
    ]
    if issues:
        fractions = [0.91, 0.96, 0.985]
        for i, issue in enumerate(issues[:3]):
            events.append({"depth": round(depth * fractions[i]), "label": issue, "type": "risk"})
    events.append({"depth": round(depth), "label": "Well reached target depth", "type": "complete"})
    events.sort(key=lambda x: x["depth"])
    return events


@app.route("/")
def index():
    return render_template("index.html")


@app.route("/api/wells")
def wells_api():
    return jsonify(load_wells())


@app.route("/api/analyze", methods=["POST"])
def analyze():
    data = request.get_json(force=True)
    new_well = {
        "latitude": float(data.get("latitude", 17.385)),
        "longitude": float(data.get("longitude", 78.486)),
        "depth": float(data.get("depth", 3000)),
        "formation_pressure": float(data.get("formation_pressure", 0.72)),
        "mud_weight": float(data.get("mud_weight", 1.20)),
        # Formation is optional in the prototype; default keeps the demo compatible.
        "formation": data.get("formation", "F1"),
    }

    wells = load_wells()
    results = []
    for w in wells:
        d = distance_km(new_well["latitude"], new_well["longitude"], w["latitude"], w["longitude"])
        breakdown = similarity_breakdown(new_well, w)
        results.append({**w, "distance_km": round(d, 2), "similarity": breakdown["overall"], "breakdown": breakdown})

    results.sort(key=lambda x: x["similarity"], reverse=True)
    top = results[:5]
    nearby = sorted(results, key=lambda x: x["distance_km"])[:5]
    avg_risk = round(sum(x["risk_score"] for x in nearby) / len(nearby), 1)
    overall = "HIGH" if avg_risk >= 70 else "MEDIUM" if avg_risk >= 40 else "LOW"

    risk_counts = {}
    for w in nearby:
        for issue in w["problems"].split(";"):
            issue = issue.strip()
            if issue and issue.lower() != "none":
                risk_counts[issue] = risk_counts.get(issue, 0) + 1

    recommendations = []
    if risk_counts.get("Lost Circulation", 0):
        recommendations.append("Review lost-circulation history in comparable offset wells before entering similar intervals.")
    if risk_counts.get("Well Kick", 0):
        recommendations.append("Review pressure-control history and kick-detection procedures with the drilling team.")
    if risk_counts.get("Stuck Pipe", 0):
        recommendations.append("Review stuck-pipe intervals and the associated drilling parameters in comparable wells.")
    if new_well["mud_weight"] < 1.15:
        recommendations.append("Prototype flag: proposed mud weight is relatively low; verify the safe operating window with validated field data.")
    if not recommendations:
        recommendations.append("No dominant repeated issue was detected in the selected nearby wells. Continue standard engineering review.")

    top_well = top[0]
    # A prototype-only evidence/coverage indicator: it describes how strongly the indexed sample supports the match.
    coverage = round(min(100, 55 + top_well["similarity"] * 0.4 + min(10, len(nearby) * 2)), 1)

    return jsonify({
        "overall_risk": overall,
        "average_risk": avg_risk,
        "top_matches": top,
        "nearby": nearby,
        "risk_counts": risk_counts,
        "recommendations": recommendations,
        "best_match": top_well,
        "best_match_timeline": timeline_for(top_well),
        "coverage": coverage,
        "indexed_wells": len(wells),
        "evidence_note": "Representative prototype records; similarity is transparent and rule-based, not a validated field model."
    })


if __name__ == "__main__":
    app.run(debug=True)
