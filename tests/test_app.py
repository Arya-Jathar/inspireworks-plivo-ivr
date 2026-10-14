from xml.etree import ElementTree as ET
from app import create_app

BASE_CONFIG = {
    "TESTING": True,
    "PLIVO_AUTH_ID": "test-auth-id",
    "PLIVO_AUTH_TOKEN": "test-auth-token",
    "PLIVO_FROM_NUMBER": "+918035454161",
    "PLIVO_PUBLIC_BASE_URL": "https://ivrdemo.ngrok-free.app",
    "ALLOWED_DESTINATION_NUMBER": "+919876543210",
    "CALL_TRIGGER_PIN": "safe-test-pin",
    "OTP_CODE": "1503",
    "ASSOCIATE_NUMBER": "+912264236412",
}

class FakeCallResponse:
    request_uuid = "request-uuid-123"

class FakeCalls:
    def __init__(self, result=None, error=None):
        self.result, self.error, self.kwargs = result or FakeCallResponse(), error, None
    def create(self, **kwargs):
        self.kwargs = kwargs
        if self.error:
            raise self.error
        return self.result

class FakePlivoClient:
    def __init__(self, auth_id, auth_token, calls):
        assert auth_id == BASE_CONFIG["PLIVO_AUTH_ID"]
        assert auth_token == BASE_CONFIG["PLIVO_AUTH_TOKEN"]
        self.calls = calls

def make_client(config=None):
    merged = dict(BASE_CONFIG)
    if config:
        merged.update(config)
    return create_app(merged).test_client()

def start_call(client, call_uuid="call-123"):
    return client.get("/voice/answer", query_string={"CallUUID": call_uuid})

def post(client, route, digits=None, call_uuid="call-123", **params):
    payload = {"CallUUID": call_uuid, **params}
    if digits is not None:
        payload["Digits"] = digits
    return client.post(route, data=payload)

def authenticate(client, call_uuid="call-123", language="1"):
    start_call(client, call_uuid)
    post(client, "/voice/otp", "1503", call_uuid)
    return post(client, "/voice/language", language, call_uuid)


def test_health_does_not_leak_secrets():
    client = make_client()
    response = client.get("/health")
    body = response.get_json()
    assert response.status_code == 200 and body["configured"] is True
    assert "test-auth-token" not in response.get_data(as_text=True)
    assert "safe-test-pin" not in response.get_data(as_text=True)
    assert "1503" not in response.get_data(as_text=True)


def test_homepage_and_answer_webhook_load():
    client = make_client()
    assert b"Call Me" in client.get("/").data
    response = start_call(client)
    assert response.status_code == 200 and response.mimetype == "application/xml"
    root = ET.fromstring(response.get_data(as_text=True))
    assert root.find("GetInput").attrib["numDigits"] == "4"
    assert client.application.extensions["ivr_sessions"]["call-123"]["authenticated"] is False


def test_answer_missing_call_uuid_fails_closed():
    root = ET.fromstring(make_client().get("/voice/answer").get_data(as_text=True))
    assert root.find("Hangup") is not None


def test_correct_otp_unlocks_language_menu():
    client = make_client(); start_call(client)
    response = post(client, "/voice/otp", "1503")
    root = ET.fromstring(response.get_data(as_text=True))
    assert root.find("GetInput").attrib["action"].endswith("/voice/language")
    assert client.application.extensions["ivr_sessions"]["call-123"]["authenticated"] is True


def test_wrong_otp_retries_without_authenticating_and_then_correct_succeeds():
    client = make_client(); start_call(client)
    for digits in ("1234", "1111"):
        root = ET.fromstring(post(client, "/voice/otp", digits).get_data(as_text=True))
        assert root.find("GetInput").attrib["action"].endswith("/voice/otp")
        assert client.application.extensions["ivr_sessions"]["call-123"]["authenticated"] is False
    root = ET.fromstring(post(client, "/voice/otp", "1503").get_data(as_text=True))
    assert root.find("GetInput").attrib["action"].endswith("/voice/language")


def test_leading_zero_code_is_preserved_and_malformed_input_rejected():
    client = make_client({"OTP_CODE": "0503"}); start_call(client)
    malformed = ET.fromstring(post(client, "/voice/otp", "503").get_data(as_text=True))
    assert malformed.find("GetInput").attrib["action"].endswith("/voice/otp")
    assert client.application.extensions["ivr_sessions"]["call-123"]["authenticated"] is False
    post(client, "/voice/otp", "0503")
    assert client.application.extensions["ivr_sessions"]["call-123"]["authenticated"] is True


def test_unauthenticated_caller_cannot_access_later_routes():
    client = make_client(); start_call(client)
    for route in ("/voice/language", "/voice/menu", "/voice/action", "/voice/dial-complete"):
        response = client.post(route, data={"CallUUID": "call-123", "Digits": "2"})
        assert ET.fromstring(response.get_data(as_text=True)).find("Hangup") is not None


def test_language_selection_enables_localized_level_two_menu():
    for digit, language, expected in (("1", "en", "Press 1 to hear"), ("2", "es", "Pulse 1 para escuchar")):
        client = make_client(); start_call(client); post(client, "/voice/otp", "1503")
        root = ET.fromstring(post(client, "/voice/language", digit).get_data(as_text=True))
        collector = root.find("GetInput")
        assert collector is not None and expected in " ".join(x.text or "" for x in collector.findall("Speak"))
        assert client.application.extensions["ivr_sessions"]["call-123"]["language"] == language


