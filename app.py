import streamlit as st
from pypdf import PdfReader
from groq import Groq
from ddgs import DDGS
from pydantic import BaseModel, Field
from typing import Literal
import json
import re
import os

st.set_page_config(
    page_title="TruthLayer | Automated PDF Fact-Checker",
    page_icon="🔍",
    layout="wide"
)

class ClaimResult(BaseModel):
    claim: str = Field(description="The exact factual claim extracted from the PDF.")
    verdict: Literal["Verified", "Inaccurate", "False"] = Field(
        description="Verified if accurate and current; Inaccurate if outdated or wrong number; False if fabricated or unverified."
    )
    real_fact: str = Field(description="The verified real-world fact or corrected figure based on live web search.")
    explanation: str = Field(description="Brief explanation comparing the PDF claim to live web data.")
    source_url: str = Field(description="Primary URL supporting the verification, or 'None found' if False.")

def extract_text_from_pdf(uploaded_file) -> str:
    reader = PdfReader(uploaded_file)
    pages_text = []
    for idx, page in enumerate(reader.pages):
        text = page.extract_text()
        if text:
            pages_text.append(f"--- Page {idx + 1} ---\n{text}")
    return "\n\n".join(pages_text)

def get_active_groq_model(client: Groq) -> str:
    models = client.models.list().data
    available_ids = [m.id for m in models]
    blocked = ("whisper", "guard", "tts", "orpheus", "playai", "compound", "allam", "distil")
    chat_models = [mid for mid in available_ids if not any(b in mid.lower() for b in blocked)]
    preferred_keywords = ["llama-4", "llama-3.3", "llama-3.1-70b", "qwen", "gpt-oss", "llama-3.1-8b", "gemma"]
    for kw in preferred_keywords:
        for mid in chat_models:
            if kw in mid.lower():
                return mid
    return chat_models[0] if chat_models else "llama-3.1-8b-instant"

def parse_json_safely(raw_text: str) -> dict:
    cleaned = raw_text.strip()
    cleaned = re.sub(r"^```(?:json)?\s*", "", cleaned)
    cleaned = re.sub(r"\s*```$", "", cleaned)
    start = cleaned.find("{")
    end = cleaned.rfind("}")
    if start != -1 and end != -1:
        cleaned = cleaned[start:end + 1]
    return json.loads(cleaned, strict=False)

def extract_claims(client: Groq, pdf_text: str, model_name: str) -> list[str]:
    prompt = f"""
    Extract ALL specific, verifiable factual claims from the following text—especially statistics, percentages, dates, historical milestones, financial figures, and technical metrics. Ignore pure marketing fluff or subjective opinions.
    
    Respond with ONLY valid JSON in this exact format:
    {{"claims": ["claim 1", "claim 2"]}}
    
    Document Text:
    {pdf_text[:25000]}
    """
    response = client.chat.completions.create(
        model=model_name,
        messages=[{"role": "user", "content": prompt}],
        temperature=0.1,
    )
    data = parse_json_safely(response.choices[0].message.content)
    return data.get("claims", [])

def search_live_web(query: str) -> str:
    try:
        results = DDGS().text(query, max_results=4)
        if not results:
            return "No live web search results found."
        formatted = []
        for r in results:
            formatted.append(f"- Title: {r.get('title')}\n  Snippet: {r.get('body')}\n  URL: {r.get('href')}")
        return "\n".join(formatted)
    except Exception as e:
        return f"Search unavailable: {e}"

