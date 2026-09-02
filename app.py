
import streamlit as st
from datetime import datetime
import json
from pathlib import Path

st.set_page_config(page_title="RxGuard AI", page_icon="🛡️", layout="wide")

EVIDENCE_PATH = Path(__file__).parent / "data" / "evidence_registry.json"
with open(EVIDENCE_PATH, "r", encoding="utf-8") as f:
    EVIDENCE = json.load(f)

st.title("🛡️ RxGuard AI")
st.caption("Evidence-grounded Medication Order Safety Analyzer — Research Prototype")

st.warning(
    "SIMULATED RESEARCH PROTOTYPE ONLY. No real patient data, hospital data, or confidential protocols are used. "
    "This tool does not prescribe, approve, discontinue, or automatically modify medications. "
    "Every finding requires independent clinical verification."
)

def norm(x):
    return str(x or "").strip().lower()

def num(x):
    try:
        return float(x)
    except:
        return None

def evidence_card(rule_id):
    e = EVIDENCE.get(rule_id, {})
    return {
        "source": e.get("source", "Evidence registry"),
        "title": e.get("title", ""),
        "summary": e.get("summary", ""),
        "verification": e.get("verification", ""),
        "last_reviewed": e.get("last_reviewed", "")
    }

def add_finding(findings, rule_id, severity, title, why, action):
    ev = evidence_card(rule_id)
    findings.append({
        "rule_id": rule_id,
        "severity": severity,
        "title": title,
        "why": why,
        "action": action,
        "evidence": ev
    })

def age_group(age):
    if age is None:
        return None
    if age < 18:
        return "Pediatric"
    if age >= 65:
        return "Geriatric"
    return "Adult"

