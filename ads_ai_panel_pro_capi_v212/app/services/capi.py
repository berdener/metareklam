
import os, time, hashlib, re, requests

META_PIXEL_ID = os.getenv("META_PIXEL_ID")
META_ACCESS_TOKEN = os.getenv("META_ACCESS_TOKEN")
META_TEST_EVENT_CODE = os.getenv("META_TEST_EVENT_CODE")

GRAPH_URL = f"https://graph.facebook.com/v17.0/{META_PIXEL_ID}/events" if META_PIXEL_ID else None

def _sha256_norm(s: str) -> str:
    if not s:
        return ""
    s = s.strip().lower()
    return hashlib.sha256(s.encode("utf-8")).hexdigest()

def _normalize_phone(phone: str) -> str:
    if not phone:
        return ""
    digits = re.sub(r"[^0-9]", "", phone)
    if digits.startswith("0") and len(digits) == 11:
        digits = "90" + digits[1:]
    return hashlib.sha256(digits.encode("utf-8")).hexdigest() if digits else ""

def send_capi_event(event_name: str, value: float, currency: str, email: str = "", phone: str = "", 
                    event_id: str = None, fbp: str = None, fbc: str = None,
                    event_source_url: str = None, client_user_agent: str = None, test_mode: bool = False):
    if not (META_PIXEL_ID and META_ACCESS_TOKEN):
        return {"skipped": True, "reason": "Missing META_PIXEL_ID or META_ACCESS_TOKEN"}

    user_data = {
        "em": _sha256_norm(email),
        "ph": _normalize_phone(phone),
    }
    if fbp: user_data["fbp"] = fbp
    if fbc: user_data["fbc"] = fbc
    if client_user_agent:
        user_data["client_user_agent"] = client_user_agent

    event = {
        "event_name": event_name,
        "event_time": int(time.time()),
        "action_source": "website",
        "event_id": event_id or f"svr-{int(time.time())}",
        "user_data": user_data,
        "custom_data": {
            "currency": currency or "TRY",
            "value": float(value or 0.0),
        }
    }
    if event_source_url:
        event["event_source_url"] = event_source_url

    payload = {"data": [event], "access_token": META_ACCESS_TOKEN}
    if test_mode and META_TEST_EVENT_CODE:
        payload["test_event_code"] = META_TEST_EVENT_CODE

    r = requests.post(GRAPH_URL, json=payload, timeout=20)
    try:
        return r.json()
    except Exception:
        return {"status_code": r.status_code, "text": r.text}
