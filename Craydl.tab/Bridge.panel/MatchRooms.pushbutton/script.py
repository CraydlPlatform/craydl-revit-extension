"""Review and apply room matches without saving or syncing."""

from __future__ import unicode_literals

from pyrevit import forms, revit, script

from craydl_bridge import host, host_rooms_ui, params, seed
from craydl_bridge.client import CraydlError

TITLE = "Craydl Match Rooms"
CREATE_ROOM = "create_job_room"


def empty_result():
    return {
        key: []
        for key in (
            "created",
            "linked",
            "moved",
            "skipped",
            "sent",
            "unlinked",
            "not_sent",
            "uncertain",
        )
    }


def send_room(client, job_id, model):
    args = {"job_id": job_id, "name": model["name"], "origin": "model"}
    for field in ("level", "number"):
        value = model[field].strip()
        if value:
            args[field] = value
    for field, limit in (("name", 240), ("level", 60), ("number", 30)):
        if len(args.get(field, "")) > limit:
            raise CraydlError(
                "too_long",
                "The room's %s is longer than %s characters." % (field, limit),
            )
    reply = client.write(CREATE_ROOM, args)
    data = reply.get("data") if isinstance(reply, dict) else None
    room_id = data.get("id") if isinstance(data, dict) else None
    if not params.is_job_id(room_id):
        raise CraydlError("uncertain", "Craydl did not return a valid room ID.")
    return {
        "action": "link",
        "room": {"id": room_id, "display_name": model["name"]},
        "element_id": model["element_id"],
        "rename": False,
    }


def send_rooms(client, job_id, plan, targets, result):
    by_element = {model["element_id"]: model for model in plan["sendable"]}
    links = []
    for element_id in sorted(targets):
        model = by_element[element_id]
        try:
            links.append(send_room(client, job_id, model))
        except CraydlError as error:
            if error.code == "uncertain":
                result["uncertain"].append(model)
            else:
                result["not_sent"].append((model, error.args[0]))
    return links


def classify_sent_links(result, targets):
    # The checked batch never links a model room twice. Keep send outcomes
    # separate from ordinary Revit links/skips, even on transaction rollback.
    for source, destination in (("linked", "sent"), ("skipped", "unlinked")):
        other = []
        for entry in result[source]:
            action = entry["action"]
            if action["action"] == "link" and action["element_id"] in targets:
                result[destination].append(entry)
            else:
                other.append(entry)
        result[source] = other


def room_label(model):
    return "%s %s" % (model["number"], model["name"])


def report_line(label, model=None, room=None, detail=""):
    model = model or {}
    return [
        label,
        model.get("name", ""),
        model.get("number", ""),
        model.get("phase", ""),
        (room or {}).get("display_name", ""),
        detail,
    ]


