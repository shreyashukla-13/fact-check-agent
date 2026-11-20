# 🔍 TruthLayer — Automated PDF Fact-Check Agent

An AI-powered "Truth Layer" web application that extracts factual claims (statistics, dates, financial and technical figures) from uploaded PDFs and verifies them against live Google Search data.

## Features
- **Automated Claim Extraction:** Isolates hard metrics, dates, and financial claims while filtering out subjective marketing copy.
- **Live Web Verification:** Uses Gemini 2.5 Flash with real-time Google Search grounding to cross-check every claim.
- **Actionable Truth Report:** Classifies each claim as **Verified**, **Inaccurate** (providing the real updated stat), or **False**, complete with source links.

## Local Setup
1. Clone this repository:
   
```bash
   git clone [https://github.com/YOUR_USERNAME/fact-check-agent.git](https://github.com/YOUR_USERNAME/fact-check-agent.git)
   cd fact-check-agent
