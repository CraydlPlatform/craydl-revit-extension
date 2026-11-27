"""Pure, repeatable room reconciliation. No host or network writes."""

from __future__ import unicode_literals


def normalize(name):
    return "".join(
        character for character in (name or "").lower() if character.isalnum()
    )


STARTER_ROOM_NAMES = frozenset(
    normalize(name)
    for name in ("Bed 1", "Great Room", "Garage", "Mech.", "Bath 1", "CL")
)

TEXT = {
    "same_name": "A model room has the same name, so Match Rooms starts with that link.",
    "sent_from_model": (
        "This Craydl room was sent from the model, so Match Rooms starts with a link "
        "to the model room with the same name, level and number."
    ),
    "several_same_name": "Several model rooms have this name, so choose which one to link.",
    "several_craydl_same_name": (
        "Several Craydl rooms share this name, so choose a different model room for each link."
    ),
    "no_model_room": "No placed rooms are left to link, so Match Rooms starts with a new unplaced room.",
    "unlinked_placed_rooms": (
        "Placed model rooms still have no link, so review them before creating a new room."
    ),
    "neither": (
        "Craydl has no rooms for this job and the model has no rooms of its own. "
        "Add the job's rooms in Craydl first, then run Match Rooms again."
    ),
    "model_only": (
        "Craydl has no rooms for this job. Add the model's rooms on the job's Rooms tab "
        "in Craydl, then run Match Rooms again to link them."
    ),
    "matched": "Every Craydl room is matched to a model room.",
}


def is_placed(model_room):
    return model_room["area_sf"] > 0


def is_starter(model_room):
    return (
        model_room["stamp"] == ""
        and not is_placed(model_room)
        and normalize(model_room["name"]) in STARTER_ROOM_NAMES
    )


def _text(record, key):
    return (record.get(key) or "").strip()


def _sent_key(room):
    return normalize(_text(room, "name")), _text(room, "level"), _text(room, "number")


def _target_needs(groups):
    needs = {}
    for models in groups:
        for model in models:
            element_id = model["element_id"]
            needs[element_id] = needs.get(element_id, 0) + 1
    return needs


def _sent_defaults(rows, sent_by_room):
    needs = _target_needs(sent_by_room.values())
    linked = set()
    for row in rows:
        sent = sent_by_room.get(row["room"]["id"], ())
        if len(sent) > 1:
            row["reason"] = "several_same_name"
        elif sent:
            element_id = sent[0]["element_id"]
            if needs[element_id] > 1:
                row["reason"] = "several_craydl_same_name"
            else:
                row["default"] = {"action": "link", "element_id": element_id}
                row["reason"] = "sent_from_model"
                linked.add(element_id)
    return linked


def _name_defaults(rows, reserved):
    # Keep the full candidate lists for manual selection; only the defaults
    # ignore targets already taken by a sent match.
    choices = [
        (row, [m for m in row["candidates"] if m["element_id"] not in reserved])
        for row in rows
    ]
    # Count needs by target: model-origin rows can match two different names.
    needs = _target_needs(candidates for _, candidates in choices)
    linked = set()
    for row, candidates in choices:
        if not candidates:
            continue
        if any(needs[model["element_id"]] > 1 for model in candidates):
            row["reason"] = "several_craydl_same_name"
            continue
        # If any candidate is placed, unplaced candidates cannot win the tie.
        best = [model for model in candidates if is_placed(model)] or candidates
        if len(best) == 1:
            element_id = best[0]["element_id"]
            row["default"] = {"action": "link", "element_id": element_id}
            row["reason"] = "same_name"
            linked.add(element_id)
        else:
            row["reason"] = "several_same_name"
    return linked


def _sendable(rooms, rows, unmatched_model):
    considered_names = {
        normalize(_text(room, key))
        for room in rooms
        for key in ("name", "display_name")
    }
    candidate_ids = {m["element_id"] for row in rows for m in row["candidates"]}
    return [
        model
        for model in unmatched_model
        if model["element_id"] not in candidate_ids
        and _text(model, "name")
        and normalize(model["name"]) not in considered_names
    ]


