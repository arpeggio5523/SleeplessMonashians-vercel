#!/usr/bin/env python3
"""
check_gemini.py — prove the API key, model and token budget work.
Run this FIRST.

    pip install google-genai
    $env:GEMINI_API_KEY="your-key"
    python check_gemini.py
"""
import logging
import os
import sys

logging.getLogger("google_genai.models").setLevel(logging.ERROR)

key = os.environ.get("GEMINI_API_KEY") or os.environ.get("GOOGLE_API_KEY")
if not key:
    sys.exit("GEMINI_API_KEY not set.\n"
             "  PowerShell:  $env:GEMINI_API_KEY='your-key'\n"
             "  Free key at  https://aistudio.google.com/apikey")

try:
    from google import genai
    from google.genai import types
except ImportError:
    sys.exit("google-genai not installed. Run:\n"
             "  pip uninstall -y google-generativeai\n"
             "  pip install google-genai")

client = genai.Client(api_key=key)

print("available flash models:")
names = []
try:
    for m in client.models.list():
        n = (getattr(m, "name", "") or "").replace("models/", "")
        names.append(n)
        if "flash" in n and not any(x in n for x in ("image", "tts", "audio", "live")):
            print(f"  {n}")
except Exception as e:
    print(f"  (could not list: {e})")

model = os.environ.get("SDOC_GEMINI_MODEL", "gemini-3.6-flash")
if names and model not in names:
    alt = ("gemini-flash-latest" if "gemini-flash-latest" in names else
           next((n for n in names if "flash" in n and "-lite" not in n
                 and not any(x in n for x in ("image", "tts", "audio", "live",
                                              "preview"))), None))
    if alt:
        print(f"\n'{model}' unavailable — using '{alt}' for this check.")
        print(f"Set it permanently:  $env:SDOC_GEMINI_MODEL='{alt}'")
        model = alt

# Gemini 3 spends output tokens on internal reasoning before answering, and
# max_output_tokens caps thinking + answer combined. Too small a cap returns
# a truncated fragment. 'minimal' thinking keeps classification fast.
if "2.5" in model or "2.0" in model:
    thinking = types.ThinkingConfig(thinking_budget=0)
else:
    thinking = types.ThinkingConfig(thinking_level="minimal")

print(f"\ncalling {model} ...")
try:
    resp = client.models.generate_content(
        model=model,
        contents='Reply with JSON only: {"ok": true, "note": "<5 words>"}',
        config=types.GenerateContentConfig(
            temperature=0.0,
            max_output_tokens=1024,
            response_mime_type="application/json",
            thinking_config=thinking,
        ),
    )
except Exception as e:
    sys.exit(f"\nCall failed:\n  {e}\n\n"
             "If the model is unavailable, pick one from the list above:\n"
             "  $env:SDOC_GEMINI_MODEL='<name>'")

text = (getattr(resp, "text", "") or "").strip()
print("response:", text or "(empty)")

u = getattr(resp, "usage_metadata", None)
if u:
    print(f"tokens:   thinking={getattr(u, 'thoughts_token_count', 0)} "
          f"answer={getattr(u, 'candidates_token_count', 0)}")

import json
try:
    json.loads(text)
except Exception:
    sys.exit("\nResponse is not valid JSON — likely truncated.\n"
             "Raise MAX_OUTPUT_TOKENS in sdoc/llm/gemini.py and re-run.")

print("\nValid JSON. Now run:")
print("  $env:SDOC_LLM_MODE='live'")
print("  python run_pipeline.py --llm")
if model != "gemini-3.6-flash":
    print(f"  (remember  $env:SDOC_GEMINI_MODEL='{model}')")
