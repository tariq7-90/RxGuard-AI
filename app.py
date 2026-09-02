import json
from pathlib import Path
import streamlit as st

st.set_page_config(page_title="RxGuard AI", page_icon="🛡️", layout="wide")

REGISTRY_PATH = Path(__file__).parent / "data" / "evidence_registry.json"
with open(REGISTRY_PATH, "r", encoding="utf-8") as f:
    EVIDENCE = json.load(f)


def age_to_days(age, unit):
    if unit == "Days":
        return age
    if unit == "Months":
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


def evidence_text(key):
    ev = EVIDENCE[key]
    return f'{ev["source"]} — {ev["reference"]}'


def analyze_order(age, age_unit, weight, renal, allergies, indication, drug, dose, unit,
                  route, frequency, neonatal_ga=None, neonatal_pna=None, current_medication=""):
    category = classify_age(age_to_days(age, age_unit))
    factors = [f"Age category: {category}"]
    if weight:
        factors.append(f"Weight: {weight:g} kg")
    if renal is not None:
        factors.append(f"Renal function: {renal:g} mL/min")
    if allergies.strip():
        factors.append(f"Allergies: {allergies.strip()}")
    if neonatal_ga is not None:
        factors.append(f"GA at birth: {neonatal_ga:g} weeks")
    if neonatal_pna is not None:
        factors.append(f"PNA: {neonatal_pna:g} days")

    drug_l = drug.strip().lower()
    freq_l = frequency.strip().lower()
    indication_l = indication.strip().lower()

    # 1. Methotrexate frequency
    if drug_l in {"methotrexate", "mtx"} and ("daily" in freq_l or freq_l in {"qd", "od"}):
        return {
            "level": "red",
            "title": "Potential Prescribing Error",
            "detected": "Methotrexate is ordered with a daily frequency.",
            "where": f"Frequency field: {frequency}. The concern is the administration frequency, not the 10 mg dose itself.",
            "correct": "For the demonstrated non-oncologic indication, verify whether the intended regimen is 10 mg PO once weekly.",
            "action": "Pharmacist should verify the indication and contact the prescriber before any change. Do not autonomously modify the order.",
            "factors": "; ".join(factors),
            "evidence": evidence_text("methotrexate_weekly"),
        }

    # 2. Gabapentin renal dosing
    if drug_l in {"gabapentin", "neurontin"} and renal is not None and 15 < renal < 30 and "tid" in freq_l:
        daily = dose * 3
        if daily > 700:
            return {
                "level": "red",
                "title": "Potential Prescribing Error",
                "detected": f"Gabapentin total daily dose is {daily:g} mg/day with CrCl {renal:g} mL/min.",
                "where": f"Dose + frequency fields: {dose:g} {unit} {frequency} = {daily:g} {unit}/day.",
                "correct": "Use a renal-adjusted regimen appropriate for CrCl >15–29 mL/min; the cited labeling lists 200–700 mg/day with once-daily regimens. The exact regimen must be clinically verified.",
                "action": "Pharmacist should verify indication, current renal function, and patient response, then recommend an appropriate renal-adjusted regimen to the prescriber.",
                "factors": "; ".join(factors),
                "evidence": evidence_text("gabapentin_renal"),
            }

    # 3. Neonatal ampicillin
    if drug_l == "ampicillin" and category == "Neonate" and "q8" in freq_l:
        if neonatal_ga is not None and neonatal_pna is not None and weight:
            if neonatal_ga <= 34 and neonatal_pna <= 7:
                daily_mg = 100 * weight
                per_dose = daily_mg / 2
                correct = f"For the demonstrated meningitis/septicemia label scenario: {daily_mg:g} mg/day divided q12h = {per_dose:g} mg IV q12h. Confirm indication and local neonatal protocol before changing."
            else:
                correct = "Do not infer a correction from age alone. Verify gestational age, postnatal age, indication, weight, and the applicable neonatal protocol."
        else:
            correct = "Verify gestational age, postnatal age, indication, weight, and the applicable neonatal protocol before determining the correct regimen."
        return {
            "level": "red",
            "title": "Potential Prescribing Error",
            "detected": "Neonatal ampicillin is ordered q8h and requires patient-specific neonatal dosing assessment.",
            "where": f"Frequency field: {frequency}. Neonatal dose selection depends on gestational age and postnatal age.",
            "correct": correct,
            "action": "Pharmacist should verify the neonatal dosing parameters and applicable indication/protocol, then contact the prescriber if correction is needed.",
            "factors": "; ".join(factors),
            "evidence": evidence_text("ampicillin_neonate") + " " + evidence_text("neonatal_pharmacology"),
        }

    # 4. Insulin glargine frequency
    if drug_l in {"insulin glargine", "lantus"} and ("bid" in freq_l or "twice" in freq_l):
        return {
            "level": "red",
            "title": "Potential Prescribing Error",
            "detected": "Insulin glargine is ordered twice daily in this demonstration.",
            "where": f"Frequency field: {frequency}. The concern is the frequency, not necessarily the 20-unit dose.",
            "correct": "Verify whether the intended regimen is insulin glargine once daily, consistent with the referenced labeling, with dose individualized to the patient.",
            "action": "Because insulin is high-alert, pharmacist verification is required. Contact the prescriber before any change.",
            "factors": "; ".join(factors),
            "evidence": "DailyMed / Insulin Glargine (Lantus) Prescribing Information — administered subcutaneously once daily; dose is individualized. ISMP lists insulin as a high-alert medication.",
        }

    # 5. Methotrexate + TMP/SMX interaction
    if drug_l in {"trimethoprim/sulfamethoxazole", "trimethoprim-sulfamethoxazole", "tmp/smx", "co-trimoxazole", "cotrimoxazole"} and "methotrexate" in current_medication.lower():
        return {
            "level": "red",
            "title": "Clinically Significant Drug Interaction — Pharmacist Review",
            "detected": "Trimethoprim/sulfamethoxazole is ordered while methotrexate is listed as a current medication.",
            "where": "Medication list / interaction check: TMP/SMX + methotrexate.",
            "correct": "Do not automatically substitute or discontinue therapy. Verify the indication and prescriber intent; consider an alternative or modified plan when clinically appropriate.",
            "action": "Pharmacist should assess the interaction, renal function, indication, and alternatives, then discuss with the prescriber.",
            "factors": "; ".join(factors),
            "evidence": "DailyMed / Trimethoprim-Sulfamethoxazole Prescribing Information — avoid concurrent use with methotrexate due to increased free methotrexate concentrations.",
        }

    # 6. High-alert medications: not automatically an error
    if drug_l in {"heparin", "unfractionated heparin", "insulin", "insulin glargine"}:
        return {
            "level": "yellow",
            "title": "High-Alert / Enhanced Verification",
            "detected": "The medication is classified as high-alert in the referenced medication-safety source.",
            "where": "Medication selection: high-alert medication identified.",
            "correct": "No automatic correction is suggested. The order may be appropriate; it requires enhanced verification.",
            "action": "Pharmacist should verify indication, dose, route, frequency, monitoring, and patient-specific factors. High-alert status alone does not mean the order is wrong.",
            "factors": "; ".join(factors),
            "evidence": evidence_text("high_alert"),
        }

    # 7. No configured anomaly
    return {
        "level": "green",
        "title": "No Significant Anomaly Detected",
        "detected": "No configured demonstration rule was triggered by the supplied information.",
        "where": "No specific anomaly identified by the current prototype rules.",
        "correct": "No automatic correction suggested.",
        "action": "Continue standard clinical pharmacist verification. This result is not a guarantee that the order is safe or appropriate.",
        "factors": "; ".join(factors),
        "evidence": "Configured RxGuard AI evidence registry / applicable clinical references.",
    }


