"""
Seed: ISA-95 / B2MML object model attributes.

Source : B2MML (Business To Manufacturing Markup Language), the open XML
         implementation of ANSI/ISA-95 maintained by MESA International.
Repo   : https://github.com/MESAInternational/B2MML-BatchML  (Schema/*.xsd)
Version: B2MML V0701 (based on ANSI/ISA-95.00.02-2018 Part 2 Object Model).
License: Royalty-free use granted by MESA International (see repo LICENSE).

Field definitions were extracted directly from the published XSD complexTypes
(PersonType, EquipmentType, MaterialDefinitionType, MaterialLotType, etc.).
Base-type mapping verified against B2MML-CoreComponents.xsd:
    IdentifierType / DescriptionType -> string  (VARCHAR)
    DateTimeType                     -> dateTime (DATETIME)
    ValueType / QuantityValueType    -> composite value+UoM (modelled as OBJECT)
    *Type (nested objects)           -> OBJECT (nested ISA-95 structure)
"""

SRC_STD = "ISA-95 (B2MML)"
SRC_BASE = ("https://github.com/MESAInternational/B2MML-BatchML/blob/master/"
            "Schema/")
VERSION = "B2MML V0701 / ISA-95.00.02-2018"

# xsd-type -> (SQL DataType, note appended to description if composite/object)
TYPE_MAP = {
    "IdentifierType": ("VARCHAR", None),
    "DescriptionType": ("VARCHAR", None),
    "DateTimeType": ("DATETIME", None),
    "ValueType": ("OBJECT", "Composite value (ValueString + DataType + UnitOfMeasure)."),
    "QuantityValueType": ("OBJECT", "Composite quantity (QuantityString + DataType + UnitOfMeasure)."),
}
# Any other *Type is a nested ISA-95 object structure.
def _map_type(xsd_type):
    if xsd_type in TYPE_MAP:
        return TYPE_MAP[xsd_type]
    return ("OBJECT", f"Nested ISA-95 structure ({xsd_type}).")


CATEGORIES = [
    {"name": "Manufacturing",
     "description": "Production operations, process segments and shop-floor execution.",
     "source": "ISA-95 / B2MML"},
    {"name": "Human Resources",
     "description": "Personnel, roles and workforce master data.",
     "source": "ISA-95 / B2MML; Odoo; ERPNext"},
    {"name": "Maintenance / Asset Management",
     "description": "Equipment, physical assets and their maintenance.",
     "source": "ISA-95 / B2MML"},
    {"name": "Product Master Data",
     "description": "Material/product definitions and classifications.",
     "source": "ISA-95 / B2MML; Schema.org; GS1"},
    {"name": "Inventory / Warehouse",
     "description": "Material lots, sub-lots, quantities and storage locations.",
     "source": "ISA-95 / B2MML"},
]

# Reusable descriptions for the ISA-95 common header attributes.
_C = {
    "ID": "Unique identifier of the object within its hierarchy scope.",
    "Version": "Version identifier of the object definition.",
    "Description": "Human-readable description (language-tagged, repeatable).",
    "PublishedDate": "Date/time the object information was published.",
    "EffectiveStartDate": "Date/time the object definition becomes effective.",
    "EffectiveEndDate": "Date/time the object definition stops being effective.",
    "HierarchyScope": "Location of this object within the role-based equipment hierarchy.",
    "SpatialDefinition": "Spatial/geometric definition of the object.",
    "TestSpecificationID": "Reference to an associated test/QA specification.",
}

