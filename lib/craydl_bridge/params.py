"""Permanent shared-parameter identities and a host-independent binding plan."""

from __future__ import unicode_literals


PARAMETERS = [
    {
        "name": name,
        "guid": guid,
        "categories": set(categories),
        "data_type": "Text",
        "instance": True,
        "group": "IdentityData",
        "user_modifiable": True,
    }
    for name, guid, categories in [
        (
            "Craydl_JobID",
            "eff68b15-d648-4b7c-a0f4-b53b13eeb27f",
            ["OST_ProjectInformation"],
        ),
        ("Craydl_RoomID", "d205d5ea-9764-47d0-93fe-42bba38a38e7", ["OST_Rooms"]),
        ("Craydl_SelectionID", "978539d5-a966-4323-801a-018e6c11c1d9", []),
        ("Craydl_ProductID", "cbcab026-79bc-4398-9db4-db6bf3a4f722", []),
    ]
]


def binding_plan(existing):
    """Return active bindings only; categories on add rows are the missing set."""
    existing = list(existing)
    plan = []
    for parameter in PARAMETERS:
        if not parameter["categories"]:
            continue
        row = dict(parameter)
        row["categories"] = set(parameter["categories"])
        conflicts = [
            item
            for item in existing
            if item["name"] == parameter["name"] and item["guid"] != parameter["guid"]
        ]
        matches = [item for item in existing if item["guid"] == parameter["guid"]]
        if conflicts:
            row["action"] = "name_conflict"
        elif not matches:
            row["action"] = "bind"
        else:
            row["categories"] -= matches[0]["categories"]
            row["action"] = "add_categories" if row["categories"] else "ok"
        plan.append(row)
    return plan


def is_job_id(text):
    """Accept only a canonical lowercase, hyphenated UUID, with no trimming."""
    if not isinstance(text, (str, type(""))) or len(text) != 36:
        return False
    return all(
        character == "-"
        if index in (8, 13, 18, 23)
        else character in "0123456789abcdef"
        for index, character in enumerate(text)
    )
