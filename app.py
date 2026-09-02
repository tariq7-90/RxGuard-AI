import json
from pathlib import Path

from flask import Flask, jsonify, render_template_string, request

app = Flask(__name__)

REGISTRY_PATH = Path(__file__).parent / "data" / "evidence_registry.json"

with open(REGISTRY_PATH, "r", encoding="utf-8") as f:
    EVIDENCE = json.load(f)

HTML = """
<!doctype html>
<html>
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>RxGuard AI</title>
<style>
body{font-family:Arial,sans-serif;max-width:1000px;margin:30px auto;padding:0 18px;background:#f6f7f9;color:#17202a}
.card{background:white;border-radius:14px;padding:20px;margin:14px 0;box-shadow:0 2px 10px #00000012}
h1{margin-bottom:4px}.muted{color:#667085}.grid{display:grid;grid-template-columns:repeat(2,1fr);gap:12px}
label{font-weight:600;font-size:14px}input,select{width:100%;box-sizing:border-box;padding:10px;margin-top:5px;border:1px solid #d0d5dd;border-radius:8px}
button{padding:11px 16px;border:0;border-radius:8px;cursor:pointer;font-weight:700}
.primary{background:#17202a;color:white}.result{border-left:6px solid;padding:15px}.red{border-color:#d92d20}.orange{border-color:#f79009}.yellow{border-color:#fdb022}.green{border-color:#12b76a}
@media(max-width:700px){.grid{grid-template-columns:1fr}}
</style>
</head>
<body>
<div class="card">
<h1>RxGuard AI</h1>
<div class="muted">Evidence-Based Medication Order Verification</div>
<p>Detect potential prescribing errors before they reach the patient.</p>
</div>

<form class="card" method="post">
<h2>Patient Information</h2>
<div class="grid">
<div><label>Age</label><input name="age" type="number" min="0" step="0.01" required></div>
<div><label>Age Unit</label><select name="age_unit"><option value="days">Days</option><option value="months">Months</option><option value="years" selected>Years</option></select></div>
<div><label>Weight (kg)</label><input name="weight" type="number" min="0" step="0.01"></div>
<div><label>Renal Function (CrCl / eGFR as applicable)</label><input name="renal" type="number" min="0" step="0.01"></div>
<div><label>Allergies</label><input name="allergies"></div>
<div><label>Clinical Indication</label><input name="indication" placeholder="e.g., rheumatoid arthritis"></div>
</div>

<h2>Medication Order</h2>
<div class="grid">
<div><label>Drug</label><input name="drug" placeholder="e.g., methotrexate" required></div>
<div><label>Dose</label><input name="dose" type="number" min="0" step="0.01" required></div>
<div><label>Unit</label><input name="unit" placeholder="mg / units / mg/kg"></div>
<div><label>Route</label><input name="route" placeholder="PO / IV / SC"></div>
<div><label>Frequency</label><input name="frequency" placeholder="once daily / once weekly / q8h"></div>
</div>
<br>
<button class="primary" type="submit">Analyze Medication Order</button>
</form>

{% if result %}
<div class="card result {{result.color}}">
<h2>{{result.title}}</h2>
<p><b>What was detected?</b> {{result.detected}}</p>
<p><b>Why flagged?</b> {{result.reason}}</p>
<p><b>Patient factors:</b> {{result.factors}}</p>
<p><b>Recommended action:</b> {{result.action}}</p>
<p><b>Evidence:</b> {{result.evidence}}</p>
<p class="muted"><b>Pharmacist verification required.</b> This prototype does not modify the original medication order.</p>
</div>
{% endif %}

<div class="card">
<h3>Safety Disclaimer</h3>
<p class="muted">Research and demonstration prototype only. Not connected to BestCare, hospital EHR systems, patient records, UpToDate, Micromedex, or other clinical databases. Do not use for real prescribing, dispensing, or medication administration decisions.</p>
</div>
</body>
</html>
"""

def age_days(age, unit):
    if unit == "days":
        return age
    if unit == "months":
        return age * 30.4375
    return age * 365.25

def classify_age(days):
    if days < 28:
        return "Neonate"
    if days < 730:
        return "Infant"
    if days < 4380:
        return "Child"
    if days < 6570:
        return "Adolescent"
    if days < 23725:
        return "Adult"
    return "Older Adult"

