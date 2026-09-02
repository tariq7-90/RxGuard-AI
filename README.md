# RxGuard-AI

**Evidence-Based Medication Order Verification**

RxGuard AI is a research and demonstration prototype designed to support pharmacists in identifying potential prescribing/order-entry anomalies before medication administration.

## Project structure

```text
RxGuard-AI/
├── app.py
├── requirements.txt
├── README.md
└── data/
    └── evidence_registry.json
```

## Run locally

```bash
python -m venv .venv
```

Activate the environment, then:

```bash
pip install -r requirements.txt
python app.py
```

Open the local address shown by Flask.

## Design

```text
Medication Order
       ↓
Patient Context
       ↓
Evidence Registry
       ↓
Rule-Based Analysis
       ↓
Explainable Alert
       ↓
Pharmacist Verification
```

The current prototype uses transparent, rule-based checks. It is **not a validated AI/ML clinical decision-support system**.

## Evidence approach

The evidence registry is intentionally separated from the application logic. In a production system, evidence should be controlled, versioned, institutionally approved, and integrated through licensed sources where required.

Potential future integrations include:

- Hospital-approved protocols
- Licensed drug-information databases such as UpToDate/Micromedex
- Clinical guidelines
- EHR/BestCare integration
- Explainable AI/LLM layer with pharmacist review

The prototype does not connect to these systems.

## Safety

RxGuard AI does not autonomously prescribe, discontinue, or modify medications.

A production implementation would require clinical validation, medication-safety governance, cybersecurity review, institutional approval, licensed evidence integration, and controlled EHR integration.

## Disclaimer

All demonstration data are fictional. This prototype must not be used for real patient care, prescribing, dispensing, or medication administration decisions.
