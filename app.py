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
        "source_url