st.markdown("""
<style>
.main-title{font-size:42px;font-weight:800;margin-bottom:0}.subtitle{font-size:20px;color:#667085;margin-bottom:8px}.tagline{font-size:16px;color:#475467}
.result{padding:22px;border-radius:10px;border-left:8px solid;margin-bottom:12px;color:#101828 !important;background:#fff}.result *{color:#101828 !important}.result h3{margin-top:0;color:#101828 !important}.result p{color:#344054 !important}
.red{border-left-color:#d92d20;background:#fff5f4}.orange{border-left-color:#f79009;background:#fff8eb}.yellow{border-left-color:#fdb022;background:#fffdf0}.green{border-left-color:#12b76a;background:#f1fcf6}
.result h3{color:#101828 !important}.result p{color:#344054 !important;line-height:1.6}.result b{color:#101828 !important}
</style>
""", unsafe_allow_html=True)

st.markdown('<div class="main-title">🛡️ RxGuard AI</div>', unsafe_allow_html=True)
st.markdown('<div class="subtitle">Evidence-Based Medication Order Verification</div>', unsafe_allow_html=True)
st.markdown('<div class="tagline">Detect potential prescribing errors before they reach the patient.</div>', unsafe_allow_html=True)
st.divider()

st.header("Patient Information")
c1,c2,c3=st.columns(3)
with c1:
    age=st.number_input("Age", min_value=0.0, value=45.0, step=1.0)
    age_unit=st.selectbox("Age Unit", ["Years","Months","Days"])
