# Revit bridge how-to

Use these tools to match a Craydl job's room list with a Revit 2025 project.
You choose what to apply, including which rooms to add to the job in Craydl.
The tools never save or sync the model. Save or sync yourself when you are ready.

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
3. Restart Revit, or reload pyRevit. Look for **Craydl → Bridge** and the four
   buttons: **Connect**, **Link Job**, **Match Rooms** and **Check Model**.

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
   Leave **both direct-action permissions off**. Sending a room does not need
   either permission. Keep the token private.
2. Click **Connect** in Revit, choose **Connect**, and paste the token. The
   button checks the connection before storing it. Your Windows account
   encrypts the saved token; another Windows user must connect for themselves.
3. If the check fails, read the message and check your token, job access and
   internet connection. No new token is stored on failure. **Disconnect**
   removes the local copy; revoke the token in Craydl too if it is no longer needed.

Connect normally uses `https://ccc.craydl.com/api/assistant/mcp`. Ask your model
manager before using a different server. The non-secret endpoint setting lives
in `%APPDATA%\Craydl\revit\config.json`; do not put a token in that file.

## Link a job

1. In the project you want to use (not a family), click **Link Job** after Connect.
2. Search by job name or address. Choose the job and check its name, customer,
   location and status. At most 20 results appear; cancel and enter more of the
   name or address if needed.
3. Confirm the link. If the model already has a job, the button shows it and asks
   before replacing it. Check carefully before switching jobs: changing the job
   ID in Project Information does not clear or replace room IDs.
4. If `Craydl_JobID` or `Craydl_RoomID` is missing or not bound to the right
   category, the confirmation names the fields to add or complete. The button
   binds them under Identity Data and writes the job ID in one undo step,
   **Craydl: link job**. If a field has the same name but a different identity,
   Link Job and Match Rooms both stop; ask your model manager to resolve the
   conflict.

## Match rooms

Run **Match Rooms** when starting a job's model, matching rooms that are already
modeled, or picking up where you left off. You can run it again as often as needed.

1. Finish editing any design option. Click **Match Rooms** in the connected
   project with its job linked.
2. Choose the phase for **new** rooms. The last phase is the starting choice.
   Existing rooms and their Craydl IDs are checked across **all phases**.
3. Check the job name, location, phase and counts. If any Craydl fields are
   missing or partly bound, the window names what Apply will add or complete.
   Review each Craydl room that still needs a decision:
   - **Link to a model room** adds the Craydl ID to an existing room. The
     list gives the room's number, name, phase and whether it is placed, with
     name matches first. Tick **Rename the model room to the Craydl name**
     only if you also want to change its name.
   - **Create a new unplaced room** adds a room with the Craydl name and ID
     in the phase you chose.
   - **Skip** leaves the room for another time. A clear name match is
     preselected as a link; name matching ignores case, spaces and punctuation
     and prefers a uniquely placed match. If there is no match and no placed
     room left to link, Create is preselected. Ambiguous matches and rooms
     that need review start on Skip. Check the reason shown on each row.
4. Under **Move a Craydl ID**, you can move an ID from an unplaced room to its
   clear placed match. Moves are never preselected. This transfers the ID;
   it does not physically move or delete either room. Use any target room
   only once, whether linking or moving.
5. Review **Model rooms with no Craydl room**. If the Craydl server and your
   access allow sending, tick the rooms you want to add, or choose **Tick all
   rooms below** and untick any you don't want. When you click **Apply**, each
   ticked room is added to the job in Craydl as a room from the model, with its
   name, level and number, then linked in the same Revit undo step as your
   other edits. Undo removes the link in the model, not the room in Craydl;
   the next **Match Rooms** run offers to link it again. Archive an unwanted
   room on the job's **Rooms** tab in Craydl. If sending is unavailable, add
   missing rooms on that tab, then run **Match Rooms** again to link them.
   Unplaced, unstamped template starter rooms are counted separately and
   never offered.
6. Click **Apply** to confirm your choices. Cancel, close the window, or apply
   with nothing selected to change nothing. Only active Craydl rooms participate;
   GENERAL and archived Craydl rooms are not added.
