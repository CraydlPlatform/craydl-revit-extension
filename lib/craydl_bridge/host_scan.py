"""Read-only Revit snapshot adapter. Never imported by CPython tests."""

from __future__ import unicode_literals

import io

from System import DateTime, Enum
from Autodesk.Revit.DB import (
    BuiltInCategory,
    BuiltInParameter,
    CategoryType,
    Element,
    ElementId,
    FamilyInstance,
    FilteredElementCollector,
    Material,
    PointCloudInstance,
    RevitLinkInstance,
    SharedParameterElement,
    ViewSheet,
)

from craydl_bridge import __version__, check, host, params


def element_ids(values):
    return [ElementId(value) for value in values]


def is_template_path(path):
    return path.lower().endswith(".rte")


def utc_now():
    now = DateTime.UtcNow
    return "%04d-%02d-%02dT%02d:%02d:%02dZ" % (
        now.Year,
        now.Month,
        now.Day,
        now.Hour,
        now.Minute,
        now.Second,
    )


def write_text(path, text):
    with io.open(path, "w", encoding="utf-8") as stream:
        stream.write(text)


def _text(element, parameter):
    value = element.get_Parameter(parameter)
    return (value.AsString() or "") if value else ""


def _category(element):
    name = Enum.GetName(
        BuiltInCategory, Enum.ToObject(BuiltInCategory, element.Category.Id.Value)
    )
    return str(name) if name else ""


def _phase(element_id, phases):
    return phases.get(element_id.Value, "")


def _room_id(element, phases):
    for phase in reversed(phases):
        for lookup in (element.get_Room, element.get_FromRoom, element.get_ToRoom):
            try:
                room = lookup(phase)
            except Exception:
                # Some instances do not support every kind of room lookup.
                continue
            if room is not None:
                return room.UniqueId
    return ""


def _room(doc, room):
    level = doc.GetElement(room.LevelId)
    phase_id = room.get_Parameter(BuiltInParameter.ROOM_PHASE).AsElementId()
    phase = doc.GetElement(phase_id)
    return {
        "unique_id": room.UniqueId,
        # IronPython exposes ElementId.Value as a boxed Int64.
        "element_id": int(room.Id.Value),
        "name": _text(room, BuiltInParameter.ROOM_NAME),
        "number": room.Number or "",
        "level": (level.Name or "") if level is not None else "",
        "phase": (phase.Name or "") if phase is not None else "",
        "located": room.Location is not None,
        "area_sf": round(room.Area, 1),
        "stamp": host.read_stamp(room, params.PARAMETERS[1]["guid"]) or "",
    }


def _item(element, phases, phase_names):
    if element.Category is None or element.Category.CategoryType != CategoryType.Model:
        return None
    created = _phase(element.CreatedPhaseId, phase_names)
    if not created:
        return None
    symbol = element.Symbol
    return {
        "unique_id": element.UniqueId,
        "element_id": int(element.Id.Value),
        "nested": element.SuperComponent is not None,
        "in_place": bool(symbol.Family.IsInPlace),
        "category": _category(element),
        "family": symbol.FamilyName or "",
        "type": Element.Name.GetValue(symbol) or "",
        "manufacturer": _text(symbol, BuiltInParameter.ALL_MODEL_MANUFACTURER),
        "model": _text(symbol, BuiltInParameter.ALL_MODEL_MODEL),
        "url": _text(symbol, BuiltInParameter.ALL_MODEL_URL),
        "description": _text(symbol, BuiltInParameter.ALL_MODEL_DESCRIPTION),
        "created_phase": created,
        "demolished_phase": _phase(element.DemolishedPhaseId, phase_names),
        "room_unique_id": _room_id(element, phases),
    }


def _host(doc, element, phase_names):
    type_element = doc.GetElement(element.GetTypeId())
    key = (
        _category(element),
        (Element.Name.GetValue(type_element) or "") if type_element is not None else "",
        _phase(element.CreatedPhaseId, phase_names),
        _phase(element.DemolishedPhaseId, phase_names),
    )
    parameter = element.get_Parameter(BuiltInParameter.HOST_AREA_COMPUTED)
    return key, parameter.AsDouble() if parameter else 0.0


def _material_use(element, phase_names):
    if element.Category is None or element.Category.CategoryType != CategoryType.Model:
        return None
    phase = _phase(element.CreatedPhaseId, phase_names)
    if not phase:
        return None
    # Read both collections before counting; a failed element contributes nothing.
    material_ids = set(value.Value for value in element.GetMaterialIds(False))
    material_ids.update(value.Value for value in element.GetMaterialIds(True))
    return phase, material_ids


def _skip(element, skipped):
    # One unreadable element can be encountered by several independent collectors.
    try:
        key = ("element", element.Id.Value)
    except Exception:
        key = ("object", id(element))
    skipped.add(key)


