import json
from pathlib import Path

import streamlit as st


# ---------------------------------------------------------
# Configuration
# ---------------------------------------------------------

st.set_page_config(
    page_title="RxGuard AI",
    page_icon="🛡️",
    layout="wide"
)

REGISTRY_PATH = Path(__file__).parent / "data" / "evidence_registry.json"

with open(REGISTRY_PATH, "r", encoding="utf-8") as f:
    EVIDENCE = json.load(f)


# ---------------------------------------------------------
# Helper functions
# ---------------------------------------------------------

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


def analyze_order(
    age,
    age_unit,
    weight,
    renal,
    allergies,
    indication,
    drug,
    dose,
    unit,
    route,
    frequency,
    neonatal_ga=None,
    neonatal_pna=None
):
    days = age_to_days(age, age_unit)
    category = classify_age(days)

    factors = f"Age category: {category}"

    if weight:
        factors += f"; weight: {weight:g} kg"

    if renal is not None:
        factors += f"; renal function: {renal:g}"

    drug_l = drug.strip().lower()
    indication_l = indication.strip().lower()
    frequency_l = frequency.strip().lower()

    # --------------------------------------------------
    # Methotrexate frequency rule
    # --------------------------------------------------

    if (
        drug_l in {"methotrexate", "mtx"}
        and ("daily" in frequency_l or "qd" in frequency_l)
    ):
        ev = EVIDENCE["methotrexate_weekly"]

        return {
            "level": "red",
            "title": "Potential Prescribing Error",
            "detected": (
                "Methotrexate is ordered with a daily frequency."
            ),
            "reason": (
                "For the demonstrated non-oncologic indications, "
                "the referenced labeling uses once-weekly administration. "
                "Daily-vs-weekly frequency errors are a known serious "
                "medication-safety risk."
            ),
            "factors": factors,
            "action": (
                "Verify the indication and contact the prescriber. "
                "Consider correction to the appropriate weekly regimen "
                "only after clinical confirmation."
            ),
            "evidence": (
                f'{ev["source"]} — {ev["reference"]}'
            )
        }

    # --------------------------------------------------
    # Gabapentin renal rule
    # --------------------------------------------------

    if (
        drug_l in {"gabapentin", "neurontin"}
        and renal is not None
        and 15 < renal < 30
        and dose * 3 > 700
        and "tid" in frequency_l
    ):
        ev = EVIDENCE["gabapentin_renal"]

        return {
            "level": "red",
            "title": "Potential Prescribing Error",
            "detected": (
                "The entered gabapentin daily dose appears above "
                "the labeled renal-adjusted range for CrCl >15–29 mL/min."
            ),
            "reason": (
                "Gabapentin is renally cleared and the cited labeling "
                "provides a substantially lower total daily dose range "
                "for this renal function."
            ),
            "factors": (
                f"{factors}; ordered daily dose: "
                f"{dose * 3:g} {unit}/day (assuming TID)."
            ),
            "action": (
                "Verify the indication, renal function, and regimen; "
                "select an appropriate renal-adjusted regimen."
            ),
            "evidence": (
                f'{ev["source"]} — {ev["reference"]}'
            )
        }

    # --------------------------------------------------
    # Neonatal ampicillin verification
    # --------------------------------------------------

    if (
        drug_l == "ampicillin"
        and category == "Neonate"
        and "q8" in frequency_l
    ):
        ev = EVIDENCE["ampicillin_neonate"]

        neonatal_info = ""

        if (
            neonatal_ga is not None
            and neonatal_pna is not None
        ):
            neonatal_info = (
                f"; GA at birth: {neonatal_ga:g} weeks; "
                f"PNA: {neonatal_pna:g} days"
            )

        return {
            "level": "orange",
            "title": "Patient-Specific Verification Required",
            "detected": (
                "Neonatal ampicillin dosing requires assessment "
                "of gestational age and postnatal age."
            ),
            "reason": (
                "Neonatal ampicillin dosing can depend on gestational "
                "age and postnatal age; weight alone is insufficient."
            ),
            "factors": (
                factors + neonatal_info
            ),
            "action": (
                "Verify gestational age, postnatal age, indication, "
                "and the applicable institutional neonatal protocol "
                "before changing the order."
            ),
            "evidence": (
                f'{ev["source"]} — {ev["reference"]}'
            )
        }

    # --------------------------------------------------
    # High-alert medication
    # --------------------------------------------------

    if drug_l in {
        "heparin",
        "unfractionated heparin",
        "insulin",
        "insulin glargine"
    }:
        ev = EVIDENCE["high_alert"]

        return {
            "level": "yellow",
            "title": "High-Alert / Enhanced Verification",
            "detected": (
                "The medication is categorized as high-alert "
                "in the referenced medication-safety source."
            ),
            "reason": (
                "High-alert status means that an error can cause "
                "significant harm; it does not by itself mean that "
                "this order is incorrect."
            ),
            "factors": factors,
            "action": (
                "Perform enhanced pharmacist verification of indication, "
                "dose, route, frequency, and monitoring requirements."
            ),
            "evidence": (
                f'{ev["source"]} — {ev["reference"]}'
            )
        }

    # --------------------------------------------------
    # No anomaly
    # --------------------------------------------------

    return {
        "level": "green",
        "title": "No Significant Anomaly Detected",
        "detected": (
            "No demonstration rule was triggered by the supplied information."
        ),
        "reason": (
            "This result means only that the current prototype did not "
            "identify a configured anomaly. It is not a guarantee of "
            "safety or appropriateness."
        ),
        "factors": factors,
        "action": (
            "Continue standard clinical pharmacist verification."
        ),
        "evidence": (
            "Configured RxGuard AI evidence registry."
        )
    }


