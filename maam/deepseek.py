"""Private, single-endpoint DeepSeek Responses transport with no fallback."""
from urllib.error import HTTPError
from urllib.request import Request, build_opener

from .generation import NoRedirect
from .migration import canonical

ENDPOINT = "https://api.deepseek.com/responses"
TRANSPORT = "deepseek_responses"


def response(key, payload, timeout):
    body = canonical(payload)
    if key.encode() in body or key[:20].encode() in body:
        raise OSError("credential_in_payload_blocked")
    request = Request(ENDPOINT, data=body, method="POST", headers={
        "Authorization": "Bearer " + key, "Content-Type": "application/json"})
    try:
        handle = build_opener(NoRedirect()).open(request, timeout=timeout)
    except HTTPError as exc:
        code = exc.code
        exc.close()
        raise OSError(f"provider_http_{code}") from None
    with handle:
        if handle.code != 200:
            raise OSError(f"provider_http_{handle.code}")
        raw = handle.read(4 * 1024 * 1024 + 1)
        if len(raw) > 4 * 1024 * 1024:
            raise OSError("provider_response_too_large")
        if key.encode() in raw or key[:20].encode() in raw:
            raise OSError("credential_echo_blocked")
        return handle.code, handle.headers.get("x-request-id"), raw


def input_allowance(payload, limit):
    """Reserve the full input limit; this is not a provider tokenizer count.

The byte screen leaves framing headroom, but is not a tokenizer guarantee.
Actual provider usage is checked afterward and any overrun stops the run.
"""
    size = len(canonical(payload))
    if size + 2048 > limit:
        raise OSError("input_payload_exceeds_local_byte_screen")
    return 200, None, canonical({"input_tokens": limit, "payload_bytes": size,
                                "method": "full_input_budget_reservation_not_token_count"})