def analyze(o):
    findings = []
    drug = norm(o["drug"])
    freq = norm(o["frequency"])
    route = norm(o["route"])
    indication = norm(o["indication"])
    unit = norm(o["unit"])
    dose = num(o["dose"])
    age = num(o["age"])
    weight = num(o["weight"])
    egfr = num(o["egfr"])
    alt = num(o["alt"])
    ast = num(o["ast"])
    potassium = num(o["potassium"])
    magnesium = num(o.get("magnesium"))
    sodium = num(o.get("sodium"))
    calcium = num(o.get("calcium"))
    phosphate = num(o.get("phosphate"))
    agegroup = age_group(age)
    meds = [norm(x) for x in o["meds"].split(",") if x.strip()]
    allergy = norm(o["allergy"])

    # High-value order-entry / frequency rules
    if drug == "methotrexate" and any(x in indication for x in ["rheumatoid", "ra", "psoriasis", "inflammatory"]):
        if any(x in freq for x in ["daily", "every day", "qid", "tid", "bid"]):
            add_finding(
                findings, "MTX_WEEKLY",
                "HIGH",
                "Potential frequency error: methotrexate entered more frequently than expected",
                f"Order is {o['dose']} {o['unit']} {o['frequency']} for {o['indication']}. Low-dose methotrexate for inflammatory disease is typically administered on a weekly schedule; a daily frequency can represent a serious order-entry error.",
                "Verify the intended frequency with the prescriber before dispensing/administering."
            )
        if dose is not None and dose > 30 and any(x in freq for x in ["weekly", "once weekly", "qweek"]):
            add_finding(
                findings, "MTX_DOSE_ANOMALY",
                "MODERATE",
                "Methotrexate dose requires verification",
                f"The entered dose is {o['dose']} {o['unit']} per week. The system flags this as outside the common low-dose range used in many inflammatory indications and requests verification rather than automatically suggesting a replacement dose.",
                "Verify indication, formulation, intended weekly dose, and patient-specific factors."
            )

    if "insulin glargine" in drug:
        if any(x in freq for x in ["tid", "three times", "q8h", "every 8 hours"]):
            add_finding(
                findings, "GLARGINE_FREQUENCY",
                "HIGH",
                "Potential frequency anomaly: insulin glargine entered three times daily",
                "Insulin glargine is a basal insulin generally administered once daily in standard regimens. A TID order should be verified because the frequency may represent a selection or transcription error.",
                "Verify the intended basal insulin schedule and formulation with the prescriber."
            )

    # Heparin: deliberately framed as an anomaly detector, not a universal dose checker
    if "heparin" == drug or drug == "unfractionated heparin":
        if unit in ["unit", "units", "u"] and dose is not None and dose >= 5000 and dose <= 10000:
            add_finding(
                findings, "HEPARIN_NUMERIC_ANOMALY",
                "MODERATE",
                "Large numeric heparin dose — verify indication and order context",
                f"The order contains {o['dose']} {o['unit']}. A large numeric value alone is not enough to declare an error because heparin dosing varies substantially by indication, route, and protocol. The system therefore requests contextual verification rather than declaring a wrong dose.",
                "Verify indication, route, protocol, weight-based parameters, and intended dose before processing."
            )

    # ISMP-style dose notation checks
    rawdose = str(o["dose"]).strip()
    if rawdose.startswith(".") and rawdose != ".":
        add_finding(
            findings, "ISMP_LEADING_ZERO",
            "MODERATE",
            "Potential unsafe decimal notation",
            f"The dose was entered as '{rawdose}'. ISMP recommends a leading zero for doses less than one measurement unit (for example, 0.5 rather than .5) because the decimal point can be missed.",
            "Rewrite the order using a leading zero before the decimal."
        )
    if "." in rawdose and rawdose.endswith("0"):
        add_finding(
            findings, "ISMP_TRAILING_ZERO",
            "MODERATE",
            "Potential unsafe trailing-zero notation",
            f"The dose was entered as '{rawdose}'. ISMP recommends avoiding trailing zeros for whole-number doses because 1.0 can be misread as 10.",
            "Remove the trailing zero when the dose is a whole number."
        )

    # Unit plausibility / mismatch examples
    if unit in ["mg", "milligram", "milligrams"] and drug in ["insulin glargine", "insulin lispro", "insulin regular"]:
        add_finding(
            findings, "INSULIN_UNIT",
            "HIGH",
            "Potential insulin unit-entry mismatch",
            f"Insulin was entered with unit '{o['unit']}'. Insulin products are conventionally dosed in units; an mg entry can represent a unit-selection or transcription error.",
            "Verify the insulin product, concentration, dose unit, and intended number of units."
        )

    # Route plausibility
    oral_only = {"warfarin", "methotrexate", "metformin", "apixaban"}
    if drug in oral_only and route in ["iv", "intravenous", "im", "intramuscular"]:
        add_finding(
            findings, "ROUTE_MISMATCH",
            "HIGH",
            "Potential route mismatch",
            f"{o['drug']} was entered via {o['route']}. The route is inconsistent with the standard route represented in this prototype rule set and requires verification.",
            "Verify formulation and intended route with the prescriber/pharmacist."
        )

    # Patient-specific safety flags: these are prompts for verification, not dose recommendations
    if egfr is not None and egfr < 30 and drug in {"metformin", "apixaban", "enoxaparin", "gabapentin", "pregabalin", "digoxin"}:
        add_finding(
            findings, "RENAL_REVIEW",
            "MODERATE",
            "Renal function may materially affect this order",
            f"eGFR is {o['egfr']} mL/min/1.73m². The selected medication can require renal-specific assessment; the prototype intentionally does not auto-recommend a new dose.",
            "Check the patient-specific renal dosing recommendation in an authorized drug reference."
        )

    if (alt is not None and alt > 3*40) or (ast is not None and ast > 3*40):
        if drug in {"methotrexate", "acetaminophen", "isoniazid", "amiodarone"}:
            add_finding(
                findings, "HEPATIC_REVIEW",
                "MODERATE",
                "Liver tests may materially affect this order",
                f"Reported liver enzymes are elevated (ALT {o['alt']}, AST {o['ast']} U/L). This may affect medication safety/monitoring and requires patient-specific review.",
                "Verify hepatic safety, monitoring requirements, and indication using an authorized clinical reference."
            )

    # Interaction prompts
    if drug == "methotrexate" and any(x in meds for x in ["trimethoprim-sulfamethoxazole", "tmp-smx", "tmp/smx", "bactrim"]):
        add_finding(
            findings, "MTX_TMP_SMX",
            "HIGH",
            "Potential clinically significant interaction",
            "Methotrexate and trimethoprim-sulfamethoxazole can have clinically important additive antifolate/toxicity concerns. The combination requires deliberate verification of indication, dosing, monitoring, and alternatives.",
            "Review the interaction in an authorized drug-interaction reference and confirm the prescriber's intent."
        )

    # Allergy check
    if allergy and allergy not in ["none", "no known allergies", "nka", "nkda"]:
        if allergy in drug or drug in allergy:
            add_finding(
                findings, "ALLERGY_MATCH",
                "HIGH",
                "Potential documented allergy match",
                f"The allergy field contains '{o['allergy']}' and the selected medication is '{o['drug']}'.",
                "Stop and verify the allergy history and intended medication before administration."
            )

    # Age-group safety prompts: intentionally generic and verification-only
    if agegroup == "Pediatric":
        if weight is None:
            add_finding(
                findings, "PEDIATRIC_CONTEXT", "MODERATE",
                "Pediatric order requires weight verification",
                "The patient is pediatric and no current weight was provided. Pediatric medication assessment often depends on age, weight, indication, and a medication-specific maximum dose.",
                "Verify current weight, age, indication, weight-based dose, and medication-specific maximum dose in an authorized reference."
            )
        elif dose is not None and weight > 0:
            add_finding(
                findings, "PEDIATRIC_REVIEW", "LOW",
                "Pediatric dosing context requires verification",
                f"Patient age is {o['age']} years and weight is {o['weight']} kg. The prototype does not assume an adult dose is appropriate for a pediatric patient.",
                "Verify the age/weight-based regimen and maximum dose in the authorized pediatric reference."
            )
    elif agegroup == "Geriatric":
        add_finding(
            findings, "GERIATRIC_REVIEW", "LOW",
            "Geriatric medication review prompted",
            f"Patient age is {o['age']} years. Age-related pharmacokinetic changes, renal function, polypharmacy, and medication-specific precautions may affect the order.",
            "Verify indication, dose, frequency, renal function, and relevant geriatric precautions in an authorized reference."
        )

    # Electrolyte safety prompts. These are deliberately threshold-based screening flags, not replacement-dose recommendations.
    electrolyte_specs = [
        ("potassium", potassium, "POTASSIUM_REVIEW", "Potassium"),
        ("magnesium", magnesium, "MAGNESIUM_REVIEW", "Magnesium"),
        ("sodium", sodium, "SODIUM_REVIEW", "Sodium"),
        ("calcium", calcium, "CALCIUM_REVIEW", "Calcium"),
        ("phosphate", phosphate, "PHOSPHATE_REVIEW", "Phosphate"),
    ]
    for key, value, rule_id, label in electrolyte_specs:
        if value is not None and label == "Potassium" and (value < 3.0 or value > 6.0):
            add_finding(findings, rule_id, "HIGH", f"{label} value requires medication-order verification",
                        f"The entered {label} is {o['potassium']} mmol/L. An abnormal electrolyte can materially change the safety of replacement or other medication orders.",
                        f"Verify the latest {label} result, indication, ordered dose/concentration, route, and administration parameters before processing.")
        elif value is not None and label != "Potassium":
            # Broad abnormality prompts use common adult reference boundaries only as screening triggers; they are not treatment targets.
            bounds = {
                "Magnesium": (1.2, 2.6),
                "Sodium": (130, 150),
                "Calcium": (7.5, 11.0),
                "Phosphate": (2.0, 5.5),
            }[label]
            if value < bounds[0] or value > bounds[1]:
                add_finding(findings, rule_id, "MODERATE", f"{label} value requires medication-order verification",
                            f"The entered {label} is {value}. This is outside the prototype's broad screening range and may affect the safety of electrolyte replacement or related medication orders.",
                            f"Verify the latest {label} result, clinical indication, ordered dose/concentration, route, and administration parameters using the hospital protocol or authorized reference.")

    # Weight-based screening: only flags when a medication commonly needs weight context.
    if drug in {"enoxaparin", "vancomycin", "gentamicin", "tobramycin", "amikacin"} and weight is None:
        add_finding(findings, "MISSING_WEIGHT", "MODERATE",
                    "Weight is missing for a medication that may require weight-based assessment",
                    "Patient weight was not provided. The prototype therefore cannot safely perform a weight-based plausibility check.",
                    "Obtain/verify current weight before relying on a dose assessment.")

    # Missing-data flags


    return findings

