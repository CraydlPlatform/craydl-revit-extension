"""Small synchronous MCP client, compatible with IronPython 2.7."""

from __future__ import unicode_literals

import json


_TEXT_TYPES = (type(""), str)
_UNCERTAIN_WRITE = "Craydl may have made the write. Check before trying again."


class CraydlError(Exception):
    """A safe-to-display bridge failure with a stable category."""

    def __init__(self, code, message):
        self.code = code
        Exception.__init__(self, message)


class CraydlClient(object):
    def __init__(self, url, token, transport, client_version):
        self._url = url
        self._token = token
        self._transport = transport
        self._client_version = client_version
        self._session_id = None
        self._initialized = False
        self._request_id = 0

    def __repr__(self):
        return "<CraydlClient>"

    def _tool_error(self, text):
        if not isinstance(text, type("")) and not isinstance(text, str):
            text = "Server reported a tool error."
        # A server or proxy may echo request credentials. Redact before bounding.
        if self._token:
            text = text.replace(self._token, "[redacted]")
        return CraydlError("tool_error", text[:300])

    def _parse_json(self, text):
        failed = False
        try:
            value = json.loads(text)
        except (ValueError, TypeError):
            failed = True
        if failed:
            raise CraydlError("protocol", "Invalid JSON in the server reply.")
        return value

    def _request(self, method, params):
        self._request_id += 1
        request = {
            "jsonrpc": "2.0",
            "id": self._request_id,
            "method": method,
            "params": params,
        }
        headers = {
            "Authorization": "Bearer " + self._token,
            "Content-Type": "application/json",
            "Accept": "application/json, text/event-stream",
        }
        if self._session_id:
            headers["Mcp-Session-Id"] = self._session_id
        failed = False
        try:
            status, response_headers, body = self._transport(
                self._url, headers, json.dumps(request)
            )
        except Exception:
            failed = True
        # Raise outside the handler: even a formatted traceback must not echo
        # a transport exception containing the Authorization header.
        if failed:
            raise CraydlError("http", "Could not reach the Craydl endpoint.")
        if status in (401, 403):
            raise CraydlError(
                "unauthorized", "Craydl refused this token (HTTP %s)." % status
            )
        if status != 200:
            raise CraydlError("http", "Craydl returned HTTP %s." % status)
        if "text/event-stream" in response_headers.get("content-type", "").lower():
            lines = [
                line[5:].strip()
                for line in body.splitlines()
                if line.startswith("data:")
            ]
            if not lines:
                raise CraydlError("protocol", "The event stream contained no data.")
            body = lines[-1]
        reply = self._parse_json(body)
        if (
            not isinstance(reply, dict)
            or reply.get("jsonrpc") != "2.0"
            or reply.get("id") != self._request_id
        ):
            raise CraydlError("protocol", "Invalid JSON-RPC reply.")
        if "error" in reply:
            error = reply["error"]
            raise self._tool_error(
                error.get("message") if isinstance(error, dict) else error
            )
        result = reply.get("result")
        if not isinstance(result, dict):
            raise CraydlError("protocol", "Missing JSON-RPC result.")
        session_id = response_headers.get("mcp-session-id")
        if session_id:
            self._session_id = session_id
        return result

    def initialize(self):
        if not self._initialized:
            result = self._request(
                "initialize",
                {
                    "protocolVersion": "2025-06-18",
                    "capabilities": {},
                    "clientInfo": {
                        "name": "craydl-revit",
                        "version": self._client_version,
                    },
                },
            )
            if result.get("protocolVersion") != "2025-06-18" or not isinstance(
                result.get("capabilities"), dict
            ):
                self._session_id = None
                raise CraydlError(
                    "protocol", "Invalid or unsupported initialize reply."
                )
            self._initialized = True

    def list_tools(self):
        """Return all advertised tool names, or raise without returning a partial set."""
        self.initialize()
        names = set()
        params = {}
        for unused in range(20):
            page = self._request("tools/list", params)
            tools = page.get("tools")
            if not isinstance(tools, list):
                raise CraydlError("protocol", "Invalid tool list.")
            for tool in tools:
                if not isinstance(tool, dict) or not isinstance(
                    tool.get("name"), _TEXT_TYPES
                ):
                    raise CraydlError("protocol", "Invalid tool name in the list.")
                names.add(tool["name"])
            cursor = page.get("nextCursor")
            if cursor is None:
                return names
            if not isinstance(cursor, _TEXT_TYPES):
                raise CraydlError("protocol", "Invalid cursor in the tool list.")
            params = {"cursor": cursor}
        raise CraydlError("incomplete", "The tool list exceeded the page safety limit.")

    def call_tool(self, name, arguments):
        self.initialize()
        result = self._request("tools/call", {"name": name, "arguments": arguments})
        content = result.get("content")
        text = None
        if isinstance(content, list) and content and isinstance(content[0], dict):
            text = content[0].get("text")
        if result.get("isError") is True:
            raise self._tool_error(text)
        return self._parse_json(text)

    def _call_write(self, name, arguments, states):
        try:
            reply = self.call_tool(name, arguments)
        except CraydlError as error:
            if error.code == "tool_error":
                try:
                    payload = json.loads(error.args[0])
                except (ValueError, TypeError):
                    pass  # Unstructured errors do not prove a refusal.
                else:
                    if (
                        not isinstance(payload, dict)
                        or payload.get("code") != "unavailable"
                    ):
                        raise
            elif error.code not in ("http", "protocol"):
                raise
        else:
            if isinstance(reply, dict) and reply.get("state") in states:
                return reply
        # Do not chain an exception from the request, and never retry the write.
        raise CraydlError("uncertain", _UNCERTAIN_WRITE)

    def write(self, name, arguments):
        """Execute a direct write or confirm one matching proposal, without retries."""
        reply = self._call_write(name, arguments, ("proposed", "executed"))
        if reply["state"] == "executed":
            return reply

        action_id = reply.get("action_id")
        target = reply.get("target")
        if not isinstance(action_id, _TEXT_TYPES) or not isinstance(target, dict):
            raise CraydlError("uncertain", _UNCERTAIN_WRITE)
        # CD4A binds a room proposal to the job the modeler saw before Apply.
        if name == "create_job_room":
            job_id = target.get("job_id")
            if not isinstance(job_id, _TEXT_TYPES) or job_id != arguments.get("job_id"):
                raise CraydlError(
                    "protocol", "The room proposal did not name the requested job."
                )
        for key, value in target.items():
            if (
                isinstance(value, _TEXT_TYPES)
                and key in arguments
                and value != arguments[key]
            ):
                raise CraydlError(
                    "protocol", "The proposal target did not match the request."
                )
        return self._call_write(name, {"action_id": action_id}, ("executed",))

    def read_all(self, name, arguments, page_limit=50, max_pages=20):
        if page_limit < 1 or max_pages < 1:
            raise CraydlError("incomplete", "Page limits must be positive.")
        args = dict(arguments)
        args["limit"] = page_limit
        records = []
        for unused in range(max_pages):
            page = self.call_tool(name, args)
            if not isinstance(page, dict) or not isinstance(page.get("data"), dict):
                raise CraydlError("protocol", "Invalid list page.")
            rows = page["data"].get("records")
            complete = page.get("complete")
            if not isinstance(rows, list) or not isinstance(complete, bool):
                raise CraydlError(
                    "protocol", "Invalid list records or completion flag."
                )
            for row in rows:
                if not isinstance(row, dict) or "data" not in row:
                    raise CraydlError("protocol", "Invalid list record.")
                records.append(row["data"])
            if complete:
                return records
            cursor = page.get("next_cursor")
            if not cursor:
                raise CraydlError(
                    "incomplete",
                    "The server returned an incomplete list without a cursor.",
                )
            args["cursor"] = cursor
        raise CraydlError("incomplete", "The list exceeded the page safety limit.")
