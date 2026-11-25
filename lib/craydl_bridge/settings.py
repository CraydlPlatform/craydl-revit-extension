"""User settings and opaque protected token storage; no Windows imports."""

from __future__ import unicode_literals

import base64
import io
import json
import os
import unicodedata

DEFAULT_URL = "https://ccc.craydl.com/api/assistant/mcp"


def _directory(directory):
    if not os.path.isdir(directory):
        os.makedirs(directory)


def _url(values):
    url = values.get("url", DEFAULT_URL)
    # Do not permit credentials, whitespace or an empty host in an endpoint.
    if not isinstance(url, type("")) and not isinstance(url, str):
        raise ValueError("The endpoint must be an HTTPS URL.")
    authority = url[8:].split("/", 1)[0].split("?", 1)[0].split("#", 1)[0]
    if (
        not url.startswith("https://")
        or not authority
        or "@" in authority
        or any(
            character.isspace() or unicodedata.category(character) == "Cc"
            for character in url
        )
    ):
        raise ValueError(
            "The endpoint must be an HTTPS URL without credentials or whitespace."
        )
    return url


def normalize_token(token):
    if not isinstance(token, type("")) and not isinstance(token, str):
        raise ValueError("Enter a nonempty token without control characters.")
    token = token.strip(" \t\r\n\v\f")
    if not token or any(unicodedata.category(character) == "Cc" for character in token):
        raise ValueError("Enter a nonempty token without control characters.")
    token = token.strip()
    if not token:
        raise ValueError("Enter a nonempty token without control characters.")
    return token


def load(directory):
    path = os.path.join(directory, "config.json")
    if not os.path.exists(path):
        return {"url": DEFAULT_URL}
    failed = False
    try:
        with io.open(path, "r", encoding="utf-8") as handle:
            values = json.load(handle)
    except (ValueError, UnicodeError):
        failed = True
    if failed or not isinstance(values, dict):
        raise ValueError("Could not read the Craydl endpoint settings.")
    return {"url": _url(values)}


def save(directory, values):
    url = _url(values)
    _directory(directory)
    with io.open(
        os.path.join(directory, "config.json"), "w", encoding="utf-8"
    ) as handle:
        handle.write("%s" % json.dumps({"url": url}))


def save_token(directory, token, protect):
    token = normalize_token(token)
    encoded = base64.b64encode(protect(token.encode("utf-8"))).decode("ascii")
    _directory(directory)
    with io.open(
        os.path.join(directory, "token.dpapi"), "w", encoding="ascii"
    ) as handle:
        handle.write(encoded)


def load_token(directory, unprotect):
    try:
        with io.open(
            os.path.join(directory, "token.dpapi"), "r", encoding="ascii"
        ) as handle:
            encoded = handle.read().encode("ascii")
        plaintext = unprotect(base64.b64decode(encoded))
        return normalize_token(plaintext.decode("utf-8"))
    except Exception:
        # Missing, corrupt and encrypted-for-another-user files are disconnected.
        return None


def clear_token(directory):
    path = os.path.join(directory, "token.dpapi")
    if os.path.exists(path):
        os.remove(path)
