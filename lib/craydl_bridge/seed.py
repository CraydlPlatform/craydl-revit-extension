"""Pure, repeatable room reconciliation. No host or network writes."""

from __future__ import unicode_literals


def normalize(name):
    return "".join(
        character for character in (name or "").lower() if character.isalnum()
    )


def plan_seed(craydl_rooms, model_rooms, phase):
    """Return one action per active non-general room, plus model-only rooms.

    Rows contain the Craydl record as ``room`` and zero, one or multiple
    matching model records as ``model_rooms``. Stamp identity wins over name
    matching, including stamps in phases other than the selected phase.
    """
    rooms = sorted(
        (r for r in craydl_rooms if r["status"] == "active" and not r["is_general"]),
        key=lambda r: (r["display_name"], r["id"]),
    )
    models = sorted(
        model_rooms, key=lambda r: (r["element_id"], r["phase"], r["name"], r["number"])
    )
    stamps, names = {}, {}
    for model in models:
        if model["stamp"]:
            stamps.setdefault(model["stamp"], []).append(model)
        elif model["phase"] == phase:
            names.setdefault(normalize(model["name"]), []).append(model)
    # Only identities without stamps compete for an existing unstamped room.
    needs = {}
    for room in rooms:
        if room["id"] not in stamps:
            name = normalize(room["display_name"])
            needs[name] = needs.get(name, 0) + 1
    rows, linked = [], set()
    for room in rooms:
        matches = stamps.get(room["id"], [])
        row = {"room": room, "model_rooms": matches}
        if matches:
            row["action"] = "present" if len(matches) == 1 else "duplicate_stamp"
            if len(matches) == 1:
                row["name_differs"] = normalize(matches[0]["name"]) != normalize(
                    room["display_name"]
                )
        else:
            name = normalize(room["display_name"])
            candidates = names.get(name, [])
            if len(candidates) == 1 and needs[name] == 1:
                row["action"] = "link"
                row["model_rooms"] = candidates
                linked.add(candidates[0]["element_id"])
            else:
                row["action"] = "create"
        rows.append(row)
    ids = set(r["id"] for r in rooms)
    return {
        "rows": rows,
        "unknown_stamps": [r for r in models if r["stamp"] and r["stamp"] not in ids],
        "unlinked": [
            r
            for r in models
            if not r["stamp"] and r["phase"] == phase and r["element_id"] not in linked
        ],
    }
