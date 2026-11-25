"""Preview and bind permanent Craydl identities; never save or sync the model."""

from __future__ import unicode_literals

from pyrevit import forms, revit

from craydl_bridge import host, params


def main():
    doc = revit.doc
    try:
        host.require_project(doc)
        plan = params.binding_plan(host.project_parameters(doc))
    except Exception as error:
        forms.alert("%s\nNothing was changed." % error, title="Craydl Set Up Model")
        return
    conflicts = [row["name"] for row in plan if row["action"] == "name_conflict"]
    if conflicts:
        forms.alert(
            "Parameter name conflict: %s\nA different or non-shared parameter has this "
            "name. Nothing was changed. Ask your model manager to resolve the conflict."
            % ", ".join(conflicts),
            title="Craydl Set Up Model",
        )
        return
    if all(row["action"] == "ok" for row in plan):
        forms.alert(
            "This model is already set up. Nothing was changed.",
            title="Craydl Set Up Model",
        )
        return
    lines = []
    for row in plan:
        if row["action"] == "ok":
            lines.append("%s: already set up" % row["name"])
        else:
            lines.append(
                "%s: %s (%s)"
                % (
                    row["name"],
                    "Bind" if row["action"] == "bind" else "Add categories",
                    ", ".join(sorted(row["categories"])),
                )
            )
    if not forms.alert(
        "\n".join(lines)
        + "\n\nApply these text instance parameters under Identity Data? "
        "This does not save or sync the model.",
        title="Craydl Set Up Model",
        yes=True,
        no=True,
    ):
        return
    try:
        changed = host.set_up_model(doc)
    except Exception as error:
        forms.alert("%s\nNothing was changed." % error, title="Craydl Set Up Model")
        return
    forms.alert(
        "Model set up. The model was not saved or synced."
        if changed
        else "This model is already set up. Nothing was changed.",
        title="Craydl Set Up Model",
    )


main()