# ---------------------------------------------------------
# Styling
# ---------------------------------------------------------

st.markdown(
    """
    <style>

    .main-title {
        font-size: 42px;
        font-weight: 800;
        margin-bottom: 0;
    }

    .subtitle {
        font-size: 20px;
        color: #667085;
        margin-bottom: 8px;
    }

    .tagline {
        font-size: 16px;
        color: #475467;
    }

    .alert-red {
        padding: 18px;
        border-left: 7px solid #d92d20;
        background: #fff1f0;
        border-radius: 8px;
    }

    .alert-orange {
        padding: 18px;
        border-left: 7px solid #f79009;
        background: #fff7e6;
        border-radius: 8px;
    }

    .alert-yellow {
        padding: 18px;
        border-left: 7px solid #fdb022;
        background: #fffbe6;
        border-radius: 8px;
    }

    .alert-green {
        padding: 18px;
        border-left: 7px solid #12b76a;
        background: #ecfdf3;
        border-radius: 8px;
    }

    .small-note {
        color: #667085;
        font-size: 13px;
    }

    </style>
    """,
    unsafe_allow_html=True
)


# ---------------------------------------------------------
# Header
# ---------------------------------------------------------

st.markdown(
    '<div class="main-title">🛡️ RxGuard AI</div>',
    unsafe_allow_html=True
)

st.markdown(
    '<div class="subtitle">'
    'Evidence-Based Medication Order Verification'
    '</div>',
    unsafe_allow_html=True
)

st.markdown(
    '<div class="tagline">'
    'Detect potential prescribing errors before they reach the patient.'
    '</div>',
    unsafe_allow_html=True
)

st.divider()


# ---------------------------------------------------------
# Patient Information
# ---------------------------------------------------------

st.header("Patient Information")

col1, col2, col3 = st.columns(3)

with col1:

    age = st.number_input(
        "Age",
        min_value=0.0,
        value=45.0,
        step=1.0
    )

    age_unit = st.selectbox(
        "Age Unit",
        [
            "Years",
            "Months",
            "Days"
        ]
    )


with col2:

    weight = st.number_input(
        "Weight (kg)",
        min_value=0.0,
        value=70.0,
        step=0.1
    )

    renal = st.number_input(
        "Renal Function (CrCl / eGFR as applicable)",
        min_value=0.0,
        value=0.0,
        step=1.0
    )


