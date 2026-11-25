"""Connect the current Windows user to Craydl; never change the model."""

from __future__ import unicode_literals

from pyrevit import forms

from craydl_bridge import __version__, host, settings
from craydl_bridge.client import CraydlClient, CraydlError


def main():
    try:
        directory = host.settings_directory()
        values = settings.load(directory)
        stored = settings.load_token(directory, host.unprotect)
    except Exception:
        forms.alert(
            "Could not read Craydl settings. Check your Windows profile permissions.",
            title="Craydl",
        )
        return
    state = (
        "Connected (stored token; not yet verified this session)"
        if stored
        else "Not connected"
    )
    forms.alert(
        "%s\nEndpoint: %s\nExtension: %s\n\n"
        "Create your token in Craydl under Connected Agents. "
        "Grant it no direct-action permission (leave both direct-action grants off)."
        % (state, values["url"], __version__),
        title="Craydl Connect",
    )
    choice = forms.CommandSwitchWindow.show(
        ["Connect", "Disconnect"], message="Craydl connection"
    )
    if choice == "Disconnect":
        try:
            settings.clear_token(directory)
        except Exception:
            forms.alert(
                "Could not remove the stored token. Check your Windows profile permissions.",
                title="Craydl",
            )
            return
        forms.alert(
            "Disconnected. The local token was removed; revoke it in Connected Agents if needed.",
            title="Craydl",
        )
        return
    if choice != "Connect":
        return
    token = forms.ask_for_string(
        prompt="Paste a Connected Agents token with no direct-action permission. "
        "It will be stored encrypted for this Windows user only.",
        title="Craydl Connect",
    )
    if token is None:
        return
    try:
        token = settings.normalize_token(token)
    except ValueError as error:
        forms.alert(str(error), title="Craydl Connect")
        return
    client = CraydlClient(values["url"], token, host.transport, __version__)
    stage = "initialize"
    try:
        client.initialize()
        stage = "job_search"
        client.call_tool("job_search", {"limit": 1})
    except CraydlError as error:
        forms.alert(
            "%s failed (%s): %s\nThe new token was not stored."
            % (stage, error.code, error.args[0]),
            title="Craydl Connect",
        )
        return
    try:
        settings.save(directory, values)
        settings.save_token(directory, token, host.protect)
    except Exception:
        forms.alert(
            "Verification succeeded, but the token could not be stored. "
            "Check your Windows profile permissions and reconnect.",
            title="Craydl Connect",
        )
        return
    forms.alert(
        "Connected. initialize and job_search succeeded; the token is stored encrypted for this Windows user.",
        title="Craydl Connect",
    )


main()
