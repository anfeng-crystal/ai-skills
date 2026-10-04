"""Package-local reference checks for removing a complete XML subtree.

Only observed scalar references and Fields/FieldId/Id references are covered;
expressions, source consumers and references outside the package need analysis.
"""

from __future__ import annotations

from typing import Any, Iterable
from xml.etree import ElementTree as ET

from metadata_knowledge import direct_properties, local_tag


REFERENCE_PROPERTIES = {
    "ParentId", "FieldId", "ListFieldId", "FieldName", "EntityId", "BaseEntityId",
    "MasterId", "ReferenceId", "ItemId", "OperationKey",
}
IDENTITY_PROPERTIES = {"Id", "PkId", "Key"}


def external_references(
    documents: Iterable[tuple[str, str, ET.Element]],
    node: ET.Element,
    inherited_properties: dict[str, Any] | None = None,
) -> list[dict[str, str]]:
    removed = set(node.iter())
    identities = set()
    for removed_node in removed:
        # A FieldId/Id is a reference holder, not an independently removed Id.
        if local_tag(removed_node.tag) in REFERENCE_PROPERTIES:
            continue
        props = dict(inherited_properties or {}) if removed_node is node else {}
        props.update(direct_properties(removed_node))
        identities.update(value for key, value in props.items()
                          if key in IDENTITY_PROPERTIES and value)
    if not identities:
        return []

    references = []
    for number, kind, root in documents:
        parents = {child: parent for parent in root.iter() for child in parent}
        for candidate in root.iter():
            if candidate in removed:
                continue
            props = direct_properties(candidate)
            matches = [(key, value) for key, value in props.items()
                       if key in REFERENCE_PROPERTIES]
            # Observed in standard form rules such as HideFieldAction/Fields.
            parent = parents.get(candidate)
            if (local_tag(candidate.tag) == "FieldId" and parent is not None
                    and local_tag(parent.tag) == "Fields"):
                matches.append(("FieldId.Id", props.get("Id", "")))
            for property_name, value in matches:
                if value not in identities:
                    continue
                references.append({
                    "unit": number,
                    "kind": kind,
                    "node_type": local_tag(candidate.tag),
                    "node_key": props.get("Key", ""),
                    "property": property_name,
                })
    return references
