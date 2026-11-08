#!/usr/bin/env python3
"""Check whether an API provider supports what the catalog chatbot needs.

Works with the Claude API or any Anthropic-compatible gateway. Set the same
environment variables you use for catalog_server.py, then run:

  python3 check_provider.py

It sends six tiny requests (well under a cent on most providers) and reports
which features work. Your key is read from the environment and never printed.
"""
import json
import os
import urllib.error
import urllib.request

BASE = os.environ.get("ANTHROPIC_BASE_URL", "https://api.anthropic.com").rstrip("/")
KEY = (os.environ.get("ANTHROPIC_API_KEY") or os.environ.get("ANTHROPIC_AUTH_TOKEN") or "").strip()
MODEL = os.environ.get("ANTHROPIC_MODEL", "claude-sonnet-5-5")
DIRECT = "api.anthropic.com" in BASE


def call(method, path, payload=None):
    headers = {"x-api-key": KEY, "anthropic-version": "2023-06-01", "content-type": "application/json"}
    if not DIRECT:
        headers["Authorization"] = f"Bearer {KEY}"
    data = json.dumps(payload).encode() if payload is not None else None
    req = urllib.request.Request(BASE + path, data=data, method=method, headers=headers)
    try:
        with urllib.request.urlopen(req, timeout=90) as r:
            return r.status, json.loads(r.read() or b"{}")
    except urllib.error.HTTPError as e:
        try:
            body = json.loads(e.read())
            msg = body.get("error", {}).get("message") if isinstance(body.get("error"), dict) else body.get("error")
        except ValueError:
            msg = None
        return e.code, {"_error": msg or f"HTTP {e.code}"}
    except urllib.error.URLError as e:
        return 0, {"_error": f"couldn't connect ({e.reason})"}


def message(**extra):
    payload = {"model": MODEL, "max_tokens": 200, "messages": [{"role": "user", "content": "Reply with the word ready."}]}
    payload.update(extra)
    return call("POST", "/v1/messages", payload)


def hint(status, err):
    if status == 0:
        return f"{err}. Check the base URL and your connection."
    if status in (401, 403):
        return f"{err}. The key was rejected: check it's complete, active, and has credit."
    if status == 404:
        return f"{err}. Check the base URL; for Anthropic-format endpoints it usually has no /v1 at the end."
    return err


def main():
    if not KEY:
        raise SystemExit("Set ANTHROPIC_API_KEY (or ANTHROPIC_AUTH_TOKEN) first.")
    print(f"Provider: {BASE}\nModel:    {MODEL}\n")
    results = {}

    # 1. Model list
    status, body = call("GET", "/v1/models")
    ids = [m.get("id", "") for m in body.get("data", [])] if status == 200 else []
    claude = [i for i in ids if "claude" in i]
    if status == 200 and ids:
        ok = MODEL in ids
        results["models"] = ok
        print(("✓" if ok else "✗") + f" Model list: {len(claude)} Claude models listed. "
              + (f"{MODEL} is available." if ok else f"{MODEL} isn't listed. Try one of: {', '.join(claude[:8]) or 'none'}"))
    else:
        print(f"- Model list: not available ({body.get('_error', 'empty')}). Not needed, just informative.")

    # 2. Basic message
    status, body = message()
    ok = status == 200 and any(b.get("type") == "text" for b in body.get("content", []))
    results["basic"] = ok
    if ok:
        served = body.get("model", "unknown")
        note = "" if served.startswith(MODEL) else f" Note: the response says it came from {served}, not {MODEL}."
        print(f"✓ Basic message: answered (model reported: {served}).{note}")
    else:
        print(f"✗ Basic message: {hint(status, body.get('_error'))}")
        return verdict(results)

    # 3. Tool use
    tool = {"name": "lookup_course", "description": "Look up a course by code.",
            "input_schema": {"type": "object", "properties": {"code": {"type": "string"}}, "required": ["code"]}}
    status, body = message(tools=[tool], tool_choice={"type": "tool", "name": "lookup_course"},
                           messages=[{"role": "user", "content": "Look up STAT 22000."}])
    ok = status == 200 and any(b.get("type") == "tool_use" for b in body.get("content", []))
    results["tools"] = ok
    print("✓ Tool use: works." if ok else f"✗ Tool use: {hint(status, body.get('_error', 'no tool call returned'))}")

    # 4. Citable search results
    doc = {"type": "search_result", "source": "https://example.edu/catalog/test", "title": "Test Course",
           "content": [{"type": "text", "text": "TEST 10100 is offered in Autumn and Spring."}], "citations": {"enabled": True}}
    status, body = message(messages=[{"role": "user", "content": [doc, {"type": "text", "text": "When is TEST 10100 offered? Cite the source."}]}])
    ok = status == 200 and any(b.get("citations") for b in body.get("content", []))
    results["citations"] = ok
    if ok:
        print("✓ Citable search results: works. Answers get exact catalog citations.")
    else:
        why = body.get("_error") or "accepted, but no citations came back"
        print(f"✗ Citable search results: {why}. The chatbot switches to tagged-text sources automatically.")

    # 5. Prompt caching
    long_text = ("The College Catalog lists courses, requirements, and policies for undergraduates. " * 300).strip()
    def cached_call(ttl):
        cc = {"type": "ephemeral", "ttl": ttl} if ttl else {"type": "ephemeral"}
        return message(system=[{"type": "text", "text": long_text, "cache_control": cc}])
    ttl_used, (status, first) = "1h", cached_call("1h")
    if status == 400:
        ttl_used, (status, first) = "5m", cached_call(None)
    if status == 200:
        _, second = cached_call("1h" if ttl_used == "1h" else None)
        read = (second.get("usage") or {}).get("cache_read_input_tokens", 0)
        ok = read > 0
        results["caching"] = ok
        label = "1-hour" if ttl_used == "1h" else "5-minute (1-hour was rejected, so the chatbot will use 5-minute)"
        print(f"✓ Prompt caching: {label} cache works ({read:,} tokens read from cache)." if ok else
              "✗ Prompt caching: accepted, but nothing was read from cache on the second call. "
              "The chatbot still works; each question will just cost more.")
    else:
        results["caching"] = False
        print(f"✗ Prompt caching: {hint(status, first.get('_error'))}")

    # 6. Token counting
    status, body = call("POST", "/v1/messages/count_tokens", {"model": MODEL, "messages": [{"role": "user", "content": "hello"}]})
    ok = status == 200 and "input_tokens" in body
    results["count"] = ok
    print("✓ Token counting: works." if ok else
          f"- Token counting: not available ({body.get('_error')}). Only --count-tokens needs it; estimates are in data/stats.json.")
    verdict(results)


def verdict(r):
    print()
    if not r.get("basic"):
        print("Result: this provider can't be used yet. Fix the error above and run the check again.")
    elif not r.get("tools"):
        print("Result: basic chat works, but the catalog chatbot needs tool use, so it won't work with this provider.")
    elif all(r.get(k) for k in ("citations", "caching")):
        print("Result: everything the catalog chatbot uses works with this provider.")
    else:
        print("Result: the catalog chatbot will work with this provider, with the fallbacks noted above.")


if __name__ == "__main__":
    main()