# Each object: (object_label, category, [ (field, xsd_type, required, multi, desc) ])
_OBJECTS = [
    ("Person", "Human Resources", [
        ("ID", "IdentifierType", True, False, _C["ID"]),
        ("Version", "IdentifierType", False, False, _C["Version"]),
        ("Description", "DescriptionType", False, True, _C["Description"]),
        ("PublishedDate", "DateTimeType", False, False, _C["PublishedDate"]),
        ("EffectiveStartDate", "DateTimeType", False, False, _C["EffectiveStartDate"]),
        ("EffectiveEndDate", "DateTimeType", False, False, _C["EffectiveEndDate"]),
        ("HierarchyScope", "HierarchyScopeType", False, False, _C["HierarchyScope"]),
        ("PersonName", "PersonNameType", False, False, "Name of the individual."),
        ("SpatialDefinition", "SpatialDefinitionType", False, False, _C["SpatialDefinition"]),
        ("OperationalLocation", "ResourceLocationType", False, False, "Operational location assigned to the person."),
        ("PersonProperty", "PersonPropertyType", False, True, "Additional property/value of the person."),
        ("PersonnelClassID", "IdentifierType", False, True, "Reference to a personnel class this person belongs to."),
        ("TestSpecificationID", "IdentifierType", False, True, _C["TestSpecificationID"]),
    ]),
    ("PersonnelClass", "Human Resources", [
        ("ID", "IdentifierType", True, False, _C["ID"]),
        ("Version", "IdentifierType", False, False, _C["Version"]),
        ("Description", "DescriptionType", False, True, _C["Description"]),
        ("PublishedDate", "DateTimeType", False, False, _C["PublishedDate"]),
        ("EffectiveStartDate", "DateTimeType", False, False, _C["EffectiveStartDate"]),
        ("EffectiveEndDate", "DateTimeType", False, False, _C["EffectiveEndDate"]),
        ("HierarchyScope", "HierarchyScopeType", False, False, _C["HierarchyScope"]),
        ("PersonnelClassBaseID", "IdentifierType", False, True, "Reference to a parent personnel class (specialization)."),
        ("PersonnelClassProperty", "PersonnelClassPropertyType", False, True, "Property/value shared by the personnel class."),
        ("PersonSourceID", "IdentifierType", False, True, "Reference to a member person of this class."),
        ("TestSpecificationID", "IdentifierType", False, True, _C["TestSpecificationID"]),
    ]),
    ("Equipment", "Maintenance / Asset Management", [
        ("ID", "IdentifierType", True, False, _C["ID"]),
        ("Version", "IdentifierType", False, False, _C["Version"]),
        ("Description", "DescriptionType", False, True, _C["Description"]),
        ("PublishedDate", "DateTimeType", False, False, _C["PublishedDate"]),
        ("EffectiveStartDate", "DateTimeType", False, False, _C["EffectiveStartDate"]),
        ("EffectiveEndDate", "DateTimeType", False, False, _C["EffectiveEndDate"]),
        ("HierarchyScope", "HierarchyScopeType", False, False, _C["HierarchyScope"]),
        ("EquipmentLevel", "EquipmentLevelType", False, False, "Role-based level: Enterprise, Site, Area, ProcessCell, Unit, ProductionLine, WorkCell, etc."),
        ("SpatialDefinition", "SpatialDefinitionType", False, False, _C["SpatialDefinition"]),
        ("EquipmentAssetMapping", "EquipmentAssetMappingType", False, True, "Mapping of equipment to physical asset over time."),
        ("PhysicalAssetID", "IdentifierType", False, False, "Reference to the physical asset realizing this equipment."),
        ("OperationalLocation", "ResourceLocationType", False, False, "Operational location of the equipment."),
        ("EquipmentProperty", "EquipmentPropertyType", False, True, "Additional property/value of the equipment."),
        ("EquipmentChild", "EquipmentType", False, True, "Child equipment within this equipment."),
        ("EquipmentClassID", "IdentifierType", False, True, "Reference to an equipment class this equipment belongs to."),
        ("TestSpecificationID", "IdentifierType", False, True, _C["TestSpecificationID"]),
    ]),
    ("EquipmentClass", "Maintenance / Asset Management", [
        ("ID", "IdentifierType", True, False, _C["ID"]),
        ("Version", "IdentifierType", False, False, _C["Version"]),
        ("Description", "DescriptionType", False, True, _C["Description"]),
        ("PublishedDate", "DateTimeType", False, False, _C["PublishedDate"]),
        ("EffectiveStartDate", "DateTimeType", False, False, _C["EffectiveStartDate"]),
        ("EffectiveEndDate", "DateTimeType", False, False, _C["EffectiveEndDate"]),
        ("HierarchyScope", "HierarchyScopeType", False, False, _C["HierarchyScope"]),
        ("EquipmentLevel", "EquipmentLevelType", False, False, "Role-based equipment level the class applies to."),
        ("EquipmentClassProperty", "EquipmentClassPropertyType", False, True, "Property/value shared by the equipment class."),
        ("EquipmentClassChild", "EquipmentClassType", False, True, "Child equipment class."),
        ("EquipmentClassBaseID", "IdentifierType", False, True, "Reference to a parent equipment class (specialization)."),
        ("EquipmentSourceID", "IdentifierType", False, True, "Reference to a member equipment of this class."),
        ("TestSpecificationID", "IdentifierType", False, True, _C["TestSpecificationID"]),
    ]),
    ("MaterialClass", "Product Master Data", [
        ("ID", "IdentifierType", True, False, _C["ID"]),
        ("Version", "IdentifierType", False, False, _C["Version"]),
        ("Description", "DescriptionType", False, True, _C["Description"]),
        ("PublishedDate", "DateTimeType", False, False, _C["PublishedDate"]),
        ("EffectiveStartDate", "DateTimeType", False, False, _C["EffectiveStartDate"]),
        ("EffectiveEndDate", "DateTimeType", False, False, _C["EffectiveEndDate"]),
        ("HierarchyScope", "HierarchyScopeType", False, False, _C["HierarchyScope"]),
        ("MaterialClassBaseID", "IdentifierType", False, True, "Reference to a parent material class (specialization)."),
        ("MaterialClassProperty", "MaterialClassPropertyType", False, True, "Property/value shared by the material class."),
        ("MaterialDefinitionSourceID", "IdentifierType", False, True, "Reference to a member material definition."),
        ("TestSpecificationID", "IdentifierType", False, True, _C["TestSpecificationID"]),
        ("AssemblyType", "AssemblyTypeType", False, False, "Type of assembly: Physical or Logical."),
        ("AssemblyRelationship", "AssemblyRelationshipType", False, False, "Relationship to assembly members: Permanent or Transient."),
    ]),
    ("MaterialDefinition", "Product Master Data", [
        ("ID", "IdentifierType", True, False, _C["ID"]),
        ("Version", "IdentifierType", False, False, _C["Version"]),
        ("Description", "DescriptionType", False, True, _C["Description"]),
        ("PublishedDate", "DateTimeType", False, False, _C["PublishedDate"]),
        ("EffectiveStartDate", "DateTimeType", False, False, _C["EffectiveStartDate"]),
        ("EffectiveEndDate", "DateTimeType", False, False, _C["EffectiveEndDate"]),
        ("HierarchyScope", "HierarchyScopeType", False, False, _C["HierarchyScope"]),
        ("SpatialDefinition", "SpatialDefinitionType", False, False, _C["SpatialDefinition"]),
        ("MaterialDefinitionProperty", "MaterialDefinitionPropertyType", False, True, "Property/value of the material definition."),
        ("MaterialClassID", "IdentifierType", False, True, "Reference to a material class this definition belongs to."),
        ("MaterialLotSourceID", "IdentifierType", False, True, "Reference to a material lot of this definition."),
        ("TestSpecificationID", "IdentifierType", False, True, _C["TestSpecificationID"]),
        ("AssemblyType", "AssemblyTypeType", False, False, "Type of assembly: Physical or Logical."),
        ("AssemblyRelationship", "AssemblyRelationshipType", False, False, "Relationship to assembly members: Permanent or Transient."),
    ]),
    ("MaterialLot", "Inventory / Warehouse", [
        ("ID", "IdentifierType", True, False, _C["ID"]),
        ("Version", "IdentifierType", False, False, _C["Version"]),
        ("Description", "DescriptionType", False, True, _C["Description"]),
        ("PublishedDate", "DateTimeType", False, False, _C["PublishedDate"]),
        ("EffectiveStartDate", "DateTimeType", False, False, _C["EffectiveStartDate"]),
        ("EffectiveEndDate", "DateTimeType", False, False, _C["EffectiveEndDate"]),
        ("HierarchyScope", "HierarchyScopeType", False, False, _C["HierarchyScope"]),
        ("SpatialDefinition", "SpatialDefinitionType", False, False, _C["SpatialDefinition"]),
        ("MaterialDefinitionID", "IdentifierType", False, False, "Reference to the material definition of this lot."),
        ("Status", "StatusType", False, False, "Current status of the material lot."),
        ("Disposition", "DispositionType", False, False, "Quality/availability disposition of the lot."),
        ("MaterialLotProperty", "MaterialLotPropertyType", False, True, "Property/value of the material lot."),
        ("MaterialSubLot", "MaterialSubLotType", False, True, "Sub-lots contained within this lot."),
        ("StorageLocation", "ResourceLocationType", False, False, "Storage location of the lot."),
        ("Quantity", "QuantityValueType", False, True, "Quantity of material in the lot (with unit of measure)."),
        ("TestSpecificationID", "IdentifierType", False, True, _C["TestSpecificationID"]),
    ]),
    ("MaterialSubLot", "Inventory / Warehouse", [
        ("ID", "IdentifierType", True, False, _C["ID"]),
        ("Version", "IdentifierType", False, False, _C["Version"]),
        ("Description", "DescriptionType", False, True, _C["Description"]),
        ("HierarchyScope", "HierarchyScopeType", False, False, _C["HierarchyScope"]),
        ("SpatialDefinition", "SpatialDefinitionType", False, False, _C["SpatialDefinition"]),
        ("Status", "StatusType", False, False, "Current status of the sub-lot."),
        ("Disposition", "DispositionType", False, False, "Quality/availability disposition of the sub-lot."),
        ("StorageLocation", "ResourceLocationType", False, False, "Storage location of the sub-lot."),
        ("Quantity", "QuantityValueType", False, True, "Quantity of material in the sub-lot (with unit of measure)."),
        ("MaterialSubLotChild", "MaterialSubLotType", False, True, "Nested child sub-lots."),
        ("MaterialLotID", "IdentifierType", False, False, "Reference to the parent material lot."),
    ]),
    ("ProcessSegment", "Manufacturing", [
        ("ID", "IdentifierType", True, False, _C["ID"]),
        ("Description", "DescriptionType", False, True, _C["Description"]),
        ("Version", "IdentifierType", False, False, _C["Version"]),
        ("PublishedDate", "DateTimeType", False, False, _C["PublishedDate"]),
        ("EffectiveStartDate", "DateTimeType", False, False, _C["EffectiveStartDate"]),
        ("EffectiveEndDate", "DateTimeType", False, False, _C["EffectiveEndDate"]),
        ("OperationsType", "OperationsTypeType", False, False, "Operations type: Production, Maintenance, Quality, Inventory, Mixed, Other."),
        ("HierarchyScope", "HierarchyScopeType", False, False, _C["HierarchyScope"]),
        ("DefinitionType", "DefinitionTypeType", False, False, "Whether the segment is a definition or an instance."),
        ("PersonnelSegmentSpecification", "PersonnelSegmentSpecificationType", False, True, "Personnel resources required by the segment."),
        ("EquipmentSegmentSpecification", "EquipmentSegmentSpecificationType", False, True, "Equipment resources required by the segment."),
        ("MaterialSegmentSpecification", "MaterialSegmentSpecificationType", False, True, "Material resources consumed/produced by the segment."),
        ("ProcessSegmentParameter", "ParameterType", False, True, "Parameter applicable to the process segment."),
        ("SegmentDependency", "SegmentDependencyType", False, True, "Ordering/timing dependency between segments."),
        ("ProcessSegmentChild", "ProcessSegmentType", False, True, "Child process segment."),
    ]),
]


def _build():
    items = []
    for obj, category, fields in _OBJECTS:
        for (fname, xtype, required, multi, desc) in fields:
            data_type, note = _map_type(xtype)
            full_desc = desc
            if note:
                full_desc = f"{desc} {note}".strip()
            if multi:
                full_desc += " (repeatable / collection)"
            items.append({
                "category": category,
                "name": f"{obj}.{fname}",
                "title": f"{obj} {fname}",
                "description": full_desc,
                "data_type": data_type,
                "is_required": required,
                "is_nullable": not required,
                "source_standard": SRC_STD,
                "source_url": f"{SRC_BASE}B2MML-{_file_for(obj)}.xsd",
                "version": VERSION,
            })
    return items


def _file_for(obj):
    if obj in ("Person", "PersonnelClass"):
        return "Personnel"
    if obj in ("Equipment", "EquipmentClass"):
        return "Equipment"
    if obj in ("MaterialClass", "MaterialDefinition", "MaterialLot", "MaterialSubLot"):
        return "Material"
    if obj == "ProcessSegment":
        return "ProcessSegment"
    return "Common"


ITEMS = _build()