with col3:

    allergies = st.text_input(
        "Allergies"
    )

    indication = st.text_input(
        "Clinical Indication",
        placeholder="e.g., rheumatoid arthritis"
    )


# ---------------------------------------------------------
# Automatic age category
# ---------------------------------------------------------

category = classify_age(
    age_to_days(
        age,
        age_unit
    )
)

st.info(
    f"**Auto Age Category:** {category}"
)


# ---------------------------------------------------------
# Neonatal fields
# ---------------------------------------------------------

neonatal_ga = None
neonatal_pna = None

if category == "Neonate":

    st.subheader(
        "Neonatal Factors"
    )

    n1, n2 = st.columns(2)

    with n1:

        neonatal_ga = st.number_input(
            "Gestational Age at Birth (weeks)",
            min_value=20.0,
            max_value=45.0,
            value=37.0,
            step=1.0
        )

    with n2:

        neonatal_pna = st.number_input(
            "Postnatal Age (days)",
            min_value=0.0,
            value=max(0.0, age),
            step=1.0
        )


st.divider()


# ---------------------------------------------------------
# Medication Order
# ---------------------------------------------------------

st.header(
    "Medication Order"
)

m1, m2 = st.columns(2)

with m1:

    drug = st.text_input(
        "Drug",
        placeholder="e.g., methotrexate"
    )

    dose = st.number_input(
        "Dose",
        min_value=0.0,
        value=10.0,
        step=0.1
    )

    unit = st.text_input(
        "Unit",
        placeholder="mg / units / mg/kg"
    )


with m2:

    route = st.text_input(
        "Route",
        placeholder="PO / IV / SC"
    )

    frequency = st.text_input(
        "Frequency",
        placeholder="once daily / once weekly / q8h"
    )


st.divider()


# ---------------------------------------------------------
# Analyze
# ---------------------------------------------------------

if st.button(
    "🔎 Analyze Medication Order",
    type="primary",
    use_container_width=True
):

    if not drug.strip():

        st.error(
            "Please enter a medication."
        )

        st.stop()


    result = analyze_order(

        age=age,

        age_unit=age_unit,

        weight=weight,

        renal=(
            renal
            if renal > 0
            else None
        ),

        allergies=allergies,

        indication=indication,

        drug=drug,

        dose=dose,

        unit=unit,

        route=route,

        frequency=frequency,

        neonatal_ga=neonatal_ga,

        neonatal_pna=neonatal_pna
    )


    level_class = (
        f"alert-{result['level']}"
    )


    st.subheader(
        "Analysis Result"
    )


    st.markdown(

        f"""
        <div class="{level_class}">

        <h3>
        {result["title"]}
        </h3>

        <p>
        <b>What was detected?</b><br>
        {result["detected"]}
        </p>

        <p>
        <b>Why flagged?</b><br>
        {result["reason"]}
        </p>

        <p>
        <b>Patient factors</b><br>
        {result["factors"]}
        </p>

        <p>
        <b>Recommended action</b><br>
        {result["action"]}
        </p>

        <p>
        <b>Evidence</b><br>
        {result["evidence"]}
        </p>

        </div>
        """,

        unsafe_allow_html=True
    )


    st.warning(
        "Pharmacist verification required. "
        "RxGuard AI does not autonomously modify medication orders."
    )


# ---------------------------------------------------------
# Footer
# ---------------------------------------------------------

st.divider()

st.subheader(
    "Safety Disclaimer"
)

st.markdown(
    """
    **Research and demonstration prototype only.**

    This application is not connected to BestCare, hospital EHR systems,
    patient records, UpToDate, Micromedex, or other clinical databases.

    It must not be used for real prescribing, dispensing, or medication
    administration decisions.

    All demonstration data are fictional.
    """
)

st.caption(
    "RxGuard AI — Medication Order → Patient Context → Evidence → Pharmacist Verification"
)