# Sidebar: simulated cases
st.sidebar.header("🧪 Simulated cases")
cases = {
    "Case 1 — Methotrexate frequency": {"drug":"Methotrexate","dose":"15","unit":"mg","route":"PO","frequency":"Once daily","duration":"30 days","indication":"Rheumatoid arthritis","age":"65","weight":"72","egfr":"58","alt":"32","ast":"29","potassium":"4.3","magnesium":"2.0","sodium":"139","calcium":"9.2","phosphate":"3.4","meds":"","allergy":"None"},
    "Case 2 — Insulin glargine frequency": {"drug":"Insulin glargine","dose":"20","unit":"units","route":"SC","frequency":"TID","duration":"Ongoing","indication":"Type 2 diabetes","age":"61","weight":"92","egfr":"72","alt":"28","ast":"24","potassium":"4.5","magnesium":"2.0","sodium":"140","calcium":"9.1","phosphate":"3.5","meds":"metformin","allergy":"None"},
    "Case 3 — Heparin numeric anomaly": {"drug":"Unfractionated heparin","dose":"8000","unit":"units","route":"IV","frequency":"Once","duration":"One-time","indication":"Anticoagulation","age":"54","weight":"80","egfr":"75","alt":"30","ast":"27","potassium":"4.1","magnesium":"2.0","sodium":"138","calcium":"9.0","phosphate":"3.2","meds":"","allergy":"None"},
    "Case 4 — Decimal notation": {"drug":"Warfarin","dose":".5","unit":"mg","route":"PO","frequency":"Once daily","duration":"7 days","indication":"Atrial fibrillation","age":"70","weight":"78","egfr":"60","alt":"25","ast":"22","potassium":"4.2","magnesium":"2.0","sodium":"140","calcium":"9.3","phosphate":"3.4","meds":"","allergy":"None"},
    "Case 5 — Pediatric review": {"drug":"Amoxicillin","dose":"500","unit":"mg","route":"PO","frequency":"Three times daily","duration":"7 days","indication":"Bacterial infection","age":"8","weight":"25","egfr":"95","alt":"20","ast":"19","potassium":"4.1","magnesium":"2.0","sodium":"139","calcium":"9.4","phosphate":"4.2","meds":"","allergy":"None"},
    "Case 6 — Geriatric review": {"drug":"Digoxin","dose":"0.25","unit":"mg","route":"PO","frequency":"Once daily","duration":"Ongoing","indication":"Atrial fibrillation","age":"82","weight":"62","egfr":"38","alt":"24","ast":"23","potassium":"4.0","magnesium":"1.9","sodium":"138","calcium":"9.1","phosphate":"3.1","meds":"","allergy":"None"},
    "Case 7 — Potassium abnormality": {"drug":"Potassium chloride","dose":"40","unit":"mEq","route":"PO","frequency":"Once","duration":"One-time","indication":"Electrolyte replacement","age":"56","weight":"75","egfr":"42","alt":"22","ast":"20","potassium":"6.2","magnesium":"2.0","sodium":"139","calcium":"9.0","phosphate":"3.2","meds":"lisinopril","allergy":"None"},
    "Case 8 — Magnesium abnormality": {"drug":"Magnesium sulfate","dose":"2","unit":"g","route":"IV","frequency":"Once","duration":"One-time","indication":"Electrolyte replacement","age":"48","weight":"70","egfr":"50","alt":"20","ast":"18","potassium":"4.0","magnesium":"1.0","sodium":"140","calcium":"8.8","phosphate":"3.0","meds":"","allergy":"None"},
    "Case 9 — Renal review": {"drug":"Enoxaparin","dose":"40","unit":"mg","route":"SC","frequency":"Once daily","duration":"7 days","indication":"VTE prophylaxis","age":"79","weight":"","egfr":"22","alt":"26","ast":"25","potassium":"4.4","magnesium":"2.0","sodium":"139","calcium":"9.2","phosphate":"3.3","meds":"","allergy":"None"},
}

