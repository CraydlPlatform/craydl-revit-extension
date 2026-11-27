"""Check the open project without editing it or contacting Craydl."""

from __future__ import unicode_literals

import os

from pyrevit import forms, revit, script

from craydl_bridge import check, host_scan


def alert(text, **options):
    return forms.alert(text, title="Craydl Check Model", **options)


def cancelled():
    alert("Cancelled. Nothing was changed.")


def main():
    doc = revit.doc
    if doc is None or doc.IsFamilyDocument:
        alert("Open a project or template first. Nothing was changed.")
        return
    mode = forms.ask_for_one_item(
        ["Check this model", "Check this template"],
        default="Check this template"
        if host_scan.is_template_path(doc.PathName)
        else "Check this model",
        prompt="Which check would you like to run?",
        title="Craydl Check Model",
    )
    if not mode:
        cancelled()
        return
    phase = None
    if mode == "Check this model":
        phases = [p.Name for p in doc.Phases]
        phase = forms.ask_for_one_item(
            phases,
            default=phases[-1] if phases else None,
            prompt="Which phase holds the new work?",
            title="Craydl Check Model",
        )
        if not phase:
            cancelled()
            return
    try:
        snapshot = host_scan.read_snapshot(doc, host_scan.utc_now())
        problems = check.validate(snapshot)
        if problems:
            alert("Snapshot could not be checked:\n" + "\n".join(problems))
            return
        report = (
            check.model_report(snapshot, phase)
            if mode == "Check this model"
            else check.template_report(snapshot)
        )
        output = script.get_output()
        for line in check.summary_lines(report, snapshot["model"]["title"]):
            print(line)
        findings = report["findings"]
        for finding in findings:
            for line in check.finding_lines(finding):
                print(line)
            ids = finding["element_ids"]
            if ids:
                print(
                    output.linkify(
                        host_scan.element_ids(ids), title="Select these %s" % len(ids)
                    )
                )
        if not findings:
            print(check.NO_FINDINGS)
        alert(
            "%s to fix and %s to review. See the pyRevit output window for details."
            % (
                sum(1 for row in findings if row["level"] == "fix"),
                sum(1 for row in findings if row["level"] == "note"),
            )
        )
    except Exception as error:
        alert("%s\nNothing was changed in the model." % error)
        return
    if not alert(
        "Save a snapshot? The file holds this job's room and product names, "
        "stays on this PC and is sent nowhere.",
        yes=True,
        no=True,
    ):
        return
    folder = forms.pick_folder()
    if not folder:
        cancelled()
        return
    try:
        path = os.path.join(folder, check.file_name(snapshot))
        host_scan.write_text(path, check.to_json(snapshot))
    except Exception as error:
        alert("%s\nNothing was changed in the model." % error)
        return
    alert("Snapshot saved:\n%s" % path)


main()
