# TruthLayer 🛡️
**Automated Document & Claim Verification Engine**

[![Python](https://img.shields.io/badge/Python-3.9+-blue.svg)](https://www.python.org/)
[![Streamlit](https://img.shields.io/badge/Streamlit-App-FF4B4B.svg)](https://streamlit.io/)
[![Status](https://img.shields.io/badge/Status-MVP%20Prototype-success.svg)]()

---

## 📌 Problem Statement
Enterprise teams across compliance, finance, and operations increasingly rely on AI-generated summaries and complex PDF reports—yet manual fact-checking remains slow, error-prone, and expensive. Without automated verification against trusted ground-truth documents, subtle factual discrepancies or hallucinations create high operational risk.

**TruthLayer** bridges this trust gap by extracting structured claims from uploaded PDF reports, cross-validating them against verified ground-truth sources, flagging discrepancies, and generating an automated accuracy scorecard.

---

## ✨ Key Features
* **Automated Claim Extraction:** Parses unstructured PDF reports into discrete, verifiable factual statements.
* **Ground-Truth Cross-Validation:** Compares extracted claims against trusted reference documents to detect matches, contradictions, and unverified statements.
* **Discrepancy Flagging:** Highlights conflicting claims so reviewers can immediately focus on high-risk anomalies rather than reading entire documents.
* **Automated Accuracy Scorecard:** Generates a structured verification summary quantifying overall document reliability and claim-level accuracy.
* **Interactive UI:** Lightweight, fast-loading web interface built with **Streamlit** for rapid prototyping and stakeholder demos.

---

## 🏗️ How It Works (Workflow)
```text
[Target PDF Report] ──┐
                      ├──► [Claim Extraction & Parsing] ──► [Cross-Validation Engine] ──► [Discrepancy Flags + Accuracy Scorecard]
[Ground-Truth Source] ┘
