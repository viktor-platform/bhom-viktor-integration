using System.Text.Json.Serialization;

namespace BHoMLcaGateway;

public sealed class AnalysisRequest
{
    [JsonPropertyName("schema_version")]
    public string SchemaVersion { get; init; } = string.Empty;

    [JsonPropertyName("job_id")]
    public string JobId { get; init; } = string.Empty;

    [JsonPropertyName("analysis_profile")]
    public string AnalysisProfile { get; init; } = string.Empty;

    [JsonPropertyName("takeoff_filename")]
    public string TakeoffFilename { get; init; } = string.Empty;

    [JsonPropertyName("template_materials_filename")]
    public string TemplateMaterialsFilename { get; init; } = string.Empty;

    [JsonPropertyName("prioritise_template_materials")]
    public bool PrioritiseTemplateMaterials { get; init; } = true;

    [JsonPropertyName("metric_filters")]
    public List<string> MetricFilters { get; init; } = [];

    [JsonPropertyName("modules")]
    public List<string> Modules { get; init; } = [];

    [JsonPropertyName("project")]
    public ProjectInfo Project { get; init; } = new();
}

public sealed class ProjectInfo
{
    [JsonPropertyName("project_id")]
    public string ProjectId { get; init; } = string.Empty;

    [JsonPropertyName("project_name")]
    public string ProjectName { get; init; } = string.Empty;

    [JsonPropertyName("gross_floor_area_m2")]
    public double? GrossFloorAreaM2 { get; init; }
}

public sealed class NormalizedResult
{
    [JsonPropertyName("schema_version")]
    public string SchemaVersion { get; init; } = "1.0";

    [JsonPropertyName("job_id")]
    public string JobId { get; init; } = string.Empty;

    [JsonPropertyName("status")]
    public string Status { get; init; } = "completed";

    [JsonPropertyName("project")]
    public ProjectInfo Project { get; init; } = new();

    [JsonPropertyName("summary")]
    public ResultSummary Summary { get; init; } = new();

    [JsonPropertyName("records")]
    public List<ResultRecord> Records { get; init; } = [];

    [JsonPropertyName("unmatched_materials")]
    public List<string> UnmatchedMaterials { get; init; } = [];

    [JsonPropertyName("warnings")]
    public List<string> Warnings { get; init; } = [];
}

public sealed class ResultSummary
{
    [JsonPropertyName("total_kgco2e")]
    public double TotalKgCo2E { get; init; }

    [JsonPropertyName("total_tco2e")]
    public double TotalTCo2E { get; init; }

    [JsonPropertyName("carbon_intensity_kgco2e_m2")]
    public double? CarbonIntensityKgCo2EPerM2 { get; init; }

    [JsonPropertyName("record_count")]
    public int RecordCount { get; init; }

    [JsonPropertyName("unmatched_material_count")]
    public int UnmatchedMaterialCount { get; init; }
}

public sealed class ResultRecord
{
    [JsonPropertyName("material")]
    public string Material { get; init; } = string.Empty;

    [JsonPropertyName("environmental_product_declaration")]
    public string EnvironmentalProductDeclaration { get; init; } = string.Empty;

    [JsonPropertyName("metric")]
    public string Metric { get; init; } = string.Empty;

    [JsonPropertyName("module")]
    public string Module { get; init; } = string.Empty;

    [JsonPropertyName("value")]
    public double Value { get; init; }

    [JsonPropertyName("unit")]
    public string Unit { get; init; } = string.Empty;
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

    [JsonPropertyName("assemblies")]
    public List<AssemblyManifestItem> Assemblies { get; init; } = [];
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
