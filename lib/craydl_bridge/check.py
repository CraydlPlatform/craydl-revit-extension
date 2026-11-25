"""Pure snapshot validation and read-only model/template reports for IronPython."""

from __future__ import unicode_literals

import json

from craydl_bridge import params, seed

SCHEMA = "craydl.revit.snapshot/1"
PRODUCT_CATEGORIES = frozenset(
    [
        "OST_PlumbingFixtures",
        "OST_LightingFixtures",
        "OST_LightingDevices",
        "OST_Casework",
        "OST_SpecialityEquipment",
        "OST_Furniture",
        "OST_FurnitureSystems",
        "OST_ElectricalFixtures",
        "OST_ElectricalEquipment",
        "OST_MechanicalEquipment",
        "OST_Doors",
        "OST_Windows",
        "OST_GenericModel",
    ]
)
STARTER_ROOM_NAMES = frozenset(
    seed.normalize(name)
    for name in [
        "Bed 1",
        "Great Room",
        "Garage",
        "Mech.",
        "Bath 1",
        "CL",
    ]
)
_UNUSABLE_NUMBERS = frozenset(["", "na", "none", "notatype", "tbd", "model"])

TEXT = {
    "not_set_up": "Craydl parameters are not fully bound; run Set Up Model.",
    "not_linked": "The model has no valid job ID; use Link Job to link it.",
    "no_placed_rooms": "No rooms are placed in the chosen phase; place rooms in that phase before seeding them.",
    "starter_rooms": "Unplaced starter rooms remain; place the rooms you need and remove the leftovers.",
    "rooms_not_placed": "Other rooms are not placed; place or remove them as appropriate.",
    "rooms_without_id": "Placed rooms in the chosen phase have no Craydl ID; run Seed Rooms to link them.",
    "duplicate_room_id": "Room IDs are shared by multiple rooms; resolve the duplicate stamps before sharing data.",
    "duplicate_room_names": "Placed rooms share a name within a phase; give them distinct names.",
    "nothing_in_new_phase": "No items or hosts were created in the chosen phase; check the phase choice and element phases.",
    "products_outside_rooms": "New products have no room reference; check their placement and room boundaries.",
    "products_without_number": "New products have no usable model number; add product numbers where known.",
    "repeated_materials": "Material names are repeated at least a hundred times; review and consolidate redundant materials.",
    "template_linked": "The template carries a job ID; clear it before reusing the template.",
    "template_room_ids": "Template rooms carry Craydl IDs; clear the stamps before reusing the template.",
    "template_rooms": "The template contains rooms; remove project rooms before reusing it.",
    "template_project_fields": "The template has client or status fields filled in; clear project-specific values.",
    "template_products": "The template contains products; review and remove project-specific instances.",
}

_MODEL_LABELS = [
    "rooms_placed",
    "rooms_placed_other_phases",
    "rooms_not_enclosed",
    "rooms_unplaced",
    "phases",
    "new_items",
    "new_products",
    "new_products_in_room",
    "new_products_with_number",
    "new_products_with_link_only",
    "new_products_unidentified",
    "materials_total",
    "materials_used_new",
    "skipped_elements",
]
_TEMPLATE_LABELS = [
    "rooms",
    "products",
    "materials_total",
    "shared_parameters",
    "skipped_elements",
]

