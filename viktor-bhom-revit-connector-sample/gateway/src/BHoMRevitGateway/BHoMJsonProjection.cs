using System.Text.Json;
using System.Text.Json.Nodes;

namespace BHoMRevitGateway;

public static class BHoMJsonProjection
{
    private const string MaterialTakeoffType =
        "BH.oM.Physical.Materials.VolumetricMaterialTakeoff";
    private const string ParameterType =
        "BH.oM.Adapters.Revit.Parameters.RevitPulledParameters";
    private const string IdentifierType =
        "BH.oM.Adapters.Revit.Parameters.RevitIdentifiers";

    public static JsonArray ParseElementArray(string serializedObjects)
    {
        JsonNode? node = JsonNode.Parse(serializedObjects);
        return node as JsonArray
            ?? throw new InvalidDataException(
                "The BHoM serializer did not return a JSON array."
            );
    }

    public static void RemovePulledParameters(JsonArray elements)
    {
        foreach (JsonObject element in elements.OfType<JsonObject>())
        {
            JsonArray? fragments = ResolveArray(element["Fragments"]);
            if (fragments is null)
            {
                continue;
            }

            for (int index = fragments.Count - 1; index >= 0; index--)
            {
                if (
                    fragments[index] is JsonObject fragment
                    && GetString(fragment, "_t") == ParameterType
                )
                {
                    fragments.RemoveAt(index);
                }
            }
        }
    }

    public static MetadataDocument BuildMetadata(
        JsonArray elements,
        PullRequest request,
        string documentName,
        string bHoMVersion
    )
    {
        return new MetadataDocument
        {
            JobId = request.JobId,
            Source = new MetadataSource
            {
                DocumentName = documentName,
                BHoMVersion = bHoMVersion,
            },
            Extraction = new ExtractionInfo
            {
                IncludeParameters = request.Options.IncludeParameters,
                IncludeMaterialTakeoff = request.Options.IncludeMaterialTakeoff,
                IncludeGeometry = request.Options.IncludeGeometry,
                Categories = [.. request.Filters.Categories],
            },
            Elements = elements
                .OfType<JsonObject>()
                .Select(BuildElementMetadata)
                .ToList(),
        };
    }

    public static JsonObject BuildGeneralMaterialTakeoff(
        JsonArray elements,
        string documentName
    )
    {
        Dictionary<string, MaterialAggregate> aggregates =
            new(StringComparer.Ordinal);
        foreach (JsonObject element in elements.OfType<JsonObject>())
        {
            foreach (MaterialLink link in ReadMaterialLinks(element))
            {
                string key = MaterialKey(link.Material);
                if (!aggregates.TryGetValue(key, out MaterialAggregate? aggregate))
                {
                    aggregate = new MaterialAggregate(link.Material);
                    aggregates.Add(key, aggregate);
                }

                aggregate.Volume += link.Volume;
                aggregate.Mass += link.Mass;
                aggregate.NumberItem += 1;
            }
        }

        JsonArray items = [];
        foreach (
            MaterialAggregate aggregate in aggregates.Values.OrderBy(
                item => GetString(item.Material, "Name"),
                StringComparer.Ordinal
            )
        )
        {
            items.Add(
                new JsonObject
                {
                    ["_t"] = "BH.oM.Physical.Materials.TakeoffItem",
                    ["Material"] = aggregate.Material.DeepClone(),
                    ["Volume"] = aggregate.Volume,
                    ["Mass"] = aggregate.Mass,
                    ["Area"] = 0.0,
                    ["Length"] = 0.0,
                    ["NumberItem"] = aggregate.NumberItem,
                    ["ElectricCurrent"] = 0.0,
                    ["Energy"] = 0.0,
                    ["Power"] = 0.0,
                    ["VolumetricFlowRate"] = 0.0,
                }
            );
        }

        return new JsonObject
        {
            ["_t"] = "BH.oM.Physical.Materials.GeneralMaterialTakeoff",
            ["Name"] = $"{documentName} aggregated Revit material takeoff",
            ["MaterialTakeoffItems"] = items,
        };
    }

