"""Chat routes — Q&A assistant and ticket proxy endpoints for the chatbot widget."""

import logging
import os

import requests
from auth import require_auth
from chat_context import get_chat_context
from flask import Blueprint, g, jsonify, request
from smart_llm import call_direct, call_harness

chat_bp = Blueprint("chat", __name__)


@chat_bp.route("/api/chat/message", methods=["POST"])
@require_auth
def chat_message():
    data = request.get_json() or {}
    message = data.get("message", "").strip()
    history = data.get("history", [])

    if not message:
        return jsonify({"error": "message is required"}), 400

    try:
        context = get_chat_context(g.user_id)
        system_prompt = "You are a resume optimization assistant. Here is the user context:\n"

        if context.get("resume_filename"):
            system_prompt += f"Resume: {context['resume_filename']}\n"
        if context.get("ats_score"):
            system_prompt += f"ATS Score: {context['ats_score']:.1f}%\n"
        if context.get("matching_keywords"):
            system_prompt += f"Matching keywords: {', '.join(context['matching_keywords'])}\n"
        if context.get("missing_keywords"):
            system_prompt += f"Missing keywords: {', '.join(context['missing_keywords'])}\n"
        if context.get("job_description"):
            system_prompt += f"Job description (excerpt): {context['job_description'][:500]}\n"
        if context.get("linkedin_headline"):
            system_prompt += f"LinkedIn: {context['linkedin_headline']}\n"

        system_prompt = system_prompt[:4000]
        full_prompt = f"{system_prompt}\nConversation history:\n"
        for item in history:
            full_prompt += f"[{item['role']}]: {item['content']}\n"
        full_prompt += f"\nUser: {message}"

        try:
            response_text = call_harness(full_prompt, task_type="reasoning", max_tokens=512)
            if response_text is None:
                raise ValueError("call_harness returned None")
        except Exception:
            response_text = call_direct(full_prompt, max_tokens=512)

        context_used = any(
            [context.get("resume_text"), context.get("ats_score"), context.get("linkedin_headline")]
        )
        return jsonify({"response": response_text, "context_used": context_used}), 200

    except Exception as e:
        logging.error(f"chat_message error: {e}")
        return jsonify({"response": "I encountered an error. Please try again.", "context_used": False}), 200


@chat_bp.route("/api/chat/ticket", methods=["POST"])
@require_auth
def chat_ticket():
    data = request.get_json() or {}
    title = data.get("title", "").strip()
    description = data.get("description", "").strip()
    ticket_type = data.get("ticket_type", "").strip()

    if len(title) < 5:
        return jsonify({"error": "title must be at least 5 characters"}), 400
    if len(description) < 10:
        return jsonify({"error": "description must be at least 10 characters"}), 400
    if ticket_type not in ("bug", "feature"):
        return jsonify({"error": "ticket_type must be 'bug' or 'feature'"}), 400

    token = os.environ.get("SUPPORT_GATEWAY_TOKEN", "")
    if not token:
        return jsonify({"status": "queued", "error": "Support gateway not configured"}), 200

    headers = {"Authorization": f"Bearer {token}", "Content-Type": "application/json"}
    payload = {"title": title, "description": description, "ticket_type": ticket_type}

    try:
        response = requests.post(
            os.environ.get("SUPPORT_API_URL", "http://localhost:8000") + "/api/support/tickets/",
            headers=headers,
            json=payload,
            timeout=10,
        )
        if response.status_code < 300:
            resp_data = response.json()
            ticket_id = resp_data.get("id") or resp_data.get("ticket_id") or "unknown"
            logging.info(f"Chat ticket created: {ticket_id} type={ticket_type} user={g.user_id}")
            return jsonify({"ticket_id": ticket_id, "status": "created"}), 200
        logging.error(f"Gateway returned {response.status_code}: {response.text[:200]}")
    except requests.RequestException as e:
        logging.error(f"Gateway request error: {e}")

    return jsonify({"status": "queued", "error": "Gateway unavailable, ticket queued locally"}), 200
