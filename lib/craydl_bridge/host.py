"""Windows/Revit adapter. Never import this module in the CPython tests."""

from __future__ import unicode_literals

import os
import tempfile

import clr

clr.AddReference("System.Security")

from System import Array, Byte, Enum, Environment, Guid
from System.IO import StreamReader
from System.Net import (
    SecurityProtocolType,
    ServicePointManager,
    WebException,
    WebRequest,
)
from System.Security.Cryptography import DataProtectionScope, ProtectedData

from Autodesk.Revit.DB import (
    BuiltInCategory,
    BuiltInParameter,
    DesignOption,
    ElementId,
    ExternalDefinitionCreationOptions,
    FilteredElementCollector,
    GroupTypeId,
    SharedParameterElement,
    SpecTypeId,
    SubTransaction,
    Transaction,
    TransactionStatus,
)

from craydl_bridge import __version__, params, settings
from craydl_bridge.client import CraydlClient


def transport(url, headers, body):
    ServicePointManager.SecurityProtocol = SecurityProtocolType.Tls12
    request = WebRequest.Create(url)
    request.Method = "POST"
    request.Timeout = 30000
    request.ReadWriteTimeout = 30000
    # Never forward the bearer to a redirect destination.
    request.AllowAutoRedirect = False
    for name, value in headers.items():
        if name.lower() == "content-type":
            request.ContentType = value
        elif name.lower() == "accept":
            request.Accept = value
        else:
            request.Headers[name] = value
    data = Array[Byte](bytearray(body.encode("utf-8")))
    request.ContentLength = len(data)
    stream = request.GetRequestStream()
    try:
        stream.Write(data, 0, len(data))
    finally:
        stream.Close()
    try:
        response = request.GetResponse()
    except WebException as error:
        response = error.Response
        if response is None:
            raise
    try:
        reader = StreamReader(response.GetResponseStream())
        try:
            text = reader.ReadToEnd()
        finally:
            reader.Close()
        response_headers = {}
        for name in response.Headers.AllKeys:
            response_headers[name.lower()] = response.Headers[name]
        return int(response.StatusCode), response_headers, text
    finally:
        response.Close()


def protect(value):
    return bytes(
        bytearray(
            ProtectedData.Protect(
                Array[Byte](bytearray(value)), None, DataProtectionScope.CurrentUser
            )
        )
    )


def unprotect(value):
    return bytes(
        bytearray(
            ProtectedData.Unprotect(
                Array[Byte](bytearray(value)), None, DataProtectionScope.CurrentUser
            )
        )
    )


def settings_directory():
    directory = os.path.join(
        Environment.GetFolderPath(Environment.SpecialFolder.ApplicationData),
        "Craydl",
        "revit",
    )
    if not os.path.isdir(directory):
        os.makedirs(directory)
    return directory


def connected_client():
    directory = settings_directory()
    token = settings.load_token(directory, unprotect)
    if token is None:
        return None
    values = settings.load(directory)
    return CraydlClient(values["url"], token, transport, __version__)


def require_project(doc):
    if doc is None:
        raise ValueError("Open a project or project template first.")
    if doc.IsFamilyDocument:
        raise ValueError(
            "Family documents are not supported. Open a project or template."
        )


def _bindings(doc):
    """Include the definition and binding privately for re-binding by GUID."""
    shared = {}
    for element in FilteredElementCollector(doc).OfClass(SharedParameterElement):
        shared[element.GetDefinition().Id] = str(element.GuidValue).lower()
    iterator = doc.ParameterBindings.ForwardIterator()
    iterator.Reset()
    rows = []
    while iterator.MoveNext():
        definition, binding = iterator.Key, iterator.Current
        categories = set()
        for category in binding.Categories:
            # Category IDs are built-in enum values, not localized display names.
            name = Enum.GetName(
                BuiltInCategory, Enum.ToObject(BuiltInCategory, category.Id.Value)
            )
            if name:
                categories.add(str(name))
        rows.append(
            {
                "name": definition.Name,
                "guid": shared.get(definition.Id),
                "categories": categories,
                "definition": definition,
                "binding": binding,
            }
        )
    return rows


def project_parameters(doc):
    require_project(doc)
    return [
        {"name": row["name"], "guid": row["guid"], "categories": row["categories"]}
        for row in _bindings(doc)
    ]