def _move_offers(matched, open_placed):
    by_name = {}
    for model in open_placed:
        by_name.setdefault(normalize(model["name"]), []).append(model)
    moves = []
    for entry in matched:
        room, source = entry["room"], entry["model_room"]
        if is_placed(source):
            continue
        names = {normalize(source["name"]), normalize(room["display_name"])}
        targets = [model for name in names for model in by_name.get(name, ())]
        if len(targets) == 1:
            moves.append({"room": room, "from": source, "to": targets[0]})
    return moves


def _candidate_order(model, phase):
    return not is_placed(model), model["phase"] != phase, model["element_id"]


def _row_candidates(room, by_name, phase):
    label = normalize(room["display_name"])
    candidates = list(by_name.get(label, ()))
    if _text(room, "origin") != "model":
        return candidates, []

    identity = _sent_key(room)
    name = identity[0]
    if name != label:
        candidates.extend(by_name.get(name, ()))
        candidates.sort(key=lambda model: _candidate_order(model, phase))
    sent, other = [], []
    for model in candidates:
        (sent if _sent_key(model) == identity else other).append(model)
    return sent + other, sent


def plan_rooms(craydl_rooms, model_rooms, phase):
    """Plan links, creations, stamp moves and send offers without writing either side."""
    rooms = sorted(
        (r for r in craydl_rooms if r["status"] == "active" and not r["is_general"]),
        key=lambda r: (r["display_name"], r["id"]),
    )
    considered_ids = {r["id"] for r in rooms}
    stamps, unknown_ids, starters, free = {}, [], [], []
    for model in sorted(model_rooms, key=lambda r: r["element_id"]):
        stamp = model["stamp"]
        if stamp and stamp in considered_ids:
            stamps.setdefault(stamp, []).append(model)
        elif stamp:
            unknown_ids.append(model)
        elif is_starter(model):
            starters.append(model)
        else:
            free.append(model)

    candidates_by_name = {}
    for model in sorted(free, key=lambda r: _candidate_order(r, phase)):
        candidates_by_name.setdefault(normalize(model["name"]), []).append(model)

    matched, duplicate_ids, rows = [], [], []
    sent_by_room = {}
    for room in rooms:
        stamped = stamps.get(room["id"], [])
        name = normalize(room["display_name"])
        if len(stamped) == 1:
            matched.append(
                {
                    "room": room,
                    "model_room": stamped[0],
                    "name_differs": normalize(stamped[0]["name"]) != name,
                }
            )
        elif stamped:
            duplicate_ids.append({"room": room, "model_rooms": stamped})
        else:
            candidates, sent = _row_candidates(room, candidates_by_name, phase)
            rows.append({"room": room, "candidates": candidates, "default": None})
            if sent:
                sent_by_room[room["id"]] = sent

    sent_links = _sent_defaults(rows, sent_by_room)
    name_rows = [row for row in rows if row["room"]["id"] not in sent_by_room]
    default_links = sent_links | _name_defaults(name_rows, sent_links)
    unmatched_model = [
        model for model in free if model["element_id"] not in default_links
    ]
    open_placed = [model for model in unmatched_model if is_placed(model)]
    for row in rows:
        if "reason" not in row:
            if open_placed:
                row["reason"] = "unlinked_placed_rooms"
            else:
                row["default"] = {"action": "create"}
                row["reason"] = "no_model_room"

    moves = _move_offers(matched, open_placed)
    if not rooms:
        state = "model_only" if free else "neither"
    elif not (rows or moves or duplicate_ids or unmatched_model):
        state = "matched"
    else:
        state = "open"
    return {
        "phase": phase,
        "matched": matched,
        "duplicate_ids": duplicate_ids,
        "unknown_ids": unknown_ids,
        "starters": starters,
        "rows": rows,
        "moves": moves,
        "unmatched_model": unmatched_model,
        "sendable": _sendable(rooms, rows, unmatched_model),
        "state": state,
    }


