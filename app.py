"""Flask app for the InspireWorks outbound Plivo IVR demo."""

from __future__ import annotations

import os
import re
import time
from typing import Any
from urllib.parse import urlsplit

from dotenv import load_dotenv
from flask import Flask, Response, jsonify, render_template, request

from voice_xml import (
    build_action_menu_xml,
    build_dial_completion_xml,
    build_dial_xml,
    build_language_prompt_xml,
    build_not_ready_xml,
    build_otp_prompt_xml,
    build_playback_xml,
)

load_dotenv()

REQUIRED_CONFIG = (
    "PLIVO_AUTH_ID",
    "PLIVO_AUTH_TOKEN",
    "PLIVO_FROM_NUMBER",
    "PLIVO_PUBLIC_BASE_URL",
    "ALLOWED_DESTINATION_NUMBER",
    "CALL_TRIGGER_PIN",
    "OTP_CODE",
    "ASSOCIATE_NUMBER",
)
E164_RE = re.compile(r"^\+[1-9]\d{7,14}$")
OTP_RE = re.compile(r"^[0-9]{4}$")
SESSION_TTL_SECONDS = 60 * 60
MAX_CONSECUTIVE_TIMEOUTS = 3
# Public sample audio documented by Plivo. Configure your own HTTPS MP3 URLs in .env if preferred.
DEFAULT_AUDIO_URL = "https://s3.amazonaws.com/plivocloud/Trumpet.mp3"


def _is_e164(number: str) -> bool:
    return bool(E164_RE.fullmatch(number))


def _is_public_https_url(value: str) -> bool:
    try:
        parsed = urlsplit(value)
        host = (parsed.hostname or "").lower().rstrip(".")
    except ValueError:
        return False
    if parsed.scheme != "https" or not host or not parsed.netloc:
        return False
    if host in {"localhost", "127.0.0.1", "0.0.0.0", "::1"}:
        return False
    if host.endswith((".local", ".example", ".test")):
        return False
    return True


def _call_uuid_from_request() -> str:
    """Read Plivo's call UUID from query/form parameters without logging input."""
    return (request.values.get("CallUUID") or request.values.get("CallUuid") or "").strip()


def _configuration_status(config: dict[str, Any]) -> tuple[bool, list[str]]:
    missing = [name for name in REQUIRED_CONFIG if not config.get(name)]
    return not missing, missing


def _valid_otp(value: str) -> bool:
    return bool(OTP_RE.fullmatch(value or ""))


def _xml_response(xml: str, status: int = 200) -> Response:
    return Response(xml, status=status, mimetype="application/xml")


def _prune_expired_sessions(sessions: dict[str, dict[str, Any]]) -> None:
    now = time.time()
    expired = [
        call_uuid
        for call_uuid, session in sessions.items()
        if now - float(session.get("last_activity", session.get("created_at", now)))
        > SESSION_TTL_SECONDS
    ]
    for call_uuid in expired:
        sessions.pop(call_uuid, None)


