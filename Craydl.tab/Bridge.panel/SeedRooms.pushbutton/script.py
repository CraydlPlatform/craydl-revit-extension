"""Preview, link and seed unplaced rooms without saving or syncing."""

from __future__ import unicode_literals

from pyrevit import forms, revit, script

from craydl_bridge import host, params, seed
from craydl_bridge.client import CraydlError

TITLE = "Craydl Seed Rooms"


class SeedChoice(forms.TemplateListItem):
    @property
    def name(self):
        row = self.item
        if row["action"] == "create":
            return "Create %s" % row["room"]["display_name"]
        model = row["model_rooms"][0]
        return "Link existing room %s %s to %s" % (
            model["number"],
            model["name"],
            row["room"]["display_name"],
        )


def counts(plan):
    rows = plan["rows"]
    return (
        "Present: %s\nPresent with a different name: %s\nDuplicate stamp: %s\n"
        "Unknown stamps: %s\nUnlinked: %s"
    ) % (
        sum(r["action"] == "present" for r in rows),
        sum(r.get("name_differs", False) for r in rows),
        sum(r["action"] == "duplicate_stamp" for r in rows),
        len(plan["unknown_stamps"]),
        len(plan["unlinked"]),
    )


def report(plan, result):
    output = script.get_output()
    lines = []
    for key, label in (("created", "Created"), ("linked", "Linked")):
        for row in result[key]:
            for room in row["model_rooms"]:
                lines.append(
                    [
                        label,
                        room["name"],
                        room["number"],
                        room["phase"],
                        row["room"]["display_name"],
                    ]
                )
    for item in result["skipped"]:
        row = item["row"]
        rooms = row["model_rooms"] or [
            {"name": row["room"]["display_name"], "number": "", "phase": ""}
        ]
        for room in rooms:
            lines.append(
                ["Skipped", room["name"], room["number"], room["phase"], item["reason"]]
            )
    for row in plan["rows"]:
        if row["action"] == "duplicate_stamp" or row.get("name_differs"):
            label = (
                "Duplicate stamp"
                if row["action"] == "duplicate_stamp"
                else "Present with a different name"
            )
            for room in row["model_rooms"]:
                lines.append(
                    [
                        label,
                        room["name"],
                        room["number"],
                        room["phase"],
                        "Craydl: %s" % row["room"]["display_name"],
                    ]
                )
    for key, label in (("unknown_stamps", "Unknown stamp"), ("unlinked", "Unlinked")):
        for room in plan[key]:
            lines.append(
                [label, room["name"], room["number"], room["phase"], room["stamp"]]
            )
    # Send Unicode values directly to pyRevit, never through Python 2 str().
    if lines:
        output.show()
        print("Craydl Seed Rooms report: Result | Room name | Number | Phase | Detail")
        for line in lines:
            print(" | ".join(line))
    else:
        print("Craydl Seed Rooms: no rows need a person.")


def main():
    doc = revit.doc
    try:
        host.require_project(doc)
        if host.editing_design_option(doc):
            raise ValueError(
                "Finish editing the design option before using Seed Rooms."
            )
        missing = [
            r["name"]
            for r in params.binding_plan(host.project_parameters(doc))
            if r["action"] != "ok"
        ]
        if missing:
            raise ValueError(
                "Run Set Up Model first: %s is missing or has a binding conflict."
                % ", ".join(missing)
            )
        client = host.connected_client()
        if client is None:
            raise ValueError("Run Connect first.")
        job_id = host.read_stamp(doc.ProjectInformation, params.PARAMETERS[0]["guid"])
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
        prompt="Choose the phase for new rooms and name matching.",
        title=TITLE,
    )
    if phase is None:
        forms.alert("Cancelled before planning. Nothing was changed.", title=TITLE)
        return
    try:
        reply = client.call_tool("job_lookup", {"job_id": job_id})
        job = reply.get("data") if isinstance(reply, dict) else None
        if not isinstance(job, dict) or job.get("id") != job_id:
            raise CraydlError("protocol", "Invalid linked-job reply.")
        rooms = client.read_all("job_rooms", {"job_id": job_id})
        plan = seed.plan_seed(rooms, host.read_model_rooms(doc), phase)
    except Exception as error:
        forms.alert(
            "Could not read the job or rooms: %s\nNothing was changed." % error,
            title=TITLE,
        )
        return
    heading = "%s | %s" % (
        job.get("name") or "(unnamed job)",
        job.get("location") or "(no location provided)",
    )
    forms.alert(heading + "\nPhase: " + phase + "\n\n" + counts(plan), title=TITLE)
    pending = [r for r in plan["rows"] if r["action"] in ("create", "link")]
    result = {"created": [], "linked": [], "skipped": []}
    if not pending:
        forms.alert(
            "No rooms to create or link. Nothing was changed. See the report for rows needing a person.",
            title=TITLE,
        )
        report(plan, result)
        return
    choices = forms.SelectFromList.show(
        [SeedChoice(row, checked=True) for row in pending],
        title=heading + " - " + phase,
        multiselect=True,
        return_all=True,
        button_name="Apply selected rooms",
    )
    selected = [choice.item for choice in (choices or []) if choice.state]
    if not selected:
        forms.alert(
            "No rooms selected, or cancelled. Nothing was changed. See the report for rows needing a person.",
            title=TITLE,
        )
        report(plan, result)
        return
    try:
        if (
            host.read_stamp(doc.ProjectInformation, params.PARAMETERS[0]["guid"])
            != job_id
        ):
            raise ValueError("The job link changed. Run Seed Rooms again.")
        result = host.apply_seed(doc, phase, selected)
    except Exception as error:
        forms.alert(
            "Revit could not apply the rooms: %s\nThe seed transaction was not committed."
            % error,
            title=TITLE,
        )
        report(
            plan,
            {
                "created": [],
                "linked": [],
                "skipped": [
                    {"row": r, "reason": "Transaction failed: %s" % error}
                    for r in selected
                ],
            },
        )
        return
    report(plan, result)
    forms.alert(
        "Created: %s. Linked: %s. Skipped: %s.\nSee the report for details. The model was not saved or synced."
        % (len(result["created"]), len(result["linked"]), len(result["skipped"])),
        title=TITLE,
    )


main()