def test_invalid_language_choice_repeats_level_one_menu():
    client = make_client(); start_call(client); post(client, "/voice/otp", "1503")
    root = ET.fromstring(post(client, "/voice/language", "9").get_data(as_text=True))
    assert root.find("GetInput").attrib["action"].endswith("/voice/language")


def test_audio_option_plays_clip_and_returns_to_level_two():
    client = make_client(); authenticate(client, language="1")
    root = ET.fromstring(post(client, "/voice/action", "1").get_data(as_text=True))
    assert root.findtext("Play") == "https://s3.amazonaws.com/plivocloud/Trumpet.mp3"
    assert root.findtext("Redirect").endswith("/voice/menu")
    assert "demonstration audio message" in (root.findtext("Speak") or "")


def test_spanish_audio_option_uses_spanish_prompt():
    client = make_client(); authenticate(client, language="2")
    root = ET.fromstring(post(client, "/voice/action", "1").get_data(as_text=True))
    assert "mensaje de demostración" in (root.findtext("Speak") or "")


def test_invalid_action_repeats_menu():
    client = make_client(); authenticate(client)
    root = ET.fromstring(post(client, "/voice/action", "9").get_data(as_text=True))
    assert root.find("GetInput").attrib["action"].endswith("/voice/action")
    assert "Invalid option" in (root.findtext("GetInput/Speak") or "")


def test_associate_option_dials_configured_number():
    client = make_client(); authenticate(client, language="1")
    root = ET.fromstring(post(client, "/voice/action", "2").get_data(as_text=True))
    dial = root.find("Dial")
    assert dial is not None and dial.findtext("Number") == "+912264236412"
    assert dial.attrib["action"].endswith("/voice/dial-complete")


def test_missing_associate_line_returns_to_menu_safely():
    client = make_client({"ASSOCIATE_NUMBER": ""}); authenticate(client)
    root = ET.fromstring(post(client, "/voice/action", "2").get_data(as_text=True))
    assert root.find("GetInput") is not None
    assert "not configured" in (root.findtext("GetInput/Speak") or "")


def test_dial_completion_success_and_failure():
    client = make_client(); authenticate(client)
    success = ET.fromstring(post(client, "/voice/dial-complete", call_uuid="call-123", DialStatus="completed").get_data(as_text=True))
    fail = ET.fromstring(post(client, "/voice/dial-complete", call_uuid="call-123", DialStatus="no-answer").get_data(as_text=True))
    assert success.find("Hangup") is not None and "Thank you" in (success.findtext("Speak") or "")
    assert fail.find("Hangup") is not None and "no associate is available" in (fail.findtext("Speak") or "")


def test_sessions_are_isolated_by_call_uuid():
    client = make_client(); start_call(client, "A"); start_call(client, "B")
    post(client, "/voice/otp", "1503", "A"); post(client, "/voice/language", "2", "A")
    sessions = client.application.extensions["ivr_sessions"]
    assert sessions["A"]["authenticated"] is True and sessions["A"]["language"] == "es"
    assert sessions["B"]["authenticated"] is False and sessions["B"]["language"] is None


def test_missing_session_fails_closed():
    root = ET.fromstring(post(make_client(), "/voice/otp", "1503", "unknown").get_data(as_text=True))
    assert root.find("Hangup") is not None


def test_timeout_retries_then_hangs_up_after_three_consecutive_silences():
    client = make_client(); start_call(client)
    first = post(client, "/voice/otp-timeout", call_uuid="call-123")
    second = post(client, "/voice/otp-timeout", call_uuid="call-123")
    third = post(client, "/voice/otp-timeout", call_uuid="call-123")
    assert ET.fromstring(first.get_data(as_text=True)).find("GetInput") is not None
    assert ET.fromstring(second.get_data(as_text=True)).find("GetInput") is not None
    assert ET.fromstring(third.get_data(as_text=True)).find("Hangup") is not None


def test_outbound_call_uses_plivo_api_with_safe_input_checks():
    calls = FakeCalls()
    factory = lambda auth_id, token: FakePlivoClient(auth_id, token, calls)
    client = make_client({"PLIVO_CLIENT_FACTORY": factory})
    response = client.post("/api/calls", json={"to": "+919876543210", "trigger_pin": "safe-test-pin"})
    assert response.status_code == 202
    assert calls.kwargs["from_"] == "+918035454161"
    assert calls.kwargs["to_"] == "+919876543210"
    assert calls.kwargs["answer_url"] == "https://ivrdemo.ngrok-free.app/voice/answer"


def test_outbound_call_rejects_bad_pin_and_destination():
    client = make_client()
    assert client.post("/api/calls", json={"to": "+919876543210", "trigger_pin": "bad"}).status_code == 401
    assert client.post("/api/calls", json={"to": "+919999999999", "trigger_pin": "safe-test-pin"}).status_code == 403
    assert client.post("/api/calls", json={"to": "not-a-number", "trigger_pin": "safe-test-pin"}).status_code == 400


def test_outbound_call_reports_api_error_without_leaking_it():
    calls = FakeCalls(error=RuntimeError("mock-token-secret"))
    client = make_client({"PLIVO_CLIENT_FACTORY": lambda aid, tok: FakePlivoClient(aid, tok, calls)})
    response = client.post("/api/calls", json={"to": "+919876543210", "trigger_pin": "safe-test-pin"})
    assert response.status_code == 502
    assert "mock-token-secret" not in response.get_data(as_text=True)