# A small data description keeps all required fields visible and all malformed
# containers on the same non-raising path; it does not infer missing values.
_SHAPE = {
    "schema": "text",
    "extension_version": "text",
    "taken_at": "text",
    "model": {
        "title": "text",
        "is_cloud": "bool",
        "is_workshared": "bool",
        "is_template": "bool",
        "cloud_project_guid": "text",
        "cloud_model_guid": "text",
        "job_id": "text",
        "set_up": "bool",
        "project_info": {
            "name": "text",
            "number": "text",
            "client_name": "text",
            "status": "text",
            "address": "text",
        },
    },
    "phases": ["text"],
    "rooms": [
        {
            "unique_id": "text",
            "name": "text",
            "number": "text",
            "level": "text",
            "phase": "text",
            "located": "bool",
            "area_sf": "number",
            "stamp": "text",
        }
    ],
    "items": [
        {
            "unique_id": "text",
            "category": "text",
            "family": "text",
            "type": "text",
            "manufacturer": "text",
            "model": "text",
            "url": "text",
            "description": "text",
            "created_phase": "text",
            "demolished_phase": "text",
            "room_unique_id": "text",
        }
    ],
    "hosts": [
        {
            "category": "text",
            "type": "text",
            "created_phase": "text",
            "demolished_phase": "text",
            "count": "integer",
            "area_sf": "number",
        }
    ],
    "materials": {
        "total": "integer",
        "used": [
            {
                "name": "text",
                "material_class": "text",
                "manufacturer": "text",
                "model": "text",
                "uses": "uses",
            }
        ],
        "repeated_names": [{"name": "text", "count": "integer"}],
    },
    "counts": {
        "shared_parameters": "integer",
        "links": "integer",
        "point_clouds": "integer",
        "sheets": "integer",
        "skipped_elements": "integer",
    },
}


def _is_text(value):
    return isinstance(value, (str, type("")))


def _is_integer(value):
    # type(1 << 64) includes long under Python 2 without a Python-3-only name.
    return isinstance(value, (int, type(1 << 64))) and not isinstance(value, bool)


def _validate(value, shape, path, problems):
    if isinstance(shape, dict):
        if not isinstance(value, dict):
            problems.append("%s must be a dict" % path)
            return
        for key in sorted(shape):
            child_path = "%s.%s" % (path, key)
            if key not in value:
                problems.append("%s is missing" % child_path)
            else:
                _validate(value[key], shape[key], child_path, problems)
    elif isinstance(shape, list):
        if not isinstance(value, list):
            problems.append("%s must be a list" % path)
            return
        for index, child in enumerate(value):
            _validate(child, shape[0], "%s[%s]" % (path, index), problems)
    elif shape == "uses":
        if not isinstance(value, dict):
            problems.append("%s must map phase names to integers" % path)
            return
        # Do not sort malformed mixed-type keys (not comparable in Python 3).
        if any(not _is_text(key) for key in value):
            problems.append("%s phase names must be text" % path)
        for key in sorted(key for key in value if _is_text(key)):
            _validate(value[key], "integer", "%s.%s" % (path, key), problems)
    else:
        valid = False
        if shape == "text":
            valid = _is_text(value)
        elif shape == "bool":
            valid = isinstance(value, bool)
        elif shape == "integer":
            valid = _is_integer(value)
        elif shape == "number":
            valid = _is_integer(value) or isinstance(value, float)
        if not valid:
            problems.append("%s must be %s" % (path, shape))


def validate(snapshot):
    """Return deterministic, path-qualified shape errors, never editing input."""
    problems = []
    _validate(snapshot, _SHAPE, "snapshot", problems)
    if isinstance(snapshot, dict) and snapshot.get("schema") != SCHEMA:
        problems.append("snapshot.schema must equal %s" % SCHEMA)
    return problems


def is_placed(room):
    return room["area_sf"] > 0


def is_not_enclosed(room):
    return room["located"] and room["area_sf"] == 0


def is_unplaced(room):
    return not room["located"]


def is_new(item, phase):
    return item["created_phase"] == phase and item["demolished_phase"] == ""


def is_product(item):
    return item["category"] in PRODUCT_CATEGORIES


def usable_model(model):
    return seed.normalize(model) not in _UNUSABLE_NUMBERS


def _finding(findings, code, level, count, examples=(), preserve_order=False):
    if count > 0:
        examples = list(examples) if preserve_order else sorted(set(examples))
        findings.append(
            {
                "code": code,
                "level": level,
                "count": count,
                "text": TEXT[code],
                "examples": examples[:10],
            }
        )