def create_app(test_config: dict[str, Any] | None = None) -> Flask:
    """App factory with isolated in-memory sessions and mockable Plivo client."""
    app = Flask(__name__)
    app.config.from_mapping(
        PLIVO_AUTH_ID=os.getenv("PLIVO_AUTH_ID", "").strip(),
        PLIVO_AUTH_TOKEN=os.getenv("PLIVO_AUTH_TOKEN", "").strip(),
        PLIVO_FROM_NUMBER=os.getenv("PLIVO_FROM_NUMBER", "").strip(),
        PLIVO_PUBLIC_BASE_URL=os.getenv("PLIVO_PUBLIC_BASE_URL", "").strip().rstrip("/"),
        ALLOWED_DESTINATION_NUMBER=os.getenv("ALLOWED_DESTINATION_NUMBER", "").strip(),
        CALL_TRIGGER_PIN=os.getenv("CALL_TRIGGER_PIN", "").strip(),
        OTP_CODE=os.getenv("OTP_CODE", "").strip(),
        ASSOCIATE_NUMBER=os.getenv("ASSOCIATE_NUMBER", "").strip(),
        AUDIO_EN_URL=os.getenv("AUDIO_EN_URL", "").strip(),
        AUDIO_ES_URL=os.getenv("AUDIO_ES_URL", "").strip(),
        TESTING=False,
    )
    if test_config:
        app.config.update(test_config)
        app.config["PLIVO_PUBLIC_BASE_URL"] = str(
            app.config.get("PLIVO_PUBLIC_BASE_URL", "")
        ).strip().rstrip("/")
        for key in ("ALLOWED_DESTINATION_NUMBER", "CALL_TRIGGER_PIN", "OTP_CODE"):
            app.config[key] = str(app.config.get(key, "")).strip()

    # This assignment demo runs as one Flask process. In-memory sessions are
    # intentionally simple and are not shared across workers or restarts.
    sessions: dict[str, dict[str, Any]] = {}
    app.extensions["ivr_sessions"] = sessions

    def base_url() -> str:
        return str(app.config.get("PLIVO_PUBLIC_BASE_URL", "")).rstrip("/")

    def active_session(call_uuid: str) -> dict[str, Any] | None:
        if not call_uuid:
            return None
        _prune_expired_sessions(sessions)
        session = sessions.get(call_uuid)
        if session is None:
            return None
        session["last_activity"] = time.time()
        return session

    def fail_closed(message: str = "We could not verify this call. Goodbye.") -> Response:
        return _xml_response(build_not_ready_xml(message))

    def otp_prompt(announcement: str | None = None) -> Response:
        return _xml_response(
            build_otp_prompt_xml(
                f"{base_url()}/voice/otp",
                f"{base_url()}/voice/otp-timeout",
                announcement,
            )
        )

    def language_prompt(announcement: str | None = None) -> Response:
        return _xml_response(
            build_language_prompt_xml(
                f"{base_url()}/voice/language",
                f"{base_url()}/voice/language-timeout",
                announcement,
            )
        )

    def action_menu_prompt(session: dict[str, Any], announcement: str | None = None) -> Response:
        language = str(session.get("language") or "en")
        return _xml_response(
            build_action_menu_xml(
                f"{base_url()}/voice/action",
                f"{base_url()}/voice/action-timeout",
                language,
                announcement,
            )
        )

    @app.get("/")
    def home() -> str:
        configured, missing = _configuration_status(app.config)
        return render_template(
            "index.html",
            configured=configured,
            missing=missing,
            allowed_destination=app.config.get("ALLOWED_DESTINATION_NUMBER", ""),
        )

    @app.get("/health")
    def health():
        """Expose configuration status only, never secret values."""
        configured, missing = _configuration_status(app.config)
        return jsonify(
            status="ok",
            configured=configured,
            missing_configuration=missing,
        ), 200

    @app.post("/api/calls")
    def create_outbound_call():
        configured, missing = _configuration_status(app.config)
        if not configured:
            return jsonify(
                ok=False,
                error="Call initiation is not configured yet.",
                missing_configuration=missing,
            ), 503

        if not _valid_otp(app.config["OTP_CODE"]):
            return jsonify(ok=False, error="OTP_CODE must contain exactly four digits."), 503

        payload = request.get_json(silent=True)
        if not isinstance(payload, dict):
            return jsonify(ok=False, error="Send a JSON request body."), 400

        supplied_pin = str(payload.get("trigger_pin", ""))
        if not supplied_pin or supplied_pin != app.config["CALL_TRIGGER_PIN"]:
            return jsonify(ok=False, error="The call-trigger PIN is incorrect."), 401

        destination = str(payload.get("to", "")).strip()
        if not _is_e164(destination):
            return jsonify(
                ok=False,
                error="Enter a valid international phone number in E.164 format, e.g. +919876543210.",
            ), 400
        if destination != app.config["ALLOWED_DESTINATION_NUMBER"]:
            return jsonify(
                ok=False,
                error="For safety, this demo can call only the configured test number.",
            ), 403

        public_url = base_url()
        if not _is_public_https_url(public_url):
            return jsonify(
                ok=False,
                error="PLIVO_PUBLIC_BASE_URL must be a public HTTPS URL, not localhost or a placeholder.",
            ), 503
        if not _is_e164(app.config["PLIVO_FROM_NUMBER"]):
            return jsonify(ok=False, error="PLIVO_FROM_NUMBER must be configured in E.164 format."), 503

        client_factory = app.config.get("PLIVO_CLIENT_FACTORY")
        if client_factory is None:
            try:
                import plivo as plivo_sdk
            except ImportError:
                return jsonify(
                    ok=False,
                    error="The Plivo SDK is not installed. Run: python -m pip install -r requirements.txt",
                ), 503
            client_factory = plivo_sdk.RestClient

        try:
            client = client_factory(
                app.config["PLIVO_AUTH_ID"], app.config["PLIVO_AUTH_TOKEN"]
            )
            result = client.calls.create(
                from_=app.config["PLIVO_FROM_NUMBER"],
                to_=destination,
                answer_url=f"{public_url}/voice/answer",
                answer_method="GET",
            )
        except Exception as exc:
            app.logger.warning("Plivo call request failed (%s)", type(exc).__name__)
            return jsonify(
                ok=False,
                error=(
                    "Plivo could not accept the call request. Check the account, credentials, "
                    "caller ID, balance, and destination permissions."
                ),
            ), 502

        request_uuid = _get_response_value(result, "request_uuid")
        return jsonify(
            ok=True,
            message="Plivo accepted the call request. This does not guarantee the recipient answered.",
            request_uuid=request_uuid,
        ), 202

    @app.route("/voice/answer", methods=["GET", "POST"])
    def voice_answer():
        """Create an isolated call session and speak the OTP prompt."""
        public_url = base_url()
        if not _is_public_https_url(public_url) or not _valid_otp(app.config.get("OTP_CODE", "")):
            return fail_closed("This IVR is not configured correctly. Goodbye.")

        call_uuid = _call_uuid_from_request()
        if not call_uuid:
            return fail_closed("We could not identify this call. Goodbye.")

        _prune_expired_sessions(sessions)
        now = time.time()
        sessions[call_uuid] = {
            "authenticated": False,
            "language": None,
            "otp_timeouts": 0,
            "language_timeouts": 0,
            "action_timeouts": 0,
            "created_at": now,
            "last_activity": now,
        }
        return otp_prompt()

    @app.post("/voice/otp")
    def voice_otp():
        """Validate four DTMF digits; never log or persist the entered code."""
        call_uuid = _call_uuid_from_request()
        session = active_session(call_uuid)
        if session is None:
            return fail_closed()
        if session.get("authenticated"):
            # A repeated OTP callback on an already authenticated call should not
            # reset state or force the caller to authenticate again.
            return language_prompt("You are already verified.")

        digits = request.values.get("Digits", "")
        if not digits:
            return handle_otp_timeout_session(session)

        # Any attempted code resets the consecutive-silence counter. Do not log it.
        session["otp_timeouts"] = 0
        if not (digits.isascii() and digits.isdigit() and len(digits) == 4):
            return otp_prompt("Please enter exactly four digits.")

        configured_otp = app.config.get("OTP_CODE", "")
        if not _valid_otp(configured_otp):
            return fail_closed("Verification is unavailable. Goodbye.")

        if digits != configured_otp:
            return otp_prompt("That code is incorrect. Please try again.")

        session["authenticated"] = True
        session["language"] = None
        session["language_timeouts"] = 0
        return language_prompt("Thank you. Verification successful.")

    def handle_otp_timeout_session(session: dict[str, Any]) -> Response:
        session["otp_timeouts"] = int(session.get("otp_timeouts", 0)) + 1
        if session["otp_timeouts"] >= MAX_CONSECUTIVE_TIMEOUTS:
            return fail_closed("We did not receive your code. Goodbye.")
        return otp_prompt("I did not receive your code. Please try again.")

    @app.post("/voice/otp-timeout")
    def voice_otp_timeout():
        session = active_session(_call_uuid_from_request())
        if session is None or session.get("authenticated"):
            return fail_closed()
        return handle_otp_timeout_session(session)

    @app.post("/voice/language")
    def voice_language():
        """Allow language selection only after a correct OTP."""
        session = active_session(_call_uuid_from_request())
        if session is None or not session.get("authenticated"):
            return fail_closed("Please authenticate before choosing a language. Goodbye.")

        digits = request.values.get("Digits", "")
        if digits == "1":
            session["language"] = "en"
            session["language_timeouts"] = 0
            session["action_timeouts"] = 0
            return action_menu_prompt(session, "You selected English.")
        if digits == "2":
            session["language"] = "es"
            session["language_timeouts"] = 0
            session["action_timeouts"] = 0
            return action_menu_prompt(session, "Ha seleccionado español.")
        if digits:
            session["language_timeouts"] = 0
            return language_prompt("Invalid option. Please press 1 for English or 2 for Spanish.")
        return handle_language_timeout_session(session)

    def handle_language_timeout_session(session: dict[str, Any]) -> Response:
        session["language_timeouts"] = int(session.get("language_timeouts", 0)) + 1
        if session["language_timeouts"] >= MAX_CONSECUTIVE_TIMEOUTS:
            return fail_closed("We did not receive a language selection. Goodbye.")
        return language_prompt("I did not receive your selection. Please try again.")

    @app.post("/voice/language-timeout")
    def voice_language_timeout():
        session = active_session(_call_uuid_from_request())
        if session is None or not session.get("authenticated"):
            return fail_closed()
        return handle_language_timeout_session(session)

    @app.route("/voice/menu", methods=["GET", "POST"])
    def voice_menu():
        """Return Level 2, used initially and after the audio message finishes."""
        session = active_session(_call_uuid_from_request())
        if session is None or not session.get("authenticated") or session.get("language") not in {"en", "es"}:
            return fail_closed("Please authenticate and select a language first. Goodbye.")
        return action_menu_prompt(session)

    @app.post("/voice/action")
    def voice_action():
        """Level 2: play a language-specific clip or dial the live associate."""
        session = active_session(_call_uuid_from_request())
        if session is None or not session.get("authenticated") or session.get("language") not in {"en", "es"}:
            return fail_closed("Please authenticate and select a language first. Goodbye.")
        digits = request.values.get("Digits", "")
        language = session["language"]
        if digits == "1":
            audio_setting = "AUDIO_ES_URL" if language == "es" else "AUDIO_EN_URL"
            audio_url = str(app.config.get(audio_setting, "")).strip() or DEFAULT_AUDIO_URL
            if not _is_public_https_url(audio_url):
                audio_url = DEFAULT_AUDIO_URL
            session["action_timeouts"] = 0
            return _xml_response(build_playback_xml(audio_url, f"{base_url()}/voice/menu", language))
        if digits == "2":
            associate = str(app.config.get("ASSOCIATE_NUMBER", "")).strip()
            if not _is_e164(associate):
                return action_menu_prompt(session, "The associate line is not configured. Please choose another option.")
            return _xml_response(
                build_dial_xml(associate, f"{base_url()}/voice/dial-complete",
                               str(app.config.get("PLIVO_FROM_NUMBER", "")), language)
            )
        if digits:
            session["action_timeouts"] = 0
            msg = ("Opción no válida. Pulse 1 para escuchar un mensaje o 2 para hablar con un representante."
                   if language == "es" else
                   "Invalid option. Press 1 to hear a message or 2 to connect to an associate.")
            return action_menu_prompt(session, msg)
        return handle_action_timeout_session(session)

    def handle_action_timeout_session(session: dict[str, Any]) -> Response:
        session["action_timeouts"] = int(session.get("action_timeouts", 0)) + 1
        if session["action_timeouts"] >= MAX_CONSECUTIVE_TIMEOUTS:
            return fail_closed("We did not receive a menu selection. Goodbye.")
        language = str(session.get("language") or "en")
        msg = ("No recibimos su selección. Inténtelo de nuevo." if language == "es"
               else "I did not receive your selection. Please try again.")
        return action_menu_prompt(session, msg)

    @app.post("/voice/action-timeout")
    def voice_action_timeout():
        session = active_session(_call_uuid_from_request())
        if session is None or not session.get("authenticated") or session.get("language") not in {"en", "es"}:
            return fail_closed()
        return handle_action_timeout_session(session)

    @app.post("/voice/dial-complete")
    def voice_dial_complete():
        session = active_session(_call_uuid_from_request())
        if session is None or not session.get("authenticated") or session.get("language") not in {"en", "es"}:
            return fail_closed()
        status = (request.values.get("DialStatus") or "").strip().lower()
        connected = status == "completed"
        return _xml_response(build_dial_completion_xml(connected, session["language"]))

    return app


def _get_response_value(result: Any, key: str) -> str | None:
    if isinstance(result, dict):
        value = result.get(key)
    else:
        value = getattr(result, key, None)
    return str(value) if value else None


app = create_app()


if __name__ == "__main__":
    app.run(host="127.0.0.1", port=int(os.getenv("PORT", "5000")), debug=False)
