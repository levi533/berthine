import json
import re
from json import JSONDecodeError


PHONE_PATTERN = re.compile(r"^\+?[1-9]\d{6,14}$")


def parse_json_body(request):
    try:
        body = json.loads(request.body)
    except (JSONDecodeError, UnicodeDecodeError):
        return None
    return body if isinstance(body, dict) else None


def normalize_phone(value):
    if not isinstance(value, str):
        return ""
    phone = re.sub(r"[\s().-]", "", value)
    return phone if PHONE_PATTERN.fullmatch(phone) else ""