selected = st.sidebar.selectbox("Load a fictional case", ["— Select —"] + list(cases))
defaults = cases.get(selected, {k:"" for k in ["drug","dose","unit","route","frequency","duration","indication","age","weight","egfr","alt","ast","potassium","magnesium","sodium","calcium","phosphate","meds","allergy"]})

with st.form("order_form"):
    st.subheader("1. Medication order")
    c1,c2,c3 = st.columns(3)
    drug = c1.text_input("Drug", value=defaults["drug"], placeholder="e.g., Methotrexate")
    dose = c2.text_input("Dose", value=defaults["dose"], placeholder="e.g., 15")
    unit = c3.text_input("Unit", value=defaults["unit"], placeholder="e.g., mg")

    c1,c2,c3 = st.columns(3)
    route = c1.text_input("Route", value=defaults["route"], placeholder="e.g., PO")
    frequency = c2.text_input("Frequency", value=defaults["frequency"], placeholder="e.g., Once daily")
    duration = c3.text_input("Duration", value=defaults["duration"], placeholder="e.g., 7 days")

    indication = st.text_input("Indication", value=defaults["indication"], placeholder="e.g., Rheumatoid arthritis")

    st.subheader("2. Patient factors")
    c1,c2,c3,c4 = st.columns(4)
    age = c1.text_input("Age (years)", value=defaults["age"])
    weight = c2.text_input("Weight (kg)", value=defaults["weight"])
    egfr = c3.text_input("eGFR (mL/min/1.73m²)", value=defaults["egfr"])
    alt = c4.text_input("ALT (U/L)", value=defaults["alt"])

    c1,c2,c3 = st.columns(3)
    ast = c1.text_input("AST (U/L)", value=defaults["ast"])
    potassium = c2.text_input("Potassium (mmol/L)", value=defaults["potassium"])
    magnesium = c3.text_input("Magnesium (mg/dL)", value=defaults.get("magnesium", ""))

    c1,c2,c3 = st.columns(3)
    sodium = c1.text_input("Sodium (mmol/L)", value=defaults.get("sodium", ""))
    calcium = c2.text_input("Calcium (mg/dL)", value=defaults.get("calcium", ""))
    phosphate = c3.text_input("Phosphate (mg/dL)", value=defaults.get("phosphate", ""))

    meds = st.text_input("Current medications (comma-separated)", value=defaults["meds"])

    allergy = st.text_input("Allergies", value=defaults["allergy"], placeholder="e.g., penicillin, none")

    submitted = st.form_submit_button("🔎 Analyze order", use_container_width=True)