def default_actions(plan):
    """Copy default choices in row order; moves and sends are always opt-in."""
    actions = []
    for row in plan["rows"]:
        if row["default"] is not None:
            action = dict(row["default"], room=row["room"])
            if action["action"] == "link":
                action["rename"] = False
            actions.append(action)
    return actions


def check_actions(plan, actions):
    """Check a batch against the plan and return modeler-facing problems."""
    if not isinstance(actions, (list, tuple)):
        return ["Choose the room edits again in Match Rooms before applying them."]

    row_names = {row["room"]["id"]: row["room"]["display_name"] for row in plan["rows"]}
    # Free rooms include all sendable rooms, so their native ID types are covered too.
    free_ids = {model["element_id"] for model in plan["unmatched_model"]}
    for row in plan["rows"]:
        default = row["default"]
        if default and default["action"] == "link":
            free_ids.add(default["element_id"])
    moves = {
        (m["room"]["id"], m["from"]["element_id"], m["to"]["element_id"])
        for m in plan["moves"]
    }
    # Revit supplies boxed Int64 IDs under IronPython, not Python int/long.
    # Trust ID types from the plan's model records plus Python integers, not
    # arbitrary values that happen to compare equal (such as True or 1.0).
    sendable = {model["element_id"]: model for model in plan["sendable"]}
    id_types = {int, type(1 << 64)}
    id_types.update(type(element_id) for element_id in free_ids)
    for _, source, target in moves:
        id_types.update((type(source), type(target)))

    problems, seen_rooms, seen_targets = [], set(), set()
    send_targets, sent_keys = set(), set()
    for action in actions:
        kind = action.get("action") if isinstance(action, dict) else None
        if type(kind) not in (str, type("")) or kind not in (
            "link",
            "create",
            "move",
            "send",
        ):
            problems.append(
                "Choose Link, Create or Move for each room edit, or skip it."
            )
            continue
        if kind == "send":
            target = action.get("element_id")
            if (
                "room" in action
                or type(target) not in id_types
                or target not in sendable
            ):
                problems.append("Choose a model room from the list of rooms to send.")
                continue
            key = _sent_key(sendable[target])
            if target in send_targets:
                problems.append("Send each model room only once.")
            elif key in sent_keys:
                problems.append(
                    "Send only one room with the same name, level and number."
                )
            send_targets.add(target)
            sent_keys.add(key)
            continue
        room = action.get("room")
        if not isinstance(room, dict) or type(room.get("id")) not in (str, type("")):
            problems.append(
                "A choice is missing its Craydl room, so select the room again."
            )
            continue
        room_id = room["id"]
        target = None
        if kind == "move":
            source, target = action.get("from_element_id"), action.get("to_element_id")
            if (
                type(source) not in id_types
                or type(target) not in id_types
                or (room_id, source, target) not in moves
            ):
                problems.append(
                    "Choose one of the ID moves offered in Match Rooms or skip the move."
                )
                continue
        elif room_id not in row_names:
            problems.append(
                "Link or create only the Craydl rooms listed for a decision."
            )
            continue
        elif kind == "link":
            target = action.get("element_id")
            if type(target) not in id_types or target not in free_ids:
                problems.append(
                    "Choose an unstamped model room from the list or skip the link."
                )
                continue
            if not isinstance(action.get("rename"), bool):
                problems.append("Tick or clear the rename box before linking a room.")
                continue
        if kind == "create" or (kind == "link" and action["rename"]):
            name = room.get("display_name")
            if type(name) not in (str, type("")) or name != row_names[room_id]:
                problems.append(
                    "Use the Craydl room name shown in Match Rooms or skip the edit."
                )
                continue
        if room_id in seen_rooms:
            problems.append("Keep just one edit for each Craydl room.")
        seen_rooms.add(room_id)
        if target is not None:
            if target in seen_targets:
                problems.append("Choose a different model room for each link or move.")
            seen_targets.add(target)
    for _ in send_targets & seen_targets:
        problems.append("Send, link or move a model room only once.")
    return sorted(problems)
