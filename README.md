# Revit bridge how-to

Use these tools to bring a Craydl job's room list into a Revit 2025 project.
You choose what to apply. The tools never save or sync the model and never
change the job in Craydl. Save or sync yourself when you are ready.

## Install

1. Install **pyRevit 7.0** with its IronPython 2.7 engine for Revit 2025,
   including the pyRevit CLI. Ask your model manager if you do not have it.
2. Close Revit. If you previously copied `Craydl.extension` by hand, move that
   folder out of `%APPDATA%\pyRevit\Extensions` first (keep it as a backup).
   In a Windows terminal, install from the public Git URL:

   ```powershell
   pyrevit extend ui Craydl https://github.com/CraydlPlatform/craydl-revit-extension.git --branch=main
   ```

   This installs a Git-backed `Craydl.extension`; no GitHub login is required.
3. Restart Revit, or reload pyRevit. Look for **Craydl → Bridge** and the five
   buttons: **Connect**, **Set Up Model**, **Link Job**, **Seed Rooms** and **Check Model**.

### Update

Close Revit, run the following in a Windows terminal, then reopen Revit:

```powershell
pyrevit extensions update Craydl
```

Install/update syntax is checked against [pyRevit 7.0's CLI usage](https://github.com/pyrevitlabs/pyRevit/blob/ccc49398b26fece01eb16ac3c773070c86d9becc/dev/pyRevitLabs/pyRevitCLI/Resources/UsagePatterns.txt).
Do not edit the installed files: updates replace them. The public repository is
an automatically generated mirror of the released extension, not a source repo.
Changes are made only in craydl-app, and published from `production` by CI.

### Folder-copy fallback

If URL installation or updating is unavailable, ask your model manager for the
released `revit/Craydl.extension` folder from craydl-app. Close Revit and copy the
whole folder into `%APPDATA%\pyRevit\Extensions`. Keep the `.extension` name and
all its contents together; do not copy just button scripts. Reopen Revit.
A hand-copied folder cannot update through Git: replace the whole folder with a
new released copy, or remove it before switching to URL installation.

## Connect

1. In Craydl, open **Settings → Connected Agents** and create your own token.
   Leave **both direct-action permissions off**. Keep the token private.
2. Click **Connect** in Revit, choose **Connect**, and paste the token. The
   button checks the connection before storing it. Your Windows account
   encrypts the saved token; another Windows user must connect for themselves.
3. If the check fails, read the message and check your token, job access and
   internet connection. No new token is stored on failure. **Disconnect**
   removes the local copy; revoke the token in Craydl too if it is no longer needed.

Connect normally uses `https://ccc.craydl.com/api/assistant/mcp`. Ask your model
manager before using a different server. The non-secret endpoint setting lives
in `%APPDATA%\Craydl\revit\config.json`; do not put a token in that file.

## Set up a model or template

1. Open a project or project template, not a family, then click **Set Up Model**.
2. Review and confirm the proposed fields. The tool adds `Craydl_JobID` to
   Project Information and `Craydl_RoomID` to rooms, as text fields under
   Identity Data. Existing fields with the correct identity are kept. A field
   with the same name but a different identity stops setup: ask your model
   manager to resolve it rather than deleting fields blindly.
3. If everything is already set up, nothing changes. For a template, **save the
   template yourself after setup**, so new projects inherit the fields. Do not
   link a reusable template to a real job or seed its rooms unless that is intended.

## Link a job

1. In the project you want to use, click **Link Job** after Connect and setup.
2. Search by job name or address. Choose the job and check its name, customer,
   location and status. At most 20 results appear; cancel and enter more of the
   name or address if needed.
3. Confirm the link. If the model already has a job, the button shows it and asks
   before replacing it. This changes only the job ID in Project Information;
   it does not clear or replace room IDs. Check carefully before switching jobs.

## Seed rooms

1. Finish editing any design option. Click **Seed Rooms** in the connected,
   set-up project with its job linked. A message names any missing step.
2. Choose the phase. The last phase in the model is the starting choice. New
   rooms and name matches use this phase; existing room IDs are checked across
   **all phases**, so an old-phase room is not created again in a new phase.
3. Check the job name, location, phase and counts. Review the ticked list:
   **Create** adds an unplaced room with the Craydl display name;
   **Link existing room** adds only its Craydl room ID. A name match ignores
   punctuation, spaces and case, but it must be unambiguous on both sides.
4. Untick anything you do not want. Click **Apply selected rooms** to confirm.
   Cancel or untick everything to change nothing. Only active Craydl rooms
   participate; GENERAL and archived Craydl rooms are not added.
5. Read the report in pyRevit's output window. Place newly created rooms yourself
   using Revit's room tools. Revit assigns their numbers; the bridge does not
   set or change numbers. Save or sync yourself when satisfied.

The whole application is one undo step, **Craydl: seed rooms**. A refused row is
skipped while other selected rows proceed. If Revit cannot commit the overall
edit, nothing from that seed transaction is kept. Running Seed Rooms again
adds only missing rooms: it never deletes, moves, renames or re-numbers an
existing room, and it does not edit rooms already carrying the right ID.

## Read the report

| Line | What it means | What to do |
| --- | --- | --- |
| Created | A new unplaced room now has the Craydl name and room ID. | Place it in the chosen phase when ready. |
| Linked | An existing room received the Craydl room ID; nothing else changed. | Check the match; no further action is normally needed. |
| Skipped | Revit refused this selected row. The report gives the reason. | Resolve the reason, such as asking the owner to relinquish the room, then run again. A failed creation does not leave a half-created room behind. |
| Present | Exactly one room already has this Craydl room ID, in any phase. This is a preview count, not an edit. | Nothing to do if its identity and name are right. |
| Present with a different name | The ID matches, but the names differ beyond case, spaces or punctuation. The report shows the model name, number, phase and Craydl name. | Decide which name is right; correct it yourself in the appropriate system. The tool will not rename it. This count is included in Present. |
| Duplicate stamp | Several model rooms carry the same Craydl room ID, possibly from copying a room. | Decide which room represents that Craydl room. With your model manager, correct or clear the other IDs; do not delete rooms just to clear this warning. |
| Unknown stamp | A model room has an ID absent from the active, non-GENERAL room list for this job. It may belong to another job or an archived room. | Check the linked job and the room's history before correcting or clearing its ID. All phases are checked. |
| Unlinked | An unstamped room in the chosen phase was not offered as a unique link. It may have no match, or more than one possible match. | Check whether it belongs in this job. Resolve ambiguous names or link the correct permanent room ID with your model manager. The bridge leaves it alone. |

When there are no rooms to create or link, or you cancel the checklist, no edit
starts. The report still lists the rooms needing a person. A report of a
problem is not permission to change or delete a room automatically.


## Check a model

Run **Check Model** after linking and seeding, after placing rooms and products,
or before sharing the model's data with Craydl. Open a project (not a family),
choose **Check this model**, then choose the phase that holds the new work.
The last phase is the starting choice, not a guess about your model. Check it:
new construction may still have been modeled in Existing.

The button reads the model once, changes nothing and sends nothing. It needs no
connection or token. Read the report in pyRevit's output window. **FIX** means a
condition would stop useful sharing; correct it yourself before sharing.
**NOTE** means something to review, not an instruction to delete it. Counts are
findings, not a count of edits. Nothing in the report authorizes an automatic fix.

| Finding code | What it means | What to do |
| --- | --- | --- |
| `not_set_up` (FIX) | The Craydl fields are missing or not bound correctly. | Run Set Up Model; ask your model manager about identity conflicts. |
| `not_linked` (FIX) | The model has no valid Craydl job ID. | Connect and use Link Job to select the right job. |
| `no_placed_rooms` (FIX) | No room has positive area in the chosen phase. | Check the phase, place rooms and resolve their boundaries. |
| `starter_rooms` (NOTE) | Unstamped starter rooms, such as Bed 1 or Garage, have no area. | Place those needed for this job; remove unused leftovers by hand. |
| `rooms_not_placed` (NOTE) | Other rooms have no area, including located rooms that are not enclosed. | Place or enclose the rooms you need; review the rest before removing them. |
| `rooms_without_id` (FIX) | Placed rooms in the chosen phase lack a Craydl room ID. | Run Seed Rooms and review the matches; ask your model manager about unmatched rooms. |
| `duplicate_room_id` (FIX) | Several rooms carry one Craydl room ID, across any phases. | Identify the correct room and correct or clear the other stamps with your model manager. |
| `duplicate_room_names` (NOTE) | Placed rooms share a name within a phase. | Give them distinct names so they can be distinguished. |
| `nothing_in_new_phase` (FIX) | No family instances or wall, floor, ceiling or roof hosts were created in the chosen phase. | Check your phase choice and the elements' created phases in Revit. |
| `products_outside_rooms` (FIX) | New products have no room reference in any phase. | Check placement and room boundaries, including door relationships. |
| `products_without_number` (NOTE) | New products have no usable type model number; NA, Not a Type and similar placeholders do not identify a product. | Add the manufacturer's model number where known. A URL alone is reported separately, not treated as a number. |
| `repeated_materials` (NOTE) | At least 100 materials share a name. | Review and consolidate redundant materials carefully; do not remove needed finishes blindly. |

The summary separates placed rooms in the chosen and other phases, unplaced
rooms, and located rooms with zero area. It also shows created/demolished items
and hosts per phase, product identification and material use. New products are
model-category family instances created in your chosen phase and not demolished.
The report is a readiness check, not a complete model audit or proof of a live
Craydl connection. If `skipped_elements` is nonzero, some elements could not be
read: review the model and check again; the report is incomplete for those elements.

After the report you may save a **snapshot**. It is a UTF-8 JSON file containing
what the check read, including this job's room and product names and project
information. Choose Yes and a folder; the button shows the full file path.
Keep the file private as you would the model. It stays on this PC and is sent
nowhere by the button. No ends quietly. Cancelling a choice or the folder picker
changes nothing. A read or file-write error is reported; the model is never edited.
The snapshot is not a Revit backup and saving it does not save the model.

## Check a template and start a job from it

1. Open the reusable project template and run **Set Up Model** first, so new jobs
   inherit the correct Craydl fields. Do not link it to a real job.
2. Run **Check Model → Check this template**. A `.rte` path starts with that mode
   selected. You can also choose it yourself. No new-work phase is requested.
3. Read the template report. A clean template is set up, has no job ID, no Craydl
   room IDs and no rooms. `not_set_up`, `template_linked`, `template_room_ids`
   and `template_rooms` are FIX findings. Clear project-specific job and room
   stamps and remove project rooms by hand in Revit, with your model manager.
   `template_project_fields` is a NOTE about client/status values;
   `template_products` is a NOTE about product instances; `repeated_materials`
   asks you to review duplicate material names. Review those notes too rather
   than automatically deleting template content you need.
4. Clean the template in Revit by hand and check again until no **FIX** line is
   left. Review any skipped elements before trusting the result. **Save the
   template yourself**; Check Model neither saves nor changes it.
5. For each new job, create a project from that template. Connect if needed,
   **Link Job**, **Seed Rooms**, then **place the rooms** using Revit's room
   tools. Run the model check with the correct new-work phase. Save or sync
   the project yourself when ready.
