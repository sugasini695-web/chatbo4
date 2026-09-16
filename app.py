import os
from typing import Any

from dotenv import load_dotenv
from flask import Flask, jsonify, render_template, request
from google import genai
from google.genai import types

from chatbot_config import CHATBOT_SYSTEM_PROMPT, GEMINI_MODEL


load_dotenv()

app = Flask(__name__)

MAX_MESSAGE_LENGTH = 4000
MAX_HISTORY_MESSAGES = 12
ACTIVE_GEMINI_MODEL = os.getenv("GEMINI_MODEL", GEMINI_MODEL)


def get_gemini_client() -> genai.Client:
    api_key = os.getenv("GEMINI_API_KEY", "").strip()
    if not api_key:
        raise RuntimeError("GEMINI_API_KEY is not configured.")
    return genai.Client(api_key=api_key)


def build_conversation(history: list[dict[str, Any]], message: str) -> str:
    transcript: list[str] = []

    for item in history[-MAX_HISTORY_MESSAGES:]:
        role = item.get("role")
        content = item.get("content")
        if role not in {"user", "assistant"} or not isinstance(content, str):
            continue
        cleaned_content = content.strip()
        if cleaned_content:
            speaker = "Student" if role == "user" else "Nova Talk"
            transcript.append(f"{speaker}: {cleaned_content}")

    transcript.append(f"Student: {message}")
    transcript.append("Nova Talk:")
    return "\n\n".join(transcript)


@app.get("/")
def index():
    return render_template("index.html", chatbot_name="Nova Talk")


@app.get("/healthz")
def healthz():
    return jsonify({"status": "ok", "model": GEMINI_MODEL})


@app.post("/api/chat")
def chat():
    payload = request.get_json(silent=True) or {}
    message = payload.get("message")
    history = payload.get("history", [])

    if not isinstance(message, str):
        return jsonify({"error": "Please enter a study question."}), 400

    message = message.strip()
    if not message:
        return jsonify({"error": "Please enter a study question."}), 400
    if len(message) > MAX_MESSAGE_LENGTH:
        return jsonify({"error": f"Please keep your question under {MAX_MESSAGE_LENGTH} characters."}), 400
    if not isinstance(history, list):
        history = []

    try:
        client = get_gemini_client()
        response = client.models.generate_content(
            model=ACTIVE_GEMINI_MODEL,
            contents=build_conversation(history, message),
            config=types.GenerateContentConfig(
                system_instruction=CHATBOT_SYSTEM_PROMPT,
                temperature=0.45,
                max_output_tokens=900,
            ),
        )
        answer = (response.text or "").strip()
        if not answer:
            raise RuntimeError("Gemini returned an empty response.")
        return jsonify({"answer": answer, "model": ACTIVE_GEMINI_MODEL})
    except RuntimeError as error:
        return jsonify({"error": str(error)}), 503
    except Exception:
        app.logger.exception("Gemini request failed")
        return jsonify({"error": "Nova Talk is temporarily unavailable. Please try again."}), 502


if __name__ == "__main__":
    port = int(os.getenv("PORT", "5000"))
    app.run(host="0.0.0.0", port=port)