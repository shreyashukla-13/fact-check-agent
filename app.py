import streamlit as st
from pypdf import PdfReader
from google import genai
from google.genai import types
from pydantic import BaseModel, Field
from typing import Literal
import json
import os

# --- Page Config ---
st.set_page_config(
    page_title="TruthLayer | Automated PDF Fact-Checker",
    page_icon="🔍",
    layout="wide"
)

# --- Structured Output Schema ---
class ClaimResult(BaseModel):
    claim: str = Field(description="The exact factual claim, stat, date, or financial figure extracted from the PDF.")
    verdict: Literal["Verified", "Inaccurate", "False"] = Field(
        description="Verified if accurate and current; Inaccurate if outdated or wrong number; False if fabricated or unverified."
    )
    real_fact: str = Field(description="The verified real-world fact or corrected figure based on live web search.")
    explanation: str = Field(description="Brief explanation comparing the PDF claim to live web data.")
    source_url: str = Field(description="Primary URL supporting the verification, or 'None found' if False.")

class FactCheckReport(BaseModel):
    summary: str = Field(description="A 2-sentence overall reliability summary of the document.")
    results: list[ClaimResult]

# --- Helper Functions ---
def extract_text_from_pdf(uploaded_file) -> str:
    reader = PdfReader(uploaded_file)
    pages_text = []
    for idx, page in enumerate(reader.pages):
        text = page.extract_text()
        if text:
            pages_text.append(f"--- Page {idx + 1} ---\n{text}")
    return "\n\n".join(pages_text)

def analyze_and_verify_pdf(pdf_text: str, api_key: str) -> FactCheckReport:
    client = genai.Client(api_key=api_key)
    
    prompt = f"""
    You are a strict, investigative Fact-Checking Agent acting as a 'Truth Layer' for marketing and business reports.
    
    Task:
    1. Read the provided PDF text carefully.
    2. Extract ALL specific, verifiable factual claims—especially statistics, percentages, dates, historical milestones, financial figures, and technical metrics. Ignore pure marketing fluff or subjective opinions.
    3. Use Google Search to verify EACH extracted claim against live, up-to-date web data.
    4. Classify each claim strictly as:
       - "Verified": The number, date, or fact matches current, authoritative live web sources.
       - "Inaccurate": The claim contains an outdated statistic, wrong number, or altered date (e.g., citing 2020 numbers as current, or inflating a real metric). Provide the exact corrected real-world fact.
       - "False": The claim is completely fabricated, hallucinated, or has zero credible supporting evidence on the web.
    
    Document Text:
    {pdf_text[:30000]}
    """

    response = client.models.generate_content(
        model="gemini-3.8-flash",
        contents=prompt,
        config=types.GenerateContentConfig(
            tools=[{"google_search": {}}],
            response_mime_type="application/json",
            response_schema=FactCheckReport,
            temperature=0.1,
        ),
    )
    
    data = json.loads(response.text)
    return FactCheckReport(**data)

# --- UI Layout ---
st.title("🔍 TruthLayer: Automated PDF Fact-Check Agent")
st.markdown("Upload a PDF report to extract statistics, dates, and financial claims and verify them against **live web data**.")

# Sidebar for API Key (falls back to Streamlit Secrets if deployed)
with st.sidebar:
    st.header("⚙️ Configuration")
    default_key = st.secrets.get("GEMINI_API_KEY", "") if hasattr(st, "secrets") else os.environ.get("GEMINI_API_KEY", "")
    api_key = st.text_input("Gemini API Key", value=default_key, type="password", help="Get a free key from Google AI Studio")
    st.info("💡 **How it works:** Extracts hard claims (stats, dates, financials) and cross-references them using live Google Search grounding.")

uploaded_file = st.file_uploader("Upload a PDF Document", type=["pdf"])

if uploaded_file is not None:
    if not api_key:
        st.warning("⚠️ Please enter your Gemini API Key in the sidebar (or configure `GEMINI_API_KEY` in Streamlit Secrets).")
    else:
        with st.spinner("📄 Reading PDF and extracting factual claims..."):
            pdf_text = extract_text_from_pdf(uploaded_file)
        
        if not pdf_text.strip():
            st.error("Could not extract readable text from this PDF. Please upload a text-based PDF.")
        else:
            with st.expander("View Extracted PDF Text"):
                st.text(pdf_text[:3000] + ("..." if len(pdf_text) > 3000 else ""))
            
            if st.button("🚀 Run Live Fact-Check", type="primary"):
                with st.spinner("🌐 Cross-referencing claims against live web data..."):
                    try:
                        report = analyze_and_verify_pdf(pdf_text, api_key)
                        
                        # Metrics Row
                        verified_count = sum(1 for r in report.results if r.verdict == "Verified")
                        inaccurate_count = sum(1 for r in report.results if r.verdict == "Inaccurate")
                        false_count = sum(1 for r in report.results if r.verdict == "False")
                        
                        st.subheader("📊 Verification Scorecard")
                        col1, col2, col3, col4 = st.columns(4)
                        col1.metric("Total Claims Checked", len(report.results))
                        col2.metric("✅ Verified", verified_count)
                        col3.metric("⚠️ Inaccurate / Outdated", inaccurate_count)
                        col4.metric("❌ False / Unverified", false_count)
                        
                        st.info(f"**Executive Summary:** {report.summary}")
                        st.divider()
                        
                        # Detailed Claim Cards
                        st.subheader("📋 Detailed Claim-by-Claim Report")
                        for idx, item in enumerate(report.results, 1):
                            if item.verdict == "Verified":
                                badge = "✅ VERIFIED"
                                box_fn = st.success
                            elif item.verdict == "Inaccurate":
                                badge = "⚠️ INACCURATE / OUTDATED"
                                box_fn = st.warning
                            else:
                                badge = "❌ FALSE / NO EVIDENCE"
                                box_fn = st.error
                            
                            with st.container(border=True):
                                st.markdown(f"### Claim #{idx}: {badge}")
                                st.markdown(f"**PDF Statement:** *\"{item.claim}\"*")
                                box_fn(f"**Real-World Fact:** {item.real_fact}")
                                st.markdown(f"**Analysis:** {item.explanation}")
                                if item.source_url and item.source_url.startswith("http"):
                                    st.markdown(f"🔗 **Source:** [{item.source_url}]({item.source_url})")
                                    
                    except Exception as e:
                        st.error(f"An error occurred during verification: {e}")