def report_lines(plan, actions, result, model_rooms, send_targets):
    chosen = {a["room"]["id"] for a in actions}
    by_element = {model["element_id"]: model for model in model_rooms}
    applied_targets, moved_ids = set(send_targets), set()
    for key, label in (
        ("created", "Created"),
        ("linked", "Linked"),
        ("moved", "Moved"),
    ):
        for entry in result[key]:
            records = entry["model_rooms"]
            model = records[-1]
            room = entry["action"]["room"]
            if key != "created":
                applied_targets.add(model["element_id"])
            detail = ""
            if key == "moved":
                moved_ids.add(room["id"])
                detail = "from " + room_label(records[0])
            yield report_line(label, model, room, detail)
    for entry in result["skipped"]:
        action = entry["action"]
        target = action.get("element_id", action.get("to_element_id"))
        yield report_line(
            "Skipped", by_element.get(target), action["room"], entry["reason"]
        )
    for entry in result["sent"]:
        room = entry["action"]["room"]
        yield report_line(
            "Sent to Craydl",
            entry["model_rooms"][0],
            room,
            "New Craydl room %s." % room["id"],
        )
    for model, reason in result["not_sent"]:
        yield report_line("Not sent", model, detail=reason)
    for entry in result["unlinked"]:
        action = entry["action"]
        room = action["room"]
        reason = entry["reason"]
        if not reason.endswith((".", "!", "?")):
            reason += "."
        yield report_line(
            "Sent, not linked",
            by_element[action["element_id"]],
            room,
            "Craydl room %s was created, but its ID was not added here: %s "
            "Run Match Rooms again to link it." % (room["id"], reason),
        )
    for model in result["uncertain"]:
        yield report_line(
            "Send uncertain",
            model,
            detail="Craydl may have created this room. Run Match Rooms again before sending it again.",
        )
    for row in plan["matched"]:
        if row["name_differs"]:
            yield report_line(
                "Matched with a different name", row["model_room"], row["room"]
            )
    for row in plan["duplicate_ids"]:
        for model in row["model_rooms"]:
            yield report_line("Duplicate ID", model, row["room"])
    for model in plan["unknown_ids"]:
        yield report_line("Unknown ID", model, detail=model["stamp"])
    for row in plan["rows"]:
        if row["room"]["id"] not in chosen:
            detail = seed.TEXT[row["reason"]]
            if row["candidates"]:
                detail += " " + ", ".join(
                    room_label(model) for model in row["candidates"]
                )
            yield report_line("Not decided", room=row["room"], detail=detail)
    for move in plan["moves"]:
        if move["room"]["id"] not in moved_ids:
            detail = "from %s to %s" % (
                room_label(move["from"]),
                room_label(move["to"]),
            )
            yield report_line("Move offered", move["to"], move["room"], detail)
    for model in plan["unmatched_model"]:
        if model["element_id"] not in applied_targets:
            yield report_line(
                "Only in the model",
                model,
                detail="Add this room on the job's Rooms tab in Craydl, then run Match Rooms again.",
            )


def report(plan, actions, result, model_rooms, send_targets=()):
    lines = list(report_lines(plan, actions, result, model_rooms, send_targets))
    script.get_output().show()
    # Keep Revit text as Unicode all the way to pyRevit's output window.
    if lines:
        print(
            "Craydl Match Rooms report: Result | Model room | Number | Phase | Craydl room | Detail"
        )
        for line in lines:
            print(" | ".join(line))
    else:
        print(TITLE + ": " + seed.TEXT[plan["state"]])
    if plan["starters"]:
        print(
            "Starter rooms: %s (template leftovers; remove the ones you do not need)."
            % len(plan["starters"])
        )


def next_step(plan, result):
    moved_ids = {entry["action"]["room"]["id"] for entry in result["moved"]}
    waiting = len(result["created"])
    waiting += sum(
        entry["model_rooms"][0]["area_sf"] == 0
        for entry in result["linked"] + result["sent"]
    )
    waiting += sum(
        row["model_room"]["area_sf"] == 0 and row["room"]["id"] not in moved_ids
        for row in plan["matched"]
    )
    if waiting:
        return (
            "Next: place the %s rooms that are not placed yet with Revit's Room tool, "
            "picking each from the Room list on the Options Bar." % waiting
        )
    return "Every matched room is placed."