def _repeated_materials(snapshot, findings):
    names = [
        row for row in snapshot["materials"]["repeated_names"] if row["count"] >= 100
    ]
    # The snapshot already orders these by count descending, then name.
    examples = []
    for row in names:
        example = "%s x%s" % (row["name"], row["count"])
        if example not in examples:
            examples.append(example)
    _finding(findings, "repeated_materials", "note", len(names), examples, True)


def _room_label(room):
    return (
        "%s (%s)" % (room["name"], room["number"]) if room["number"] else room["name"]
    )


def model_report(snapshot, new_phase):
    """Report a validated snapshot using the selected phase for new work."""
    rooms, items, hosts = snapshot["rooms"], snapshot["items"], snapshot["hosts"]
    placed = [room for room in rooms if is_placed(room)]
    chosen = [room for room in placed if room["phase"] == new_phase]
    new_items = [item for item in items if is_new(item, new_phase)]
    products = [item for item in new_items if is_product(item)]
    numbered = [item for item in products if usable_model(item["model"])]
    link_only = [
        item for item in products if not usable_model(item["model"]) and item["url"]
    ]
    summary = {
        "rooms_placed": len(chosen),
        "rooms_placed_other_phases": len(placed) - len(chosen),
        "rooms_not_enclosed": sum(1 for room in rooms if is_not_enclosed(room)),
        "rooms_unplaced": sum(1 for room in rooms if is_unplaced(room)),
        "phases": [
            {
                "name": phase,
                "items_created": sum(
                    1 for item in items if item["created_phase"] == phase
                ),
                "items_demolished": sum(
                    1 for item in items if item["demolished_phase"] == phase
                ),
                "hosts_created": sum(
                    host["count"] for host in hosts if host["created_phase"] == phase
                ),
                "hosts_demolished": sum(
                    host["count"] for host in hosts if host["demolished_phase"] == phase
                ),
            }
            for phase in snapshot["phases"]
        ],
        "new_items": len(new_items),
        "new_products": len(products),
        "new_products_in_room": sum(1 for item in products if item["room_unique_id"]),
        "new_products_with_number": len(numbered),
        "new_products_with_link_only": len(link_only),
        "new_products_unidentified": len(products) - len(numbered) - len(link_only),
        "materials_total": snapshot["materials"]["total"],
        "materials_used_new": sum(
            1
            for material in snapshot["materials"]["used"]
            if new_phase in material["uses"]
        ),
        "skipped_elements": snapshot["counts"]["skipped_elements"],
    }
    findings = []
    set_up = snapshot["model"]["set_up"]
    _finding(findings, "not_set_up", "fix", int(not set_up))
    _finding(
        findings,
        "not_linked",
        "fix",
        int(not params.is_job_id(snapshot["model"]["job_id"])),
    )
    _finding(findings, "no_placed_rooms", "fix", int(not chosen))
    starters, other_unplaced = [], []
    for room in rooms:
        if not is_placed(room):
            if not room["stamp"] and seed.normalize(room["name"]) in STARTER_ROOM_NAMES:
                starters.append(room)
            else:
                other_unplaced.append(room)
    _finding(
        findings, "starter_rooms", "note", len(starters), [r["name"] for r in starters]
    )
    _finding(
        findings,
        "rooms_not_placed",
        "note",
        len(other_unplaced),
        [_room_label(r) for r in other_unplaced],
    )
    _finding(
        findings,
        "rooms_without_id",
        "fix",
        sum(1 for r in chosen if not r["stamp"]) if set_up else 0,
    )
    stamps, names = {}, {}
    for room in rooms:
        if room["stamp"]:
            stamps[room["stamp"]] = stamps.get(room["stamp"], 0) + 1
        if is_placed(room):
            key = (room["phase"], seed.normalize(room["name"]))
            names.setdefault(key, []).append(room["name"])
    _finding(
        findings,
        "duplicate_room_id",
        "fix",
        sum(1 for count in stamps.values() if count > 1),
    )
    groups = [group for group in names.values() if len(group) > 1]
    _finding(
        findings,
        "duplicate_room_names",
        "note",
        len(groups),
        ["%s x%s" % (min(group), len(group)) for group in groups],
    )
    _finding(
        findings,
        "nothing_in_new_phase",
        "fix",
        int(
            not any(element["created_phase"] == new_phase for element in items + hosts)
        ),
    )
    outside = (
        [item for item in products if not item["room_unique_id"]] if placed else []
    )
    categories = {}
    for item in outside:
        category = item["category"]
        categories[category] = categories.get(category, 0) + 1
    _finding(
        findings,
        "products_outside_rooms",
        "fix",
        len(outside),
        ["%s x%s" % (c, n) for c, n in categories.items()],
    )
    _finding(findings, "products_without_number", "note", len(products) - len(numbered))
    _repeated_materials(snapshot, findings)
    return {
        "mode": "model",
        "new_phase": new_phase,
        "summary": summary,
        "findings": findings,
    }


