#!/usr/bin/env python3
"""Get Kahoot Quiz ID from a Game PIN.

Usage:
    python get_kahoot_id.py <game_pin>
    python get_kahoot_id.py          (prompts for PIN)
"""

import sys
import json
import socket
import urllib.request
import urllib.error
import time
import re
import base64


def decode_challenge(challenge, session_token):
    """Decode the Kahoot session token using the challenge string.

    Kahoot encodes the session token (from the X-Kahoot-Session-Token header)
    using a key derived from the challenge JavaScript snippet.  The key is
    built by extracting every digit that appears in the challenge and
    concatenating them, then XOR-ing against the base64-decoded token bytes.

    Args:
        challenge: The 'challenge' field string returned by the API.
        session_token: The 'X-Kahoot-Session-Token' response header value.

    Returns:
        The decoded token string, or None if decoding fails.
    """
    try:
        # The decode key is composed of all digit characters in the challenge
        key = "".join(re.findall(r"\d", challenge))
        if not key:
            print("[decode_challenge] No digits found in challenge; cannot decode.")
            return None

        raw = base64.b64decode(session_token).decode("latin-1")
        decoded = "".join(
            chr(ord(raw[i]) ^ ord(key[i % len(key)])) for i in range(len(raw))
        )
        return decoded
    except Exception as exc:  # pylint: disable=broad-except
        print(f"[decode_challenge] Error: {type(exc).__name__}: {exc}")
        return None


def extract_quiz_id(data, decoded_token=None):
    """Try to find the quiz UUID in all available response data.

    Args:
        data: Parsed JSON response body (dict).
        decoded_token: Optional decoded session token string.

    Returns:
        Quiz UUID string if found, else None.
    """
    # Direct fields in the response body
    for field in ("quizId", "quiz_id", "quizUuid", "uuid", "id", "kahootId"):
        if data.get(field):
            return data[field]

    # Nested under common wrapper keys
    for wrapper in ("kahoot", "quiz", "game", "session"):
        nested = data.get(wrapper)
        if isinstance(nested, dict):
            for field in ("uuid", "id", "quizId", "quiz_id"):
                if nested.get(field):
                    return nested[field]

    # The decoded token is sometimes a JSON payload
    if decoded_token:
        try:
            token_data = json.loads(decoded_token)
            for field in ("quizId", "quiz_id", "uuid", "id"):
                if token_data.get(field):
                    return token_data[field]
        except (json.JSONDecodeError, AttributeError):
            # Token is a plain string (WebSocket session key), not JSON
            pass

    return None


def get_quiz_id(pin):
    """Fetch the Kahoot Quiz ID for the given Game PIN.

    Contacts the Kahoot session reservation API, prints all response
    details, and attempts to extract the Quiz UUID from the data.

    Args:
        pin: Kahoot Game PIN as a string.

    Returns:
        Quiz UUID string on success, or None on failure.
    """
    timestamp = int(time.time() * 1000)
    url = f"https://kahoot.it/reserve/session/{pin}/?{timestamp}"

    print(f"[*] Game PIN   : {pin}")
    print(f"[*] Request URL: {url}")

    req_headers = {
        "User-Agent": (
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
            "AppleWebKit/537.36 (KHTML, like Gecko) "
            "Chrome/122.0.0.0 Safari/537.36"
        ),
        "Accept": "application/json, text/plain, */*",
        "Accept-Language": "en-US,en;q=0.9",
        "Origin": "https://kahoot.it",
        "Referer": "https://kahoot.it/",
    }

    try:
        request = urllib.request.Request(url, headers=req_headers)
        with urllib.request.urlopen(request, timeout=15) as response:
            status = response.status
            resp_headers = dict(response.headers)
            body = response.read().decode("utf-8")

        print(f"\n[+] HTTP Status : {status}")

        print("\n[+] Response Headers:")
        for key, value in resp_headers.items():
            print(f"    {key}: {value}")

        try:
            data = json.loads(body)
        except json.JSONDecodeError as exc:
            print(f"\n[-] Failed to parse response body as JSON: {exc}")
            print(f"    Raw body: {body!r}")
            return None

        print("\n[+] Response Body (JSON):")
        print(json.dumps(data, indent=2))

        # Attempt to decode the challenge + session token
        session_token = resp_headers.get("X-Kahoot-Session-Token") or resp_headers.get(
            "x-kahoot-session-token"
        )
        challenge = data.get("challenge", "")
        decoded_token = None

        if session_token:
            print(f"\n[+] Session Token Header: {session_token}")
            if challenge:
                print(f"\n[+] Challenge: {challenge}")
                decoded_token = decode_challenge(challenge, session_token)
                if decoded_token is not None:
                    print(f"[+] Decoded Token: {decoded_token}")
                else:
                    print("[-] Could not decode session token from challenge.")
            else:
                print("[-] No 'challenge' field in response; skipping token decode.")
        else:
            print("[-] No X-Kahoot-Session-Token header in response.")

        quiz_id = extract_quiz_id(data, decoded_token)
        if quiz_id:
            print(f"\n[✓] Quiz ID: {quiz_id}")
            return quiz_id

        print(
            "\n[-] Quiz ID not found in the HTTP response. "
            "For live games the quiz UUID is only available via the "
            "WebSocket game session (wss://kahoot.it/cometd/<pin>/<token>)."
        )
        return None

    except urllib.error.HTTPError as exc:
        print(f"\n[-] HTTP Error: {exc.code} {exc.reason}")
        try:
            error_body = exc.read().decode("utf-8")
            print(f"    Error body: {error_body}")
        except Exception as read_exc:  # pylint: disable=broad-except
            print(f"    Could not read error body: {type(read_exc).__name__}: {read_exc}")
        if exc.code == 404:
            print(
                "    The game PIN was not found. "
                "The game may have ended or the PIN may be incorrect."
            )
        elif exc.code == 429:
            print("    Rate-limited by Kahoot. Please wait a moment and try again.")
        elif exc.code >= 500:
            print("    Kahoot server error. Please try again later.")
        return None

    except urllib.error.URLError as exc:
        print(f"\n[-] Network Error: {exc.reason}")
        return None

    except socket.timeout:
        print("\n[-] Request timed out. Check your internet connection and try again.")
        return None

    except Exception as exc:  # pylint: disable=broad-except
        print(f"\n[-] Unexpected error: {type(exc).__name__}: {exc}")
        return None


def main():
    """Entry point: parse the PIN from argv or stdin, then look up the quiz."""
    if len(sys.argv) > 1:
        pin = sys.argv[1].strip()
    else:
        try:
            pin = input("Enter Kahoot Game PIN: ").strip()
        except (EOFError, KeyboardInterrupt):
            print("\nAborted.")
            sys.exit(1)

    if not pin:
        print("[-] Error: No PIN provided.")
        sys.exit(1)

    if not pin.isdigit():
        print(f"[!] Warning: PIN '{pin}' contains non-numeric characters.")

    quiz_id = get_quiz_id(pin)
    sys.exit(0 if quiz_id is not None else 1)


if __name__ == "__main__":
    main()