with c2:
    weight=st.number_input("Weight (kg)", min_value=0.0, value=70.0, step=0.1)
    renal=st.number_input("Renal Function (CrCl / eGFR as applicable)", min_value=0.0, value=0.0, step=1.0)
with c3:
    allergies=st.text_input("Allergies")
    indication=st.text_input("Clinical Indication", placeholder="e.g., rheumatoid arthritis")

category=classify_age(age_to_days(age,age_unit))
st.info(f"**Auto Age Category:** {category}")

neonatal_ga=None; neonatal_pna=None
if category=="Neonate":
    st.subheader("Neonatal Factors")
    n1,n2=st.columns(2)
    with n1:
        neonatal_ga=st.number_input("Gestational Age at Birth (weeks)", min_value=20.0, max_value=45.0, value=37.0, step=1.0)
    with n2:
        neonatal_pna=st.number_input("Postnatal Age (days)", min_value=0.0, value=max(0.0,age), step=1.0)

st.divider(); st.header("Medication Order")
m1,m2=st.columns(2)
with m1:
    drug=st.text_input("Drug", placeholder="e.g., methotrexate")
    dose=st.number_input("Dose", min_value=0.0, value=10.0, step=0.1)
    unit=st.text_input("Unit", placeholder="mg / units / mg/kg")
with m2:
    route=st.text_input("Route", placeholder="PO / IV / SC")
    frequency=st.text_input("Frequency", placeholder="once daily / once weekly / q8h")
    current_medication=st.text_input("Current Medication(s) — optional", placeholder="e.g., Methotrexate 10 mg PO once weekly")

st.divider()
if st.button("🔎 Analyze Medication Order", type="primary", use_container_width=True):
    if not drug.strip():
        st.error("Please enter a medication.")
        st.stop()
    result=analyze_order(age,age_unit,weight,renal if renal>0 else None,allergies,indication,drug,dose,unit,route,frequency,neonatal_ga,neonatal_pna,current_medication)
    st.subheader("Analysis Result")
    st.markdown(f"""
    <div class="result {result['level']}">
      <h3>{result['title']}</h3>
      <p><b>What was detected?</b><br>{result['detected']}</p>
      <p><b>Where is the issue?</b><br>{result['where']}</p>
      <p><b>What would be appropriate?</b><br>{result['correct']}</p>
      <p><b>Patient factors considered</b><br>{result['factors']}</p>
      <p><b>Required pharmacist action</b><br>{result['action']}</p>
      <p><b>Evidence / Source</b><br>{result['evidence']}</p>
    </div>
    """, unsafe_allow_html=True)

    st.markdown("### Pharmacist Verification")
    st.caption("The pharmacist reviews the alert, verifies the evidence and clinical context, and communicates with the prescriber when needed.")
    a1, a2 = st.columns(2)
    with a1:
        if st.button("✅ Confirm Order", use_container_width=True):
            st.success("Order reviewed and confirmed by pharmacist (demonstration only).")
    with a2:
        if st.button("✏️ Recommend Correction", use_container_width=True):
            st.info("Pharmacist should document the recommended correction and reason, then communicate with the prescriber. RxGuard AI does not modify the EHR order automatically.")

    st.warning("Pharmacist verification required. RxGuard AI identifies potential issues and provides evidence; it does not autonomously modify medication orders.")

st.divider(); st.subheader("Safety Disclaimer")
st.markdown("""
**Research and demonstration prototype only.**

This application is not connected to BestCare, hospital EHR systems, patient records, UpToDate, Micromedex, or other clinical databases. It must not be used for real prescribing, dispensing, or medication administration decisions. All demonstration data are fictional.
""")
st.caption("RxGuard AI — Medication Order → Patient Context → Evidence → Pharmacist Verification")
