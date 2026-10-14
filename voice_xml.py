"""Helpers for producing valid Plivo XML responses."""
from __future__ import annotations

from xml.etree.ElementTree import Element, SubElement, tostring


def _serialize(response: Element) -> str:
    body = tostring(response, encoding="unicode", short_empty_elements=True)
    return '<?xml version="1.0" encoding="UTF-8"?>' + body


def _speak(parent: Element, message: str, language: str | None = None) -> None:
    attrs = {"language": language} if language else {}
    node = SubElement(parent, "Speak", attrs)
    node.text = message


def _redirect(parent: Element, url: str, method: str = "POST") -> None:
    node = SubElement(parent, "Redirect", {"method": method})
    node.text = url


def build_otp_prompt_xml(action_url: str, timeout_url: str, announcement: str | None = None) -> str:
    """Collect a four-digit OTP via DTMF without logging digits."""
    response = Element("Response")
    get_input = SubElement(response, "GetInput", {
        "action": action_url, "method": "POST", "inputType": "dtmf",
        "numDigits": "4", "finishOnKey": "none", "digitEndTimeout": "3",
        "executionTimeout": "15", "startInputTimeout": "10", "log": "false",
        "retries": "1", "redirect": "true",
    })
    prompt = []
    if announcement:
        prompt.append(announcement)
    prompt.append("Welcome to InspireWorks. Please enter your four-digit verification code.")
    _speak(get_input, " ".join(prompt), "en-US")
    _redirect(response, timeout_url)
    return _serialize(response)


def build_language_prompt_xml(action_url: str, timeout_url: str, announcement: str | None = None) -> str:
    """Collect language preference after OTP authentication."""
    response = Element("Response")
    get_input = SubElement(response, "GetInput", {
        "action": action_url, "method": "POST", "inputType": "dtmf",
        "numDigits": "1", "finishOnKey": "none", "digitEndTimeout": "3",
        "executionTimeout": "15", "startInputTimeout": "10", "log": "false",
        "retries": "1", "redirect": "true",
    })
    if announcement:
        _speak(get_input, announcement, "en-US")
    _speak(get_input, "For English, press 1.", "en-US")
    _speak(get_input, "Para español, oprima el 2.", "es-ES")
    _redirect(response, timeout_url)
    return _serialize(response)


def build_action_menu_xml(action_url: str, timeout_url: str, language: str, announcement: str | None = None) -> str:
    """Level 2 action menu in the selected language."""
    response = Element("Response")
    get_input = SubElement(response, "GetInput", {
        "action": action_url, "method": "POST", "inputType": "dtmf",
        "numDigits": "1", "finishOnKey": "none", "digitEndTimeout": "3",
        "executionTimeout": "15", "startInputTimeout": "10", "log": "false",
        "retries": "1", "redirect": "true",
    })
    if announcement:
        _speak(get_input, announcement, "es-ES" if language == "es" else "en-US")
    if language == "es":
        _speak(get_input, "Pulse 1 para escuchar un mensaje. Pulse 2 para hablar con un representante.", "es-ES")
    else:
        _speak(get_input, "Press 1 to hear a short audio message. Press 2 to connect to a live associate.", "en-US")
    _redirect(response, timeout_url)
    return _serialize(response)


def build_playback_xml(audio_url: str, menu_url: str, language: str) -> str:
    """Play one public audio clip, speak a short message, then return to Level 2."""
    response = Element("Response")
    SubElement(response, "Play").text = audio_url
    if language == "es":
        _speak(response, "Gracias por llamar a InspireWorks. Este es nuestro mensaje de demostración.", "es-ES")
    else:
        _speak(response, "Thank you for calling InspireWorks. This is our demonstration audio message.", "en-US")
    _redirect(response, menu_url)
    return _serialize(response)


def build_dial_xml(associate_number: str, completion_url: str, caller_id: str, language: str) -> str:
    """Dial the live associate and post DialStatus to completion_url."""
    response = Element("Response")
    if language == "es":
        _speak(response, "Por favor espere mientras le conectamos con un representante.", "es-ES")
    else:
        _speak(response, "Please hold while we connect you to a live associate.", "en-US")
    attrs = {"action": completion_url, "method": "POST", "timeout": "20"}
    if caller_id:
        attrs["callerId"] = caller_id
    dial = SubElement(response, "Dial", attrs)
    SubElement(dial, "Number").text = associate_number
    return _serialize(response)


def build_dial_completion_xml(connected: bool, language: str) -> str:
    response = Element("Response")
    if language == "es":
        message = "Gracias por llamar a InspireWorks. Adiós." if connected else "Lo sentimos, no hay ningún representante disponible en este momento. Adiós."
        _speak(response, message, "es-ES")
    else:
        message = "Thank you for calling InspireWorks. Goodbye." if connected else "Sorry, no associate is available right now. Please try again later. Goodbye."
        _speak(response, message, "en-US")
    SubElement(response, "Hangup")
    return _serialize(response)


def build_not_ready_xml(message: str) -> str:
    response = Element("Response")
    _speak(response, message, "en-US")
    SubElement(response, "Hangup")
    return _serialize(response)