def main():
    doc = revit.doc
    try:
        host.require_project(doc)
        if host.editing_design_option(doc):
            raise ValueError(
                "Finish editing the design option before using Match Rooms."
            )
        bindings = host.binding_changes(host.project_parameters(doc))
        client = host.connected_client()
        if client is None:
            raise ValueError("Run Connect first.")
        job_guid = params.PARAMETERS[0]["guid"]
        job_id = host.read_stamp(doc.ProjectInformation, job_guid)
        if not params.is_job_id(job_id):
            raise ValueError("Run Link Job first: this model has no valid job link.")
        phases = host.phase_names(doc)
        if not phases:
            raise ValueError("This model has no phases.")
    except Exception as error:
        forms.alert("%s\nNothing was changed." % error, title=TITLE)
        return
    phase = forms.ask_for_one_item(
        phases,
        default=phases[-1],
        prompt="Choose the phase for new rooms.",
        title=TITLE,
    )
    if phase is None:
        forms.alert(
            "Cancelled before planning. Nothing was changed.",
            title=TITLE,
            warn_icon=False,
        )
        return
    try:
        reply = client.call_tool("job_lookup", {"job_id": job_id})
        job = reply.get("data") if isinstance(reply, dict) else None
        if not isinstance(job, dict) or job.get("id") != job_id:
            raise CraydlError("protocol", "Invalid linked-job reply.")
        rooms = client.read_all("job_rooms", {"job_id": job_id})
        can_send = CREATE_ROOM in client.list_tools()
        model_rooms = host.read_model_rooms(doc)
        plan = seed.plan_rooms(rooms, model_rooms, phase)
    except Exception as error:
        forms.alert(
            "Could not read the job or rooms: %s\nNothing was changed." % error,
            title=TITLE,
        )
        return
    if not (plan["rows"] or plan["moves"] or (can_send and plan["sendable"])):
        message = seed.TEXT.get(
            plan["state"], "No Craydl room is waiting for a decision. See the report."
        )
        forms.alert(message, title=TITLE, warn_icon=False)
        report(plan, [], empty_result(), model_rooms)
        return
    heading = "%s | %s" % (
        job.get("name") or "(unnamed job)",
        job.get("location") or "(no location provided)",
    )
    actions = host_rooms_ui.ask(plan, heading, phase, bindings, can_send)
    if not actions:
        message = "Cancelled." if actions is None else "Nothing was selected."
        forms.alert(message + " Nothing was changed.", title=TITLE, warn_icon=False)
        report(plan, [], empty_result(), model_rooms)
        return
    try:
        current_job_id = host.read_stamp(doc.ProjectInformation, job_guid)
    except Exception as error:
        forms.alert(
            "Could not re-read the job link: %s\nNothing was changed." % error,
            title=TITLE,
        )
        return
    if current_job_id != job_id:
        forms.alert("The job link changed. Run Match Rooms again.", title=TITLE)
        return
    problems = seed.check_actions(plan, actions)
    if problems:
        forms.alert("\n".join(problems + ["Nothing was changed."]), title=TITLE)
        return
    result = empty_result()
    send_targets = {a["element_id"] for a in actions if a["action"] == "send"}
    if send_targets:
        actions = [a for a in actions if a["action"] != "send"]
        links = send_rooms(client, job_id, plan, send_targets, result)
        edit_actions = actions + links
    else:
        edit_actions = actions
    try:
        result.update(host.apply_rooms(doc, phase, edit_actions, bindings))
    except Exception as error:
        result["skipped"] = [
            {"action": a, "reason": "Transaction failed: %s" % error}
            for a in edit_actions
        ]
        if not send_targets:
            forms.alert(
                "Revit could not apply the rooms: %s\nThe edit was not committed."
                % error,
                title=TITLE,
            )
            report(plan, actions, result, model_rooms)
            return
    classify_sent_links(result, send_targets)
    report(plan, actions, result, model_rooms, send_targets)
    skipped = sum(
        len(result[key]) for key in ("skipped", "not_sent", "unlinked", "uncertain")
    )
    counts = "Created: %s. Linked: %s. Moved: %s. Sent to Craydl: %s. Skipped: %s." % (
        len(result["created"]),
        len(result["linked"]),
        len(result["moved"]),
        len(result["sent"]),
        skipped,
    )
    message = [counts]
    if result["unlinked"] or result["uncertain"]:
        message.append(
            "Some rooms may already be in Craydl. Run Match Rooms again before sending them again."
        )
    message.extend([next_step(plan, result), "The model was not saved or synced."])
    forms.alert(
        "\n".join(message),
        title=TITLE,
        warn_icon=False,
    )


main()