    private static ElementMetadata BuildElementMetadata(JsonObject element)
    {
        JsonObject? identifiers = FindFragment(element, IdentifierType);
        JsonObject? parameters = FindFragment(element, ParameterType);
        List<ParameterMetadata> parameterItems = [];
        if (parameters is not null)
        {
            foreach (JsonObject item in Items(parameters["Parameters"]).OfType<JsonObject>())
            {
                parameterItems.Add(
                    new ParameterMetadata
                    {
                        Name = GetString(item, "Name"),
                        Value = ToPlainValue(item["Value"]),
                        Unit = GetNullableString(item, "Unit"),
                        IsReadOnly = GetBoolean(item, "IsReadOnly"),
                    }
                );
            }
        }

        return new ElementMetadata
        {
            BHoMGuid = GetString(element, "BHoM_Guid"),
            BHoMType = GetString(element, "_t"),
            Name = GetString(element, "Name"),
            Category = identifiers is null
                ? string.Empty
                : GetString(identifiers, "CategoryName"),
            Family = identifiers is null
                ? string.Empty
                : GetString(identifiers, "FamilyName"),
            FamilyType = identifiers is null
                ? string.Empty
                : GetString(identifiers, "FamilyTypeName"),
            RevitElementId = identifiers is null
                ? string.Empty
                : GetStringValue(identifiers["ElementId"]),
            RevitUniqueId = identifiers is null
                ? string.Empty
                : GetStringValue(identifiers["PersistentId"]),
            Parameters = parameterItems,
            Materials = ReadMaterialLinks(element)
                .Select(
                    link => new MaterialMetadata
                    {
                        Name = link.Name,
                        VolumeM3 = link.Volume,
                        MassKg = link.Mass,
                    }
                )
                .ToList(),
        };
    }

    private static List<MaterialLink> ReadMaterialLinks(JsonObject element)
    {
        JsonObject? takeoff = FindFragment(element, MaterialTakeoffType);
        if (takeoff is null)
        {
            return [];
        }

        List<JsonObject> materials = Items(takeoff["Materials"])
            .OfType<JsonObject>()
            .ToList();
        List<double> volumes = Items(takeoff["Volumes"])
            .Select(GetDoubleValue)
            .ToList();
        List<MaterialLink> links = [];
        for (int index = 0; index < Math.Min(materials.Count, volumes.Count); index++)
        {
            JsonObject material = materials[index];
            double volume = volumes[index];
            double density = GetDouble(material, "Density");
            links.Add(
                new MaterialLink(
                    material,
                    GetString(material, "Name"),
                    volume,
                    volume * density
                )
            );
        }

        return links;
    }

    private static JsonObject? FindFragment(JsonObject element, string type)
    {
        return Items(element["Fragments"])
            .OfType<JsonObject>()
            .FirstOrDefault(fragment => GetString(fragment, "_t") == type);
    }

    private static IEnumerable<JsonNode?> Items(JsonNode? node)
    {
        JsonArray? array = ResolveArray(node);
        return array ?? [];
    }

    private static JsonArray? ResolveArray(JsonNode? node)
    {
        if (node is JsonArray array)
        {
            return array;
        }

        return node is JsonObject wrapper ? wrapper["_v"] as JsonArray : null;
    }

    private static string MaterialKey(JsonObject material)
    {
        string guid = GetString(material, "BHoM_Guid");
        return !string.IsNullOrWhiteSpace(guid)
            ? guid
            : string.Join(
                "|",
                GetString(material, "_t"),
                GetString(material, "Name"),
                GetDouble(material, "Density").ToString("R")
            );
    }

    private static object? ToPlainValue(JsonNode? node)
    {
        return node is null
            ? null
            : JsonSerializer.Deserialize<object?>(node.ToJsonString());
    }

    private static string GetString(JsonObject value, string name) =>
        GetNullableString(value, name) ?? string.Empty;

    private static string? GetNullableString(JsonObject value, string name)
    {
        return value[name] is JsonValue node && node.TryGetValue(out string? text)
            ? text
            : null;
    }

    private static string GetStringValue(JsonNode? node)
    {
        if (node is null)
        {
            return string.Empty;
        }

        if (node is JsonValue value && value.TryGetValue(out string? text))
        {
            return text ?? string.Empty;
        }

        return node.ToJsonString().Trim('"');
    }

    private static double GetDouble(JsonObject value, string name) =>
        GetDoubleValue(value[name]);

    private static double GetDoubleValue(JsonNode? node)
    {
        return node is JsonValue value && value.TryGetValue(out double number)
            ? number
            : 0.0;
    }

    private static bool GetBoolean(JsonObject value, string name)
    {
        return value[name] is JsonValue node
            && node.TryGetValue(out bool boolean)
            && boolean;
    }

    private sealed class MaterialLink
    {
        public MaterialLink(
            JsonObject material,
            string name,
            double volume,
            double mass
        )
        {
            Material = material;
            Name = name;
            Volume = volume;
            Mass = mass;
        }

        public JsonObject Material { get; }
        public string Name { get; }
        public double Volume { get; }
        public double Mass { get; }
    }

    private sealed class MaterialAggregate(JsonObject material)
    {
        public JsonObject Material { get; } = material;
        public double Volume { get; set; }
        public double Mass { get; set; }
        public int NumberItem { get; set; }
    }
}
