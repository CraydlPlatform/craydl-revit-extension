"""Pure snapshot validation and read-only model/template reports for IronPython."""

from __future__ import unicode_literals

import json

from craydl_bridge import params, seed

SCHEMA = "craydl.revit.snapshot/2"
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
STARTER_ROOM_NAMES = seed.STARTER_ROOM_NAMES
_UNUSABLE_NUMBERS = frozenset(["", "na", "none", "notatype", "tbd", "model"])

TEXT = {
    "not_set_up": "Craydl parameters are not fully bound; Link Job adds the missing fields.",
    "not_linked": "The model has no valid job ID; use Link Job to link it.",
    "no_placed_rooms": "No room has an area in the chosen phase. Place the rooms that are waiting, or run the check on the phase that holds the rooms.",
    "starter_rooms": "Starter rooms from the template remain with no area; place the ones you need and remove the leftovers.",
    "rooms_waiting_to_be_placed": "These rooms already have Craydl IDs but have no area; place them with Revit's Room tool or check their boundaries.",
    "rooms_not_placed": "These rooms have neither an area nor a Craydl ID and are not template starters; place or enclose the ones you need.",
    "rooms_without_id": "Placed rooms in the chosen phase have no Craydl ID; run Match Rooms to link each one.",
    "id_on_unplaced_room": "A Craydl ID sits on a room that is not placed while a placed room has the same name; run Match Rooms to move the ID.",
    "duplicate_room_id": "Room IDs are shared by multiple rooms; resolve the duplicate stamps before sharing data.",
    "duplicate_room_names": "Placed rooms share a name in the chosen phase; give them distinct names if they represent different rooms.",
    "nothing_in_new_phase": "No items or hosts were created in the chosen phase; check the phase choice and element phases.",
    "products_on_placeholder_type": "These products were loaded on their placeholder type, so they carry no model number; load the real type from the family's type catalog.",
    "products_named_without_number": "These products have a maker or link but no usable model number; add the manufacturer's model number where known.",
    "products_not_identified": "These products have no usable model number, maker or link; add the product details where known.",
    "custom_items": "These in-place families are not counted as products; review them as custom items.",
    "products_outside_rooms": "These products have no room reference; review their placement and the room boundaries.",
    "repeated_materials": "Material names are repeated at least a hundred times; review and consolidate redundant materials.",
    "template_linked": "The template carries a job ID; clear it before reusing the template.",
    "template_room_ids": "Template rooms carry Craydl IDs; clear the stamps before reusing the template.",
    "template_rooms": "The template contains rooms; remove project rooms before reusing it.",
    "template_project_fields": "The template has client or status fields filled in; clear project-specific values.",
    "template_products": "The template contains products; review and remove project-specific instances.",
}

STAGE_TEXT = {
    "survey": "This looks like a survey or as-built model; run the check on the phase that holds its rooms and items.",
    "not_linked": "Run Link Job to link the model and add any missing Craydl fields.",
    "rooms_to_match": "Use Match Rooms to link the placed rooms without a Craydl ID (%s).",
    "rooms_to_place": "Use Revit's Room tool to place the Craydl rooms waiting for an area (%s).",
    "no_rooms": "No rooms are placed or linked yet; draw rooms in Revit or use Match Rooms to bring them in from Craydl.",
    "ready": "The rooms are matched; review the findings below before sharing.",
}

LABELS = {
    "rooms_placed": "Rooms with an area in {phase}",
    "rooms_placed_other_phases": "Rooms with an area in other phases",
    "rooms_not_enclosed": "Located rooms without an area",
    "rooms_unplaced": "Rooms without a location",
    "rooms_with_id": "Rooms with a Craydl ID in any phase",
    "new_items": "Items created in {phase} and not demolished",
    "new_products": "Of those, products",
    "new_nested_parts": "Of those, parts nested in another family (not counted as products)",
    "new_custom_items": "Of those, in-place items (not counted as products)",
    "new_products_in_room": "Products with a room reference",
    "new_products_with_number": "Products with a usable model number",
    "new_products_with_link_only": "Products with a link but no usable model number",
    "new_products_unidentified": "Products with neither a link nor a usable model number",
    "materials_total": "Materials in the model",
    "materials_used_new": "Materials used in {phase}",
    "skipped_elements": "Elements that could not be read",
    "rooms": "Rooms",
    "products": "Products",
    "shared_parameters": "Shared parameters",
}
NO_FINDINGS = "Nothing needs attention."