if submitted:
    order = locals()
    findings = analyze(order)
    st.divider()
    st.subheader("3. Analysis result")

    if not findings:
        st.success("No rule-based anomaly detected in this prototype. This does NOT mean the order is clinically appropriate.")
    else:
        sev_order = {"HIGH":0,"MODERATE":1,"LOW":2}
        findings.sort(key=lambda x: sev_order.get(x["severity"], 9))
        for f in findings:
            box = st.error if f["severity"] == "HIGH" else st.warning
            box(f"**{f['severity']} — {f['title']}**")
            st.write(f["why"])
            st.markdown(f"**Recommended pharmacist action:** {f['action']}")
            with st.expander("📚 Evidence / basis for the flag"):
                st.write(f"**Source:** {f['evidence']['source']}")
                st.write(f"**Reference:** {f['evidence']['title']}")
                st.write(f"**Evidence summary:** {f['evidence']['summary']}")
                st.write(f"**Verification:** {f['evidence']['verification']}")
                st.caption(f"Registry last reviewed: {f['evidence']['last_reviewed']}")

    st.subheader("4. Explainability")
    st.info(
        "The prototype does not silently change the order. It identifies a potential anomaly, explains the trigger, "
        "shows the evidence source, and leaves the final decision to the pharmacist/prescriber."
    )

st.divider()
st.caption("Prototype architecture: structured order → evidence-grounded rule engine → explainable finding → pharmacist verification → review log.")
