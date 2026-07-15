using System.Text.Json.Serialization;

namespace BHoMMaterialLookupGateway;

public sealed class LookupRequest
{
    [JsonPropertyName("schema_version")]
    public string SchemaVersion { get; init; } = "";
    [JsonPropertyName("job_id")]
    public string JobId { get; init; } = "";
    [JsonPropertyName("dataset_scope")]
    public string DatasetScope { get; init; } = "All installed LCA datasets";
    [JsonPropertyName("searches")]
    public List<SearchRequest> Searches { get; init; } = [];
}

public sealed class SearchRequest
{
    [JsonPropertyName("source_material")]
    public string SourceMaterial { get; init; } = "";
    [JsonPropertyName("query")]
    public string Query { get; init; } = "";
    [JsonPropertyName("count")]
    public int Count { get; init; } = 8;
}

public sealed class LookupResult
{
    [JsonPropertyName("schema_version")]
    public string SchemaVersion { get; init; } = "1.0";
    [JsonPropertyName("job_id")]
    public string JobId { get; init; } = "";
    [JsonPropertyName("status")]
    public string Status { get; init; } = "completed";
    [JsonPropertyName("source")]
    public LookupSource Source { get; init; } = new();
    [JsonPropertyName("searches")]
    public List<SearchResult> Searches { get; init; } = [];
}

public sealed class LookupSource
{
    [JsonPropertyName("dataset")]
    public string Dataset { get; init; } = "Installed BHoM LCA datasets";
    [JsonPropertyName("toolkit")]
    public string Toolkit { get; init; } = "BHoM Library_Engine";
    [JsonPropertyName("library_path")]
    public string LibraryPath { get; init; } = "LifeCycleAssessment";
    [JsonPropertyName("dataset_count")]
    public int DatasetCount { get; init; }
    [JsonPropertyName("epd_count")]
    public int EpdCount { get; init; }
}

public sealed class SearchResult
{
    [JsonPropertyName("source_material")]
    public string SourceMaterial { get; init; } = "";
    [JsonPropertyName("query")]
    public string Query { get; init; } = "";
    [JsonPropertyName("candidates")]
    public List<LookupCandidate> Candidates { get; init; } = [];
}

public sealed class LookupCandidate
{
    [JsonPropertyName("catalog_id")]
    public string CatalogId { get; init; } = "";
    [JsonPropertyName("name")]
    public string Name { get; init; } = "";
    [JsonPropertyName("dataset_name")]
    public string DatasetName { get; init; } = "";
    [JsonPropertyName("description")]
    public string Description { get; init; } = "";
    [JsonPropertyName("manufacturer")]
    public string Manufacturer { get; init; } = "";
    [JsonPropertyName("plant_name")]
    public string PlantName { get; init; } = "";
    [JsonPropertyName("quantity_type")]
    public string QuantityType { get; init; } = "";
    [JsonPropertyName("density_kg_m3")]
    public double? DensityKgM3 { get; init; }
    [JsonPropertyName("a1toa3_kgco2e_per_declared_unit")]
    public double? A1ToA3 { get; init; }
    [JsonPropertyName("match_score")]
    public double MatchScore { get; init; }
    [JsonPropertyName("epd_json")]
    public string EpdJson { get; init; } = "";
}

public sealed class GatewayEvent
{
    [JsonPropertyName("timestamp_utc")]
    public DateTimeOffset TimestampUtc { get; init; }
    [JsonPropertyName("severity")]
    public string Severity { get; init; } = "";
    [JsonPropertyName("code")]
    public string Code { get; init; } = "";
    [JsonPropertyName("message")]
    public string Message { get; init; } = "";
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
    public string GatewayVersion { get; init; } = "";
    [JsonPropertyName("dotnet_version")]
    public string DotnetVersion { get; init; } = "";
    [JsonPropertyName("operating_system")]
    public string OperatingSystem { get; init; } = "";
    [JsonPropertyName("dataset_root")]
    public string DatasetRoot { get; init; } = "";
    [JsonPropertyName("dataset_files")]
    public int DatasetFiles { get; init; }
    [JsonPropertyName("assemblies")]
    public List<string> Assemblies { get; init; } = [];
}