def template_report(snapshot):
    """Report template clutter regardless of the phase or placement of objects."""
    rooms = snapshot["rooms"]
    products = [item for item in snapshot["items"] if is_product(item)]
    summary = {
        "rooms": len(rooms),
        "products": len(products),
        "materials_total": snapshot["materials"]["total"],
        "shared_parameters": snapshot["counts"]["shared_parameters"],
        "skipped_elements": snapshot["counts"]["skipped_elements"],
    }
    findings = []
    _finding(findings, "not_set_up", "fix", int(not snapshot["model"]["set_up"]))
    _finding(findings, "template_linked", "fix", int(snapshot["model"]["job_id"] != ""))
    _finding(
        findings, "template_room_ids", "fix", sum(1 for room in rooms if room["stamp"])
    )
    _finding(
        findings, "template_rooms", "fix", len(rooms), [room["name"] for room in rooms]
    )
    fields = [
        "%s: %s" % (key, snapshot["model"]["project_info"][key])
        for key in ("client_name", "status")
        if snapshot["model"]["project_info"][key]
    ]
    _finding(findings, "template_project_fields", "note", len(fields), fields)
    _finding(findings, "template_products", "note", len(products))
    _repeated_materials(snapshot, findings)
    return {"mode": "template", "summary": summary, "findings": findings}


def format_report(report, title):
    """Return ordered printable lines, independent of dict iteration order."""
    template = report["mode"] == "template"
    lines = ["Craydl Check %s: %s" % ("Template" if template else "Model", title)]
    for label in _TEMPLATE_LABELS if template else _MODEL_LABELS:
        value = report["summary"][label]
        if label == "phases":
            for phase in value:
                lines.append(
                    "phase %s: items created %s, demolished %s; hosts created %s, demolished %s"
                    % (
                        phase["name"],
                        phase["items_created"],
                        phase["items_demolished"],
                        phase["hosts_created"],
                        phase["hosts_demolished"],
                    )
                )
        else:
            lines.append("%s: %s" % (label, value))
    for finding in report["findings"]:
        lines.append(
            "%s | %s | %s | %s"
            % (
                finding["level"].upper(),
                finding["code"],
                finding["count"],
                finding["text"],
            )
        )
        if finding["examples"]:
            lines.append("   e.g. " + ", ".join(finding["examples"]))
    if not report["findings"]:
        lines.append("Nothing needs attention.")
    return lines


def to_json(snapshot):
    return json.dumps(snapshot, sort_keys=True, indent=1, separators=(",", ": "))


def file_name(snapshot):
    parts = []
    for character in snapshot["model"]["title"]:
        if (
            character
            in "abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789"
        ):
            parts.append(character)
        elif not parts or parts[-1] != "-":
            parts.append("-")
    slug = "".join(parts)[:60].strip("-") or "model"
    stamp = "".join(c for c in snapshot["taken_at"] if c in "0123456789")
    return "craydl-snapshot-%s-%s.json" % (slug, stamp)
