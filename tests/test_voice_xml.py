from xml.etree import ElementTree as ET

from voice_xml import (
    build_action_menu_xml,
    build_dial_completion_xml,
    build_dial_xml,
    build_language_prompt_xml,
    build_not_ready_xml,
    build_otp_prompt_xml,
    build_playback_xml,
)


def test_otp_prompt_collects_four_dtmf_digits_without_logging():
    root = ET.fromstring(build_otp_prompt_xml("https://x.test/otp", "https://x.test/timeout"))
    collector = root.find("GetInput")
    assert collector is not None
    assert collector.attrib["action"] == "https://x.test/otp"
    assert collector.attrib["inputType"] == "dtmf"
    assert collector.attrib["numDigits"] == "4"
    assert collector.attrib["log"] == "false"
    assert root.findtext("Redirect") == "https://x.test/timeout"


def test_language_menu_offers_both_languages():
    root = ET.fromstring(build_language_prompt_xml("https://x.test/lang", "https://x.test/timeout"))
    collector = root.find("GetInput")
    assert collector is not None and collector.attrib["numDigits"] == "1"
    assert "For English" in " ".join(x.text or "" for x in collector.findall("Speak"))
    assert "español" in " ".join(x.text or "" for x in collector.findall("Speak"))


def test_level_two_menu_is_localized_and_one_digit():
    for language, phrase in (("en", "Press 1 to hear"), ("es", "Pulse 1 para escuchar")):
        root = ET.fromstring(build_action_menu_xml("https://x.test/action", "https://x.test/timeout", language))
        collector = root.find("GetInput")
        assert collector is not None and collector.attrib["numDigits"] == "1"
        assert phrase in (collector.findtext("Speak") or "")
        assert collector.attrib["log"] == "false"


def test_audio_branch_plays_audio_then_speaks_and_returns_to_menu():
    root = ET.fromstring(build_playback_xml("https://example.com/demo.mp3", "https://x.test/menu", "en"))
    assert root.findtext("Play") == "https://example.com/demo.mp3"
    assert "demonstration audio message" in (root.findtext("Speak") or "")
    assert root.findtext("Redirect") == "https://x.test/menu"


def test_dial_xml_has_number_timeout_and_completion_action():
    root = ET.fromstring(build_dial_xml("+912264236412", "https://x.test/done", "+918035454161", "en"))
    dial = root.find("Dial")
    assert dial is not None
    assert dial.attrib["action"] == "https://x.test/done"
    assert dial.attrib["timeout"] == "20"
    assert dial.findtext("Number") == "+912264236412"


def test_dial_completion_handles_unavailable_and_completed():
    failed = ET.fromstring(build_dial_completion_xml(False, "en"))
    completed = ET.fromstring(build_dial_completion_xml(True, "es"))
    assert "no associate is available" in (failed.findtext("Speak") or "")
    assert completed.find("Hangup") is not None
    assert "Gracias" in (completed.findtext("Speak") or "")


def test_xml_builder_escapes_text_and_hangs_up():
    root = ET.fromstring(build_not_ready_xml("Wait <a moment> & try again"))
    assert root.findtext("Speak") == "Wait <a moment> & try again"
    assert root.find("Hangup") is not None
