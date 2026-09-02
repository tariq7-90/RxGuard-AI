
# RxGuard AI — Evidence-Grounded Medication Order Safety Analyzer

## What this is
A research/demo prototype that analyzes a fictional medication order using structured fields:
Drug, Dose, Unit, Route, Frequency, Duration, Indication, Age, Weight, Renal function, Hepatic function, Relevant labs, Current medications, and Allergies.

## Important scientific limitation
The current prototype is NOT a validated clinical AI model and is NOT connected to UpToDate, Micromedex, Lexicomp, or any hospital system.

The detection layer is a transparent, rule-based evidence prototype. This is intentional for the first research version: every alert can be traced to a rule and an evidence source instead of pretending that a black-box model has clinical validation.

A future version can add an LLM explanation layer or a licensed drug-information API, but the safety-critical detection rules should remain auditable.

## Safety behavior
The app:
1. Detects a potential anomaly.
2. Explains exactly what triggered it.
3. Shows the evidence source and a short evidence summary.
4. Recommends pharmacist/prescriber verification.
5. Never automatically changes the order.

## Simulated cases
- Methotrexate 15 mg PO once daily for rheumatoid arthritis
- Insulin glargine 20 units SC TID
- Unfractionated heparin 8,000 units IV once
- Warfarin 0.5 mg entered as ".5"
- Enoxaparin 40 mg SC daily with eGFR 22 and missing weight

All cases are fictional.

## Deployment
This project is designed for Streamlit Community Cloud. Do not upload API keys or confidential data to GitHub.