def analyze(form):
    drug = form.get("drug","").strip().lower()
    indication = form.get("indication","").strip().lower()
    freq = form.get("frequency","").strip().lower()
    dose = float(form.get("dose") or 0)
    unit = form.get("unit","").strip().lower()
    weight = float(form.get("weight") or 0)
    renal = float(form.get("renal") or 0)
    age = float(form.get("age") or 0)
    age_unit = form.get("age_unit","years")
    category = classify_age(age_days(age, age_unit))

    factors = f"Age category: {category}; weight: {weight:g} kg"
    if renal:
        factors += f"; renal function value: {renal:g}"

    # Transparent demo rules grounded in the evidence registry.
    if drug in {"methotrexate", "mtx"} and ("daily" in freq or "qd" in freq):
        ev = EVIDENCE["methotrexate_weekly"]
        return dict(color="red", title="Potential Prescribing Error",
                    detected="Methotrexate is ordered with a daily frequency.",
                    reason="For the demonstrated non-oncologic indications, the referenced labeling uses once-weekly administration. Daily-vs-weekly frequency errors are a known serious medication-safety risk.",
                    factors=factors, action="Verify the indication and contact the prescriber; consider correction to the appropriate weekly regimen if clinically confirmed.",
                    evidence=f'{ev["source"]} — {ev["reference"]}')

    if drug in {"gabapentin", "neurontin"} and renal and 15 < renal < 30 and dose * 3 > 700:
        ev = EVIDENCE["gabapentin_renal"]
        return dict(color="red", title="Potential Prescribing Error",
                    detected="The entered daily gabapentin dose appears above the labeled renal-adjusted range for CrCl >15–29 mL/min.",
                    reason="Gabapentin is renally cleared and the cited labeling provides a substantially lower total daily dose range for this renal function.",
                    factors=f"{factors}; ordered daily dose: {dose*3:g} {unit}/day (assuming TID).",
                    action="Verify the indication, renal function, and regimen; select an appropriate renal-adjusted regimen.",
                    evidence=f'{ev["source"]} — {ev["reference"]}')

    if drug == "ampicillin" and category == "Neonate" and weight > 0 and "q8" in freq and "mening" in indication:
        ev = EVIDENCE["ampicillin_neonate"]
        return dict(color="red", title="Potential Prescribing Error",
                    detected="The neonatal ampicillin frequency may not match the cited gestational-age/postnatal-age dosing framework.",
                    reason="Neonatal ampicillin dosing can depend on gestational age and postnatal age; weight alone is insufficient.",
                    factors=f"{factors}. Neonatal gestational age and postnatal age are required for definitive rule evaluation.",
                    action="Verify gestational age, postnatal age, indication, and local neonatal protocol before changing the order.",
                    evidence=f'{ev["source"]} — {ev["reference"]}')

    if drug in {"heparin", "unfractionated heparin", "insulin", "insulin glargine"}:
        ev = EVIDENCE["high_alert"]
        return dict(color="yellow", title="High-Alert / Enhanced Verification",
                    detected="The medication is categorized as high-alert in the referenced medication-safety source.",
                    reason="High-alert status means that an error can cause significant harm; it does not by itself mean this order is incorrect.",
                    factors=factors, action="Perform enhanced pharmacist verification of indication, dose, route, frequency, and monitoring requirements.",
                    evidence=f'{ev["source"]} — {ev["reference"]}')

    return dict(color="green", title="No Significant Anomaly Detected",
                detected="No demonstration rule was triggered by the supplied information.",
                reason="This result means only that the current prototype did not identify a configured anomaly; it is not a guarantee of safety or appropriateness.",
                factors=factors, action="Continue standard clinical pharmacist verification.",
                evidence="Configured RxGuard AI evidence registry.")

@app.route("/", methods=["GET","POST"])
def home():
    result = analyze(request.form) if request.method == "POST" else None
    return render_template_string(HTML, result=result)

@app.route("/api/evidence")
def evidence():
    return jsonify(EVIDENCE)

if __name__ == "__main__":
    app.run(debug=True)