7. Read the report in pyRevit's output window. Place unplaced matched rooms with
   Revit's **Room** tool, picking each from the **Room** list on the Options Bar.
   The bridge does not set or change room numbers. Save or sync yourself when
   satisfied.

The whole Revit edit, including any field bindings, is one undo step,
**Craydl: match rooms**. A refused row is skipped while the other selected rows
proceed. If every selected row fails, no new bindings are kept. If Revit cannot
commit the overall Revit edit, the model changes are not kept; rooms already
added in Craydl stay there.

## Read the report

| Line | What it means | What to do |
| --- | --- | --- |
| Created | A new unplaced room received the Craydl name and ID. | Place it in the chosen phase when ready. |
| Linked | An existing room received the Craydl ID and was renamed only if you selected that option. | Check the match and place the room if needed. |
| Moved | The listed target received the ID from the unplaced room named in the detail. | Check that the placed room now represents the Craydl room. |
| Skipped | Revit refused a selected edit. The report gives the reason. | Resolve the cause, such as asking the owner to relinquish the room, then run again. A failed creation leaves no half-created room. |
| Sent to Craydl | Craydl added the room and Revit linked it. The report gives the new Craydl ID. | Place the model room if needed. |
| Not sent | Craydl did not add the room. The report gives the reason. | Correct the issue before sending it again. |
| Sent, not linked | Craydl added the room, but Revit could not add its ID. The report gives the new ID and the reason. | Run Match Rooms again to link the existing room. |
| Send uncertain | Craydl may have added the room, but the bridge could not verify it. | Run Match Rooms again before sending the room again. |
| Matched with a different name | One model room already had the ID, but its name differs beyond case, spaces or punctuation. | Decide which name is right and correct it in the appropriate system if needed. |
| Duplicate ID | Several model rooms carry the same Craydl room ID, possibly from copying a room. | Decide which room represents the Craydl room. With your model manager, correct or clear the other IDs; do not delete rooms just to clear this warning. |
| Unknown ID | The shown ID is absent from this job's active room list. It may belong to another job or an archived room. | Check the linked job and the room's history before correcting or clearing its ID. |
| Not decided | You did not choose an edit for this Craydl room. The report gives the reason shown in the table and lists any name matches. | Review the room on the next run. |
| Move offered | The listed ID transfer was not applied. | Review the source and target and confirm the move next time if appropriate. |
| Only in the model | This model room did not receive a link or ID move and had no starting link choice. | If the room does not exist in Craydl, add it on the job's Rooms tab, then run Match Rooms again. |

If you send two rooms with the same name, Craydl numbers them, so the next
report lists the first as matched with a different name; no action is needed.

If no rooms need a decision or you cancel, the report still lists anything
that needs review. The starter-room count is informational; remove only the
template leftovers you do not need.

## Check a model

Run **Check Model** after linking and matching rooms, after placing rooms and products,
or before sharing the model's data with Craydl. Open a project (not a family),
choose **Check this model**, then choose the phase that holds the new work.
The last phase is the starting choice, not a guess about your model. Check it:
new construction may still have been modeled in Existing.

The button reads the model once, changes nothing and sends nothing. It needs no
connection or token. Read the report in pyRevit's output window. The **Stage**
line tells you where to start: check a different phase for a survey or as-built
model, link the job, match or place rooms, add rooms, or review the findings below.
A matched model can still have findings. **FIX** means something to correct before
sharing; **NOTE** means something to review. The alert counts findings, not edits.
When a **Select these N** line appears under a finding, click it to select those
elements in Revit. The link includes up to 50 elements, and the examples show how
many more distinct examples were left out. Nothing in the report fixes the model for you.