def _definitions(app, rows):
    """Create fixed-GUID definitions without changing the user's shared file."""
    previous = app.SharedParametersFilename
    descriptor, path = tempfile.mkstemp(suffix=".txt", prefix="craydl-parameters-")
    os.close(descriptor)
    try:
        app.SharedParametersFilename = path
        file = app.OpenSharedParameterFile()
        if file is None:
            raise ValueError(
                "Revit could not open the temporary shared-parameter file."
            )
        group = file.Groups.Create("Craydl")
        definitions = {}
        for row in rows:
            options = ExternalDefinitionCreationOptions(
                row["name"], SpecTypeId.String.Text
            )
            options.GUID = Guid(row["guid"])
            options.UserModifiable = True
            definitions[row["guid"]] = group.Definitions.Create(options)
        return definitions
    finally:
        try:
            app.SharedParametersFilename = previous
        finally:
            os.remove(path)


def in_transaction(doc, name, edit):
    """Run an atomic edit; a callback returning False requests rollback."""
    require_project(doc)
    transaction = Transaction(doc, name)
    try:
        if transaction.Start() != TransactionStatus.Started:
            raise ValueError("Revit could not start the edit.")
        options = transaction.GetFailureHandlingOptions()
        options.SetClearAfterRollback(True)
        # Keep failure processing synchronous (no modeless Pending commit).
        options.SetForcedModalHandling(True)
        transaction.SetFailureHandlingOptions(options)
        if edit() is False:
            if transaction.RollBack() != TransactionStatus.RolledBack:
                raise ValueError("Revit did not roll back the edit.")
            return
        if transaction.Commit() != TransactionStatus.Committed:
            raise ValueError("Revit did not commit the edit.")
    except Exception:
        if transaction.GetStatus() == TransactionStatus.Started:
            transaction.RollBack()
        raise
    finally:
        transaction.Dispose()


def binding_changes(existing):
    """Read-only preview of required changes; a name conflict stops either button."""
    plan = params.binding_plan(existing)
    conflicts = [row["name"] for row in plan if row["action"] == "name_conflict"]
    if conflicts:
        raise ValueError(
            "Parameter name conflict: %s\nA different or non-shared parameter has this "
            "name. Ask your model manager to resolve the conflict."
            % ", ".join(conflicts)
        )
    return [row for row in plan if row["action"] != "ok"]


def bind_missing_parameters(doc, confirmed):
    """Apply the confirmed binding changes inside the caller's transaction."""
    existing = _bindings(doc)
    changes = binding_changes(existing)
    if changes != confirmed:
        raise ValueError("The Craydl parameter bindings changed. Preview the edit again.")
    if not changes:
        return False

    app = doc.Application
    new_rows = [row for row in changes if row["action"] == "bind"]
    definitions = _definitions(app, new_rows) if new_rows else {}
    for row in changes:
        categories = app.Create.NewCategorySet()
        previous = next((r for r in existing if r["guid"] == row["guid"]), None)
        if previous:
            for category in previous["binding"].Categories:
                categories.Insert(category)
            definition = previous["definition"]
        else:
            definition = definitions[row["guid"]]
        for name in row["categories"]:
            categories.Insert(
                doc.Settings.Categories.get_Item(getattr(BuiltInCategory, name))
            )
        binding = app.Create.NewInstanceBinding(categories)
        method = (
            doc.ParameterBindings.ReInsert if previous else doc.ParameterBindings.Insert
        )
        if not method(definition, binding, GroupTypeId.IdentityData):
            raise ValueError("Revit refused to bind %s." % row["name"])

    # Make the new parameters visible on elements before stamping them.
    doc.Regenerate()
    return True


def read_stamp(element, guid):
    parameter = element.get_Parameter(Guid(guid))
    return parameter.AsString() if parameter else None


def write_stamp(element, guid, text):
    """Caller owns the transaction; a refused edit must never look successful."""
    parameter = element.get_Parameter(Guid(guid))
    if parameter is None:
        raise ValueError("The Craydl parameter is not available on this element.")
    if parameter.IsReadOnly:
        raise ValueError(
            "Revit refused the edit: Project Information or the element may be owned "
            "by another user, or the parameter is read-only."
        )
    if not parameter.Set(text):
        raise ValueError("Revit refused to write the Craydl stamp.")


def editing_design_option(doc):
    return DesignOption.GetActiveDesignOptionId(doc) != ElementId.InvalidElementId