# IronPython dicts do not preserve insertion order.
_MODEL_SUMMARY_ORDER = [
    "rooms_placed",
    "rooms_placed_other_phases",
    "rooms_not_enclosed",
    "rooms_unplaced",
    "rooms_with_id",
    "phases",
    "new_items",
    "new_products",
    "new_nested_parts",
    "new_custom_items",
    "new_products_in_room",
    "new_products_with_number",
    "new_products_with_link_only",
    "new_products_unidentified",
    "materials_total",
    "materials_used_new",
    "skipped_elements",
]
_TEMPLATE_SUMMARY_ORDER = [
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
            "element_id": "integer",
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
            "element_id": "integer",
            "nested": "bool",
            "in_place": "bool",
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


def is_nested_part(item):
    return item["nested"]


def is_custom_item(item):
    return (
        item["category"] in PRODUCT_CATEGORIES
        and not is_nested_part(item)
        and item["in_place"]
    )


def is_product(item):
    return (
        item["category"] in PRODUCT_CATEGORIES
        and not is_nested_part(item)
        and not item["in_place"]
    )


def usable_model(model):
    return seed.normalize(model) not in _UNUSABLE_NUMBERS


def is_placeholder_type(product):
    return seed.normalize(product["model"]) in ("na", "notatype") or (
        seed.normalize(product["type"]).startswith("notatype")
        and not usable_model(product["model"])
    )


def _finding(
    findings, code, level, count, examples=(), elements=(), preserve_order=False
):
    if count <= 0:
        return
    if preserve_order:
        distinct, seen = [], set()
        for example in examples:
            if example not in seen:
                distinct.append(example)
                seen.add(example)
    else:
        distinct = sorted(set(examples))
    findings.append(
        {
            "code": code,
            "level": level,
            "count": count,
            "text": TEXT[code],
            "examples": distinct[:10],
            "more": max(0, len(distinct) - 10),
            "element_ids": sorted(set(element["element_id"] for element in elements))[
                :50
            ],
        }
    )


def _repeated_materials(snapshot, findings):
    names = [
        row for row in snapshot["materials"]["repeated_names"] if row["count"] >= 100
    ]
    _finding(
        findings,
        "repeated_materials",
        "note",
        len(names),
        ("%s x%s" % (row["name"], row["count"]) for row in names),
        preserve_order=True,
    )


def _room_label(room):
    return (
        "%s (%s)" % (room["name"], room["number"]) if room["number"] else room["name"]
    )


def _room_name_key(room):
    return seed.normalize(room["name"])


def _groups(rows, key):
    result = {}
    for row in rows:
        result.setdefault(key(row), []).append(row)
    return result


def _duplicate_groups(rows, key):
    return [group for group in _groups(rows, key).values() if len(group) > 1]


def _room_findings(findings, rooms, placed, chosen, set_up):
    _finding(findings, "no_placed_rooms", "fix", int(not chosen))
    starters, waiting, other = [], [], []
    for room in rooms:
        if is_placed(room):
            continue
        if room["stamp"]:
            waiting.append(room)
        elif _room_name_key(room) in STARTER_ROOM_NAMES:
            starters.append(room)
        else:
            other.append(room)
    _finding(
        findings,
        "starter_rooms",
        "note",
        len(starters),
        (room["name"] for room in starters),
        starters,
    )
    for code, level, group in (
        ("rooms_waiting_to_be_placed", "note", waiting),
        ("rooms_not_placed", "note", other),
        (
            "rooms_without_id",
            "fix",
            [r for r in chosen if not r["stamp"]] if set_up else [],
        ),
    ):
        _finding(
            findings, code, level, len(group), (_room_label(r) for r in group), group
        )

    unstamped_placed = _groups((r for r in placed if not r["stamp"]), _room_name_key)
    pairs = []
    for room in waiting:
        twins = unstamped_placed.get(_room_name_key(room), ())
        if len(twins) == 1:
            pairs.append((room, twins[0]))
    _finding(
        findings,
        "id_on_unplaced_room",
        "fix",
        len(pairs),
        ("%s -> %s" % (_room_label(room), _room_label(twin)) for room, twin in pairs),
        (room for pair in pairs for room in pair),
    )

    by_stamp = _duplicate_groups((r for r in rooms if r["stamp"]), lambda r: r["stamp"])
    _finding(
        findings,
        "duplicate_room_id",
        "fix",
        len(by_stamp),
        elements=(room for group in by_stamp for room in group),
    )
    by_name = _duplicate_groups(chosen, _room_name_key)
    _finding(
        findings,
        "duplicate_room_names",
        "note",
        len(by_name),
        (
            "%s x%s" % (min(room["name"] for room in group), len(group))
            for group in by_name
        ),
        (room for group in by_name for room in group),
    )


def _family_type(item):
    return "%s: %s" % (item["family"], item["type"])


def _category_label(item):
    category = item["category"]
    return category[4:] if category.startswith("OST_") else category


def _counted_examples(rows, key):
    counts = {}
    for row in rows:
        name = key(row)
        counts[name] = counts.get(name, 0) + 1
    return ("%s x%s" % (name, count) for name, count in counts.items())


def _product_findings(findings, products, unnumbered, custom):
    placeholder, named, unidentified = [], [], []
    for product in unnumbered:
        if is_placeholder_type(product):
            placeholder.append(product)
        elif product["manufacturer"] or product["url"]:
            named.append(product)
        else:
            unidentified.append(product)
    for code, level, group, key in (
        (
            "products_on_placeholder_type",
            "fix",
            placeholder,
            lambda item: item["family"],
        ),
        ("products_named_without_number", "note", named, _family_type),
        ("products_not_identified", "note", unidentified, _category_label),
    ):
        _finding(
            findings, code, level, len(group), _counted_examples(group, key), group
        )
    _finding(
        findings,
        "custom_items",
        "note",
        len(custom),
        (item["family"] for item in custom),
        custom,
    )
    outside = [item for item in products if not item["room_unique_id"]]
    _finding(
        findings,
        "products_outside_rooms",
        "note",
        len(outside),
        _counted_examples(outside, _family_type),
        outside,
    )


def _stage(findings, created_phases, placed, rooms_with_id):
    counts = dict((row["code"], row["count"]) for row in findings)
    args = ()
    if "nothing_in_new_phase" in counts and created_phases:
        code = "survey"
    elif "not_linked" in counts or "not_set_up" in counts:
        code = "not_linked"
    elif "rooms_without_id" in counts:
        code, args = "rooms_to_match", (counts["rooms_without_id"],)
    elif "rooms_waiting_to_be_placed" in counts:
        code, args = "rooms_to_place", (counts["rooms_waiting_to_be_placed"],)
    elif not placed and not rooms_with_id:
        code = "no_rooms"
    else:
        code = "ready"
    return {"code": code, "text": STAGE_TEXT[code] % args}


def model_report(snapshot, new_phase):
    """Report a validated snapshot using the selected phase for new work."""
    rooms, items, hosts = snapshot["rooms"], snapshot["items"], snapshot["hosts"]
    placed = [room for room in rooms if is_placed(room)]
    chosen = [room for room in placed if room["phase"] == new_phase]
    new_items = [item for item in items if is_new(item, new_phase)]
    products = [item for item in new_items if is_product(item)]
    unnumbered = [item for item in products if not usable_model(item["model"])]
    link_only = sum(1 for item in unnumbered if item["url"])
    custom = [item for item in new_items if is_custom_item(item)]
    rooms_with_id = sum(1 for room in rooms if room["stamp"])
    summary = {
        "rooms_placed": len(chosen),
        "rooms_placed_other_phases": len(placed) - len(chosen),
        "rooms_not_enclosed": sum(1 for room in rooms if is_not_enclosed(room)),
        "rooms_unplaced": sum(1 for room in rooms if is_unplaced(room)),
        "rooms_with_id": rooms_with_id,
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
        "new_nested_parts": sum(1 for item in new_items if is_nested_part(item)),
        "new_custom_items": len(custom),
        "new_products_in_room": sum(1 for item in products if item["room_unique_id"]),
        "new_products_with_number": len(products) - len(unnumbered),
        "new_products_with_link_only": link_only,
        "new_products_unidentified": len(unnumbered) - link_only,
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
    _room_findings(findings, rooms, placed, chosen, set_up)
    created_phases = set(row["created_phase"] for row in items + hosts)
    _finding(
        findings, "nothing_in_new_phase", "fix", int(new_phase not in created_phases)
    )
    # A host without a readable phase is not evidence of work in another phase.
    created_phases.discard("")
    _product_findings(findings, products, unnumbered, custom)
    _repeated_materials(snapshot, findings)
    return {
        "mode": "model",
        "new_phase": new_phase,
        "stage": _stage(findings, created_phases, placed, rooms_with_id),
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


def summary_lines(report, title):
    """Return the heading, stage (model only), and ordered summary lines."""
    template = report["mode"] == "template"
    lines = ["Craydl Check %s: %s" % ("Template" if template else "Model", title)]
    phase_name = report.get("new_phase", "")
    if not template:
        lines.append("Stage: %s" % report["stage"]["text"])
    for key in _TEMPLATE_SUMMARY_ORDER if template else _MODEL_SUMMARY_ORDER:
        value = report["summary"][key]
        if key == "phases":
            for phase in value:
                lines.append(
                    "%s: items created %s, demolished %s; walls, floors, ceilings and roofs created %s, demolished %s"
                    % (
                        phase["name"],
                        phase["items_created"],
                        phase["items_demolished"],
                        phase["hosts_created"],
                        phase["hosts_demolished"],
                    )
                )
        else:
            lines.append("%s: %s" % (LABELS[key].replace("{phase}", phase_name), value))
    return lines


def finding_lines(finding):
    lines = [
        "%s | %s | %s" % (finding["level"].upper(), finding["count"], finding["text"])
    ]
    if finding["examples"]:
        examples = "   " + ", ".join(finding["examples"])
        if finding["more"]:
            examples += " and %s more" % finding["more"]
        lines.append(examples)
    return lines


def format_report(report, title):
    """Return printable lines without any host-specific selection links."""
    lines = summary_lines(report, title)
    for finding in report["findings"]:
        lines.extend(finding_lines(finding))
    if not report["findings"]:
        lines.append(NO_FINDINGS)
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