| Finding | What it means | What to do |
| --- | --- | --- |
| Craydl fields missing (FIX) | The Craydl fields are missing or not bound correctly. | Use Link Job to add the missing fields. |
| Model not linked (FIX) | The model has no valid Craydl job ID. | Connect and use Link Job to select the right job. |
| No rooms with an area in the chosen phase (FIX) | None of the rooms in that phase has an area. | Place the rooms that are waiting or run the check on the phase that holds the rooms. |
| Starter rooms left over (NOTE) | Unstamped starter rooms, such as Bed 1 or Garage, have no area. | Place the ones you need and remove the leftovers by hand. |
| Rooms waiting to be placed (NOTE) | These rooms already have Craydl IDs but have no area, in any phase. | Use Revit's Room tool to place them or check their boundaries if they already have a location. |
| Other rooms without an area (NOTE) | These rooms have no Craydl ID and are not template starters. | Place or enclose the rooms you need; review the rest before removing them. |
| Placed rooms without a Craydl ID (FIX) | Placed rooms in the chosen phase lack a Craydl room ID. | Use Match Rooms to link each one. |
| Craydl ID on an unplaced room (FIX) | A room with a Craydl ID has no area, and exactly one placed room without an ID has the same name. | Review both rooms in Match Rooms and move the ID to the placed room. |
| Duplicate Craydl room IDs (FIX) | Multiple rooms share a Craydl room ID, possibly across phases. | Identify the correct room and resolve the duplicate IDs with your model manager. |
| Duplicate placed room names (NOTE) | Placed rooms in the chosen phase share a name. | Give them distinct names if they represent different rooms. |
| No work created in the chosen phase (FIX) | No family instances, walls, floors, ceilings or roofs were created in the chosen phase. | Check your phase choice and the elements' created phases in Revit. |
| Products on a placeholder type (FIX) | These products were loaded on their placeholder type and lack a usable model number. | Load the real type from the family's type catalog. |
| Products with a maker or link but no model number (NOTE) | A manufacturer or URL is filled in, but there is no usable model number and the type is not a placeholder. | Add the manufacturer's model number where known. |
| Unidentified products (NOTE) | These are not placeholder types, but have no usable model number, manufacturer or URL. | Add product details where known. |
| Custom items (NOTE) | In-place families in product categories are not counted as products. | Review them as custom items. |
| Products outside rooms (NOTE) | These products have no room reference, even if no room is placed yet. | Check placement and room boundaries, including door relationships. |
| Repeated material names (NOTE) | At least 100 materials share a name. | Review and consolidate redundant materials carefully; do not remove needed finishes blindly. |

The summary separates rooms with an area by phase, rooms without a location,
located rooms with no area, and rooms with a Craydl ID. It also shows when items
and hosts were created or demolished, product identification and material use.
Product counts cover family instances in product categories created in the chosen
phase and not demolished. Nested parts and in-place families are not products;
the summary counts nested parts and custom items separately. A URL alone is not
a model number. The report is a readiness check, not a complete audit or proof
of a live Craydl connection. If **Elements that could not be read** is nonzero,
review the model and check again; the report is incomplete for those elements.

After the report you may save a **snapshot**. It is a UTF-8 JSON file containing
what the check read, including this job's room and product names and project
information. Choose Yes and a folder; the button shows the full file path.
Keep the file private as you would the model. It stays on this PC and is sent
nowhere by the button. No ends quietly. Cancelling a choice or the folder picker
changes nothing. A read or file-write error is reported; the model is never edited.
The snapshot is not a Revit backup and saving it does not save the model.

## Check a template and start a job from it

1. Open the reusable project template. It does not need Craydl fields; they
   are added when you link a project to a job. Do not link the template itself.
2. Run **Check Model → Check this template**. A `.rte` path starts with that mode
   selected. You can also choose it yourself. No new-work phase is requested.
3. Read the template report. A clean template has no job ID, no Craydl room IDs
   and no rooms. **Template linked to a job**, **Template rooms with Craydl IDs**
   and **Rooms in the template** are FIX findings. Clear project-specific job
   and room IDs and remove project rooms by hand in Revit, with your model manager.
   **Project fields filled in** is a NOTE about client or status values;
   **Products in the template** is a NOTE about product instances, and
   **Repeated material names** asks you to review duplicate material names.
   Review these notes rather than automatically deleting template content you need.
4. Clean the template in Revit by hand and check again until no **FIX** line is
   left. Review any skipped elements before trusting the result. **Save the
   template yourself**; Check Model neither saves nor changes it.
5. For each new job, create a project from that template. Connect if needed,
   **Link Job**, **Match Rooms**, then **place the rooms** using Revit's room
   tools. Run the model check with the correct new-work phase. Save or sync
   the project yourself when ready.
