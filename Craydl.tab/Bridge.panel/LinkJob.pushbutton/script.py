"""Choose a Craydl job and stamp Project Information, after confirmation only."""

from __future__ import unicode_literals

from pyrevit import forms, revit

from craydl_bridge import host, params
from craydl_bridge.client import CraydlError

TITLE = "Craydl Link Job"
JOB_GUID = params.PARAMETERS[0]["guid"]


def summary(job):
    return "Name: %s\nCustomer: %s\nLocation: %s\nStatus: %s" % (
        job.get("name") or "(unnamed)",
        job.get("customer_name") or "(not provided)",
        job.get("location") or "(not provided)",
        job.get("status") or "(not provided)",
    )


def main():
    doc = revit.doc
    try:
        host.require_project(doc)
        bindings = host.binding_changes(host.project_parameters(doc))
    except Exception as error:
        forms.alert("%s\nNothing was changed." % error, title=TITLE)
        return
    try:
        client = host.connected_client()
    except Exception:
        forms.alert(
            "Could not read the connection. Run Connect first. Nothing was changed.",
            title=TITLE,
        )
        return
    if client is None:
        forms.alert("Run Connect first. Nothing was changed.", title=TITLE)
        return
    try:
        current = host.read_stamp(doc.ProjectInformation, JOB_GUID)
    except Exception as error:
        forms.alert("%s\nNothing was changed." % error, title=TITLE)
        return
    current_summary = ""
    if current:
        try:
            if not params.is_job_id(current):
                raise CraydlError(
                    "invalid_id", "The stored stamp is not a canonical job id."
                )
            reply = client.call_tool("job_lookup", {"job_id": current})
            job = reply.get("data") if isinstance(reply, dict) else None
            if not isinstance(job, dict) or job.get("id") != current:
                raise CraydlError("protocol", "Invalid current-job reply.")
            current_summary = summary(job) + "\nID: " + current
        except CraydlError as error:
            current_summary = "ID: %s\nCould not read current job (%s): %s" % (
                current,
                error.code,
                error.args[0],
            )
        forms.alert("Currently linked job\n" + current_summary, title=TITLE)
    query = forms.ask_for_string(
        prompt="Type part of a job name or address (up to 255 characters).",
        title=TITLE,
    )
    if query is None:
        return
    query = query.strip()
    if not query or len(query) > 255:
        forms.alert(
            "Enter between 1 and 255 characters. Nothing was changed.", title=TITLE
        )
        return
    try:
        page = client.call_tool("job_search", {"query": query, "limit": 20})
        data = page.get("data") if isinstance(page, dict) else None
        rows = data.get("records") if isinstance(data, dict) else None
        if not isinstance(rows, list) or len(rows) > 20:
            raise CraydlError("protocol", "Invalid job search reply.")
        jobs = []
        for row in rows:
            job = row.get("data") if isinstance(row, dict) else None
            if not isinstance(job, dict) or not params.is_job_id(job.get("id")):
                raise CraydlError("protocol", "Invalid job identity in search reply.")
            jobs.append(job)
    except CraydlError as error:
        forms.alert(
            "Job search failed (%s): %s\nNothing was changed."
            % (
                error.code,
                error.args[0],
            ),
            title=TITLE,
        )
        return
    if not jobs:
        forms.alert(
            "No jobs found. Try another name or address. Nothing was changed.",
            title=TITLE,
        )
        return
    if len(jobs) == 20 or page.get("complete") is False:
        forms.alert(
            "Showing at most 20 jobs. If your job is not listed, cancel and type more of "
            "the name or address to narrow the search.",
            title=TITLE,
        )
    labels = [
        "%s. %s | %s | %s | %s"
        % (
            index + 1,
            job.get("name") or "(unnamed)",
            job.get("customer_name") or "(not provided)",
            job.get("location") or "(not provided)",
            job.get("status") or "(not provided)",
        )
        for index, job in enumerate(jobs)
    ]
    choice = forms.SelectFromList.show(
        labels, title=TITLE, multiselect=False, button_name="Choose job"
    )
    if choice is None:
        return
    selected = jobs[labels.index(choice)]
    same_job = selected["id"] == current
    if same_job and not bindings:
        forms.alert(
            "This model is already linked to that job. Nothing was changed.",
            title=TITLE,
        )
        return
    prompt = (
        "Link this model to this job?\n\n"
        + summary(selected)
        + "\nID: "
        + selected["id"]
    )
    if same_job:
        prompt = "Keep this job link and add the missing fields?\n\n" + current_summary
    elif current:
        prompt = (
            "Replace the current link?\n\nCurrent job\n"
            + current_summary
            + "\n\nNew job\n"
            + summary(selected)
            + "\nID: "
            + selected["id"]
        )
    if bindings:
        prompt += "\n\nCraydl fields to add or complete: " + ", ".join(
            row["name"] for row in bindings
        )
    if not forms.alert(
        prompt + "\n\nThis does not save or sync the model.",
        title=TITLE,
        yes=True,
        no=True,
    ):
        return

    def edit():
        if host.read_stamp(doc.ProjectInformation, JOB_GUID) != current:
            raise ValueError(
                "The job link changed during selection. Run Link Job again."
            )
        host.bind_missing_parameters(doc, bindings)
        host.write_stamp(doc.ProjectInformation, JOB_GUID, selected["id"])

    try:
        host.in_transaction(doc, "Craydl: link job", edit)
    except Exception as error:
        forms.alert(
            "Revit could not link the job: %s\nIf another user owns Project Information, "
            "ask them to relinquish it and try again. Nothing was changed." % error,
            title=TITLE,
        )
        return
    forms.alert(
        "Linked to %s. The model was not saved or synced."
        % (selected.get("name") or selected["id"],),
        title=TITLE,
    )


main()