def read_snapshot(doc, taken_at):
    host.require_project(doc)
    phases = list(doc.Phases)
    phase_names = dict((phase.Id.Value, phase.Name) for phase in phases)
    info = doc.ProjectInformation
    cloud_project_guid, cloud_model_guid = "", ""
    if doc.IsModelInCloud:
        try:
            cloud = doc.GetCloudModelPath()
            # Assign together: a failure reading either GUID leaves both empty.
            cloud_project_guid, cloud_model_guid = (
                cloud.GetProjectGUID().ToString(),
                cloud.GetModelGUID().ToString(),
            )
        except Exception:
            pass
    snapshot = {
        "schema": check.SCHEMA,
        "extension_version": __version__,
        "taken_at": taken_at,
        "model": {
            "title": doc.Title,
            "is_cloud": doc.IsModelInCloud,
            "is_workshared": doc.IsWorkshared,
            "is_template": is_template_path(doc.PathName),
            "cloud_project_guid": cloud_project_guid,
            "cloud_model_guid": cloud_model_guid,
            "job_id": host.read_stamp(info, params.PARAMETERS[0]["guid"]) or "",
            "set_up": all(
                row["action"] == "ok"
                for row in params.binding_plan(host.project_parameters(doc))
            ),
            "project_info": {
                "name": info.Name or "",
                "number": info.Number or "",
                "client_name": info.ClientName or "",
                "status": info.Status or "",
                "address": info.Address or "",
            },
        },
        "phases": host.phase_names(doc),
        "rooms": [],
        "items": [],
        "hosts": [],
        "materials": {"total": 0, "used": [], "repeated_names": []},
        "counts": {"skipped_elements": 0},
    }
    counts = snapshot["counts"]
    skipped = set()
    for room in (
        FilteredElementCollector(doc)
        .OfCategory(BuiltInCategory.OST_Rooms)
        .WhereElementIsNotElementType()
    ):
        try:
            row = _room(doc, room)
        except Exception:
            _skip(room, skipped)
            continue
        snapshot["rooms"].append(row)
    for element in FilteredElementCollector(doc).OfClass(FamilyInstance):
        try:
            row = _item(element, phases, phase_names)
        except Exception:
            _skip(element, skipped)
            continue
        if row is not None:
            snapshot["items"].append(row)
    groups = {}
    for category in (
        BuiltInCategory.OST_Walls,
        BuiltInCategory.OST_Floors,
        BuiltInCategory.OST_Ceilings,
        BuiltInCategory.OST_Roofs,
    ):
        for element in (
            FilteredElementCollector(doc)
            .OfCategory(category)
            .WhereElementIsNotElementType()
        ):
            try:
                key, area = _host(doc, element, phase_names)
            except Exception:
                _skip(element, skipped)
                continue
            group = groups.setdefault(key, {"count": 0, "area_sf": 0.0})
            group["count"] += 1
            group["area_sf"] += area
    for key in sorted(groups):
        group = groups[key]
        snapshot["hosts"].append(
            dict(
                zip(("category", "type", "created_phase", "demolished_phase"), key),
                count=group["count"],
                area_sf=round(group["area_sf"], 1),
            )
        )
    uses = {}
    for element in FilteredElementCollector(doc).WhereElementIsNotElementType():
        try:
            usage = _material_use(element, phase_names)
        except Exception:
            _skip(element, skipped)
            continue
        if usage is not None:
            phase, material_ids = usage
            for material_id in material_ids:
                by_phase = uses.setdefault(material_id, {})
                by_phase[phase] = by_phase.get(phase, 0) + 1
    names = {}
    for material in FilteredElementCollector(doc).OfClass(Material):
        snapshot["materials"]["total"] += 1
        try:
            name = material.Name or ""
            row = {
                "name": name,
                "material_class": material.MaterialClass or "",
                "manufacturer": _text(
                    material, BuiltInParameter.ALL_MODEL_MANUFACTURER
                ),
                "model": _text(material, BuiltInParameter.ALL_MODEL_MODEL),
                "uses": uses.get(material.Id.Value, {}),
            }
        except Exception:
            _skip(material, skipped)
            continue
        names[name] = names.get(name, 0) + 1
        if row["uses"]:
            snapshot["materials"]["used"].append(row)
    snapshot["materials"]["used"].sort(key=lambda row: row["name"])
    snapshot["materials"]["repeated_names"] = [
        {"name": name, "count": count}
        for name, count in sorted(names.items(), key=lambda pair: (-pair[1], pair[0]))
        if count > 1
    ][:20]
    for label, element_class in (
        ("shared_parameters", SharedParameterElement),
        ("links", RevitLinkInstance),
        ("point_clouds", PointCloudInstance),
        ("sheets", ViewSheet),
    ):
        counts[label] = (
            FilteredElementCollector(doc).OfClass(element_class).GetElementCount()
        )
    counts["skipped_elements"] = len(skipped)
    return snapshot