def phase_names(doc):
    return [phase.Name for phase in doc.Phases]


def _room_record(doc, room):
    phase_id = room.get_Parameter(BuiltInParameter.ROOM_PHASE).AsElementId()
    level = doc.GetElement(room.LevelId)
    located = room.Location is not None
    return {
        "element_id": room.Id.Value,
        "name": room.get_Parameter(BuiltInParameter.ROOM_NAME).AsString() or "",
        "number": room.Number or "",
        "located": located,
        "level": level.Name if level is not None else "",
        "area_sf": round(room.Area, 1),
        "phase": doc.GetElement(phase_id).Name,
        "stamp": read_stamp(room, params.PARAMETERS[1]["guid"]) or "",
    }


def read_model_rooms(doc):
    """Do not filter by placement or phase: old-phase stamps still own IDs."""
    return [
        _room_record(doc, room)
        for room in FilteredElementCollector(doc)
        .OfCategory(BuiltInCategory.OST_Rooms)
        .WhereElementIsNotElementType()
    ]


def _unstamped_model_room(doc, element_id, guid):
    room = doc.GetElement(ElementId(element_id))
    if room is None:
        raise ValueError("The model room no longer exists.")
    if read_stamp(room, guid):
        raise ValueError("The model room now has a Craydl ID. Run Match Rooms again.")
    return room


def apply_rooms(doc, phase_name, actions, confirmed_bindings):
    """Apply checked Match Rooms actions in one undo step, atomically per row."""
    require_project(doc)
    if editing_design_option(doc):
        raise ValueError("Finish editing the design option before using Match Rooms.")
    keys = {"create": "created", "link": "linked", "move": "moved"}
    allowed = tuple(keys)
    if any(action.get("action") not in allowed for action in actions):
        raise ValueError("Only create, link and move rows can be applied.")
    result = {"created": [], "linked": [], "moved": [], "skipped": []}
    if not actions:
        return result
    phase = next((p for p in doc.Phases if p.Name == phase_name), None)
    if phase is None:
        raise ValueError("The selected phase no longer exists. Run Match Rooms again.")

    guid = params.PARAMETERS[1]["guid"]

    def edit():
        bound_fields = bind_missing_parameters(doc, confirmed_bindings)
        for action in actions:
            kind = action["action"]
            sub = SubTransaction(doc)
            try:
                if sub.Start() != TransactionStatus.Started:
                    raise ValueError("Revit could not start this room edit.")
                room_id = action["room"]["id"]
                if kind == "create":
                    room = doc.Create.NewRoom(phase)
                    if not room.get_Parameter(BuiltInParameter.ROOM_NAME).Set(
                        action["room"]["display_name"]
                    ):
                        raise ValueError("Revit refused to set the new room's name.")
                    write_stamp(room, guid, room_id)
                    edited = [room]
                elif kind == "link":
                    room = _unstamped_model_room(doc, action["element_id"], guid)
                    write_stamp(room, guid, room_id)
                    if action["rename"] and not room.get_Parameter(
                        BuiltInParameter.ROOM_NAME
                    ).Set(action["room"]["display_name"]):
                        raise ValueError("Revit refused to rename the model room.")
                    edited = [room]
                else:
                    source = doc.GetElement(ElementId(action["from_element_id"]))
                    if source is None or read_stamp(source, guid) != room_id:
                        raise ValueError(
                            "The Craydl ID is no longer on that room. Run Match Rooms again."
                        )
                    target = _unstamped_model_room(doc, action["to_element_id"], guid)
                    # Both writes belong to this row: a refusal restores the source.
                    write_stamp(source, guid, "")
                    write_stamp(target, guid, room_id)
                    edited = [source, target]
                records = [_room_record(doc, room) for room in edited]
                if sub.Commit() != TransactionStatus.Committed:
                    raise ValueError("Revit did not commit this room edit.")
                result[keys[kind]].append({"action": action, "model_rooms": records})
            except Exception as error:
                if sub.GetStatus() == TransactionStatus.Started:
                    sub.RollBack()
                result["skipped"].append({"action": action, "reason": "%s" % error})
            finally:
                sub.Dispose()
        if bound_fields and not any(result[key] for key in keys.values()):
            return False

    in_transaction(doc, "Craydl: match rooms", edit)
    return result
