using System.Text.Json.Serialization;

namespace BHoMRevitGateway;

public sealed class PullRequest
{
    [JsonPropertyName("schema_version")]
    public string SchemaVersion { get; init; } = string.Empty;

    [JsonPropertyName("job_id")]
    public string JobId { get; init; } = string.Empty;

    [JsonPropertyName("operation")]
    public string Operation { get; init; } = string.Empty;

    [JsonPropertyName("revit_version")]
    public string RevitVersion { get; init; } = string.Empty;

    [JsonPropertyName("expected_document_name")]
    public string? ExpectedDocumentName { get; init; }

    [JsonPropertyName("filters")]
    public PullFilters Filters { get; init; } = new();

    [JsonPropertyName("options")]
    public PullOptions Options { get; init; } = new();
}

public sealed class PullFilters
{
    [JsonPropertyName("categories")]
    public List<string> Categories { get; init; } = [];
}

public sealed class PullOptions
{
    [JsonPropertyName("include_parameters")]
    public bool IncludeParameters { get; init; } = true;

    [JsonPropertyName("include_material_takeoff")]
    public bool IncludeMaterialTakeoff { get; init; } = true;

    [JsonPropertyName("include_geometry")]
    public bool IncludeGeometry { get; init; }

    [JsonPropertyName("element_limit")]
    public int ElementLimit { get; init; } = 2500;
}

public sealed class MetadataDocument
{
    [JsonPropertyName("schema_version")]
    public string SchemaVersion { get; init; } = "1.0";

    [JsonPropertyName("job_id")]
    public string JobId { get; init; } = string.Empty;

    [JsonPropertyName("source")]
    public MetadataSource Source { get; init; } = new();

    [JsonPropertyName("extraction")]
    public ExtractionInfo Extraction { get; init; } = new();

    [JsonPropertyName("elements")]
    public List<ElementMetadata> Elements { get; init; } = [];
}

public sealed class MetadataSource
{
    [JsonPropertyName("application")]
    public string Application { get; init; } = "Autodesk Revit";

    [JsonPropertyName("revit_version")]
    public string RevitVersion { get; init; } = "2025";

    [JsonPropertyName("document_name")]
    public string DocumentName { get; init; } = string.Empty;

    [JsonPropertyName("bhom_version")]
    public string BHoMVersion { get; init; } = string.Empty;

    [JsonPropertyName("mode")]
    public string Mode { get; init; } = "live Revit listener";
}

public sealed class ExtractionInfo
{
    [JsonPropertyName("read_only")]
    public bool ReadOnly { get; init; } = true;

    [JsonPropertyName("include_parameters")]
    public bool IncludeParameters { get; init; }

    [JsonPropertyName("include_material_takeoff")]
    public bool IncludeMaterialTakeoff { get; init; } = true;

    [JsonPropertyName("include_geometry")]
    public bool IncludeGeometry { get; init; }

    [JsonPropertyName("categories")]
    public List<string> Categories { get; init; } = [];
}

public sealed class ElementMetadata
{
    [JsonPropertyName("bhom_guid")]
    public string BHoMGuid { get; init; } = string.Empty;

    [JsonPropertyName("bhom_type")]
    public string BHoMType { get; init; } = string.Empty;

    [JsonPropertyName("name")]
    public string Name { get; init; } = string.Empty;

    [JsonPropertyName("category")]
    public string Category { get; init; } = string.Empty;

    [JsonPropertyName("family")]
    public string Family { get; init; } = string.Empty;

    [JsonPropertyName("family_type")]
    public string FamilyType { get; init; } = string.Empty;

    [JsonPropertyName("revit_element_id")]
    public string RevitElementId { get; init; } = string.Empty;

    [JsonPropertyName("revit_unique_id")]
    public string RevitUniqueId { get; init; } = string.Empty;

    [JsonPropertyName("parameters")]
    public List<ParameterMetadata> Parameters { get; init; } = [];

    [JsonPropertyName("materials")]
    public List<MaterialMetadata> Materials { get; init; } = [];
}

public sealed class ParameterMetadata
{
    [JsonPropertyName("name")]
    public string Name { get; init; } = string.Empty;

    [JsonPropertyName("value")]
    public object? Value { get; init; }

    [JsonPropertyName("unit")]
    public string? Unit { get; init; }

    [JsonPropertyName("is_read_only")]
    public bool IsReadOnly { get; init; }
}

public sealed class MaterialMetadata
{
    [JsonPropertyName("name")]
    public string Name { get; init; } = string.Empty;

    [JsonPropertyName("volume_m3")]
    public double VolumeM3 { get; init; }

    [JsonPropertyName("mass_kg")]
    public double MassKg { get; init; }
}

public sealed class GatewayEvent
{
    [JsonPropertyName("timestamp_utc")]
    public DateTimeOffset TimestampUtc { get; init; }

    [JsonPropertyName("severity")]
    public string Severity { get; init; } = string.Empty;

    [JsonPropertyName("code")]
    public string Code { get; init; } = string.Empty;

    [JsonPropertyName("message")]
    public string Message { get; init; } = string.Empty;
}

public sealed class EventDocument
{
    [JsonPropertyName("schema_version")]
    public string SchemaVersion { get; init; } = "1.0";

    [JsonPropertyName("job_id")]
    public string? JobId { get; init; }

    [JsonPropertyName("events")]
    public List<GatewayEvent> Events { get; init; } = [];
}

public sealed class RuntimeManifest
{
    [JsonPropertyName("schema_version")]
    public string SchemaVersion { get; init; } = "1.0";

    [JsonPropertyName("generated_at_utc")]
    public DateTimeOffset GeneratedAtUtc { get; init; }

    [JsonPropertyName("gateway_version")]
    public string GatewayVersion { get; init; } = string.Empty;

    [JsonPropertyName("dotnet_version")]
    public string DotnetVersion { get; init; } = string.Empty;

    [JsonPropertyName("operating_system")]
    public string OperatingSystem { get; init; } = string.Empty;

    [JsonPropertyName("revit")]
    public RevitRuntimeInfo Revit { get; init; } = new();

    [JsonPropertyName("assemblies")]
    public List<AssemblyManifestItem> Assemblies { get; init; } = [];
}

public sealed class RevitRuntimeInfo
{
    [JsonPropertyName("version")]
    public string Version { get; init; } = "2025";

    [JsonPropertyName("listener_process_detected")]
    public bool ListenerProcessDetected { get; init; }

    [JsonPropertyName("push_port")]
    public int PushPort { get; init; } = 14128;

    [JsonPropertyName("pull_port")]
    public int PullPort { get; init; } = 14129;
}

public sealed class AssemblyManifestItem
{
    [JsonPropertyName("name")]
    public string Name { get; init; } = string.Empty;

    [JsonPropertyName("version")]
    public string Version { get; init; } = string.Empty;

    [JsonPropertyName("file")]
    public string File { get; init; } = string.Empty;

    [JsonPropertyName("sha256")]
    public string Sha256 { get; init; } = string.Empty;
}