def verify_single_claim(client: Groq, claim: str, search_context: str, model_name: str) -> ClaimResult:
    prompt = f"""
    You are a strict investigative Fact-Checking Agent. Compare the PDF Claim against the Live Web Search Evidence below (and your verified factual knowledge if search snippets are limited).
    
    PDF Claim: {json.dumps(claim)}
    
    Live Web Search Evidence:
    {search_context}
    
    Classify the claim strictly as:
    - "Verified": The number, date, or fact matches current, authoritative live web sources.
    - "Inaccurate": The claim contains an outdated statistic, wrong number, or altered date (e.g., citing old population/revenue numbers as current, or inflating a real metric). Provide the exact corrected real-world fact.
    - "False": The claim is completely fabricated, hallucinated, or contradicted/unsupported by credible evidence on the web.
    
    Respond with ONLY valid JSON (no markdown fences, no extra text) using these exact keys:
    {{
        "claim": {json.dumps(claim)},
        "verdict": "Verified",
        "real_fact": "The verified real-world fact or corrected figure",
        "explanation": "Brief 1-2 sentence explanation comparing the PDF claim to live web data",
        "source_url": "Best matching URL from the search results, or None found"
    }}
    """
    try:
        response = client.chat.completions.create(
            model=model_name,
            messages=[{"role": "user", "content": prompt}],
            temperature=0.1,
        )
        data = parse_json_safely(response.choices[0].message.content)
        verdict = data.get("verdict", "False")
        if verdict not in ("Verified", "Inaccurate", "False"):
            verdict = "Inaccurate" if "inaccurate" in verdict.lower() else ("Verified" if "verified" in verdict.lower() else "False")
        return ClaimResult(
            claim=claim,
            verdict=verdict,
            real_fact=str(data.get("real_fact", "No verified data returned.")),
            explanation=str(data.get("explanation", "Compared against live search records.")),
            source_url=str(data.get("source_url", "None found")),
        )
    except Exception as e:
        return ClaimResult(
            claim=claim,
            verdict="False",
            real_fact="Could not verify claim automatically.",
            explanation=f"Verification fallback triggered: {str(e)[:120]}",
            source_url="None found",
        )

st.title("🔍 TruthLayer: Automated PDF Fact-Check Agent")
st.markdown("Upload a PDF report to extract statistics, dates, and financial claims and verify them against **live web data**.")

with st.sidebar:
    st.header("⚙️ Configuration")
    default_key = st.secrets.get("GROQ_API_KEY", "") if hasattr(st, "secrets") else os.environ.get("GROQ_API_KEY", "")
    api_key = st.text_input("Groq API Key", value=default_key, type="password", help="Get a free key from console.groq.com")
    st.info("💡 **How it works:** Extracts hard claims (stats, dates, financials) and cross-references them against live web search results.")

uploaded_file = st.file_uploader("Upload a PDF Document", type=["pdf"])

if uploaded_file is not None:
    if not api_key:
        st.warning("⚠️ Please enter your Groq API Key in the sidebar (or configure `GROQ_API_KEY` in Streamlit Secrets).")
    else:
        with st.spinner("📄 Reading PDF..."):
            pdf_text = extract_text_from_pdf(uploaded_file)
        
        if not pdf_text.strip():
            st.error("Could not extract readable text from this PDF. Please upload a text-based PDF.")
        else:
            with st.expander("View Extracted PDF Text"):
                st.text(pdf_text[:3000] + ("..." if len(pdf_text) > 3000 else ""))
            
            if st.button("🚀 Run Live Fact-Check", type="primary"):
                client = Groq(api_key=api_key)
                try:
                    model_name = get_active_groq_model(client)
                    with st.spinner("🧠 Extracting factual claims from document..."):
                        claims = extract_claims(client, pdf_text, model_name)
                    
                    if not claims:
                        st.warning("No specific numerical, date, or statistical claims were detected in this PDF.")
                    else:
                        results: list[ClaimResult] = []
                        progress_bar = st.progress(0, text="🌐 Verifying claims against live web data...")
                        
                        for i, claim in enumerate(claims):
                            progress_bar.progress(i / len(claims), text=f"🌐 Checking claim {i+1} of {len(claims)}...")
                            search_context = search_live_web(claim)
                            result = verify_single_claim(client, claim, search_context, model_name)
                            results.append(result)
                        
                        progress_bar.empty()
                        
                        verified_count = sum(1 for r in results if r.verdict == "Verified")
                        inaccurate_count = sum(1 for r in results if r.verdict == "Inaccurate")
                        false_count = sum(1 for r in results if r.verdict == "False")
                        
                        st.subheader("📊 Verification Scorecard")
                        col1, col2, col3, col4 = st.columns(4)
                        col1.metric("Total Claims Checked", len(results))
                        col2.metric("✅ Verified", verified_count)
                        col3.metric("⚠️ Inaccurate / Outdated", inaccurate_count)
                        col4.metric("❌ False / Unverified", false_count)
                        st.divider()
                        
                        st.subheader("📋 Detailed Claim-by-Claim Report")
                        for idx, item in enumerate(results, 1):
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
