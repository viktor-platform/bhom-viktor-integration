using System.Text.RegularExpressions;
using BH.oM.Data.Library;
using BH.oM.LifeCycleAssessment;
using BH.oM.LifeCycleAssessment.Fragments;
using BH.oM.LifeCycleAssessment.MaterialFragments;
using BHoMLibrary = BH.Engine.Library.Query;
using BHoMSerialiser = BH.Engine.Serialiser.Convert;

namespace BHoMMaterialLookupGateway;

public static partial class LookupRunner
{
    private static readonly Dictionary<string, string> LibraryPaths = new(StringComparer.OrdinalIgnoreCase)
    {
        ["All installed LCA datasets"] = "LifeCycleAssessment",
        ["ICE"] = "LifeCycleAssessment\\ICE",
        ["Boverket"] = "LifeCycleAssessment\\Boverket",
        ["EC3 snapshots"] = "LifeCycleAssessment\\EC3",
        ["EPiC"] = "LifeCycleAssessment\\EPiC",
        ["Oekobaudat"] = "LifeCycleAssessment\\Oekobaudat",
    };

    public static string Run(CommandLineOptions options, EventLog eventLog)
    {
        LookupRequest request = JsonIO.Read<LookupRequest>(options.RequestPath);
        Validate(request);
        PreloadPublishedAssemblies();
        string libraryPath = LibraryPaths[request.DatasetScope];

        List<Dataset> datasets = BHoMLibrary.Datasets(libraryPath);
        List<CatalogEntry> catalogue = datasets
            .SelectMany(dataset => dataset.Data
                .OfType<EnvironmentalProductDeclaration>()
                .Select(epd => new CatalogEntry(dataset.Name, epd)))
            .GroupBy(entry => entry.Epd.BHoM_Guid)
            .Select(group => group.First())
            .ToList();

        if (catalogue.Count == 0)
            throw new InvalidDataException(
                $"No EnvironmentalProductDeclaration objects were found at BHoM library path '{libraryPath}'."
            );

        eventLog.Note(
            "lookup.started",
            $"Searching {catalogue.Count} installed EPDs from {datasets.Count} BHoM datasets."
        );
        List<SearchResult> searches = request.Searches
            .Select(search => Search(search, catalogue, eventLog))
            .ToList();

        JsonIO.Write(options.OutputPath, new LookupResult
        {
            JobId = request.JobId,
            Source = new LookupSource
            {
                Dataset = request.DatasetScope,
                LibraryPath = libraryPath,
                DatasetCount = datasets.Count,
                EpdCount = catalogue.Count,
            },
            Searches = searches,
        });
        eventLog.Note(
            "lookup.completed",
            $"Returned {searches.Sum(item => item.Candidates.Count)} candidates from installed BHoM datasets."
        );
        return request.JobId;
    }

    private static void PreloadPublishedAssemblies()
    {
        foreach (string path in Directory.EnumerateFiles(AppContext.BaseDirectory, "*.dll"))
        {
            try
            {
                System.Reflection.Assembly.LoadFrom(path);
            }
            catch (BadImageFormatException)
            {
                // Native dependencies are ignored; BHoM managed assemblies are loaded.
            }
            catch (FileLoadException)
            {
                // An already loaded assembly is safe to reuse.
            }
        }
    }

    private static SearchResult Search(
        SearchRequest search,
        List<CatalogEntry> catalogue,
        EventLog eventLog
    )
    {
        List<LookupCandidate> candidates = catalogue
            .Select(entry => new RankedEntry(entry, MatchScore(search.Query, entry)))
            .Where(entry => entry.Score > 0)
            .OrderByDescending(entry => entry.Score)
            .ThenBy(entry => entry.Entry.Epd.Name, StringComparer.OrdinalIgnoreCase)
            .Take(search.Count)
            .Select(entry => ToCandidate(entry.Entry, entry.Score))
            .ToList();

        if (candidates.Count == 0)
            eventLog.Warning(
                "lookup.no_results",
                $"No installed BHoM EPDs matched '{search.Query}' for '{search.SourceMaterial}'."
            );

        return new SearchResult
        {
            SourceMaterial = search.SourceMaterial,
            Query = search.Query,
            Candidates = candidates,
        };
    }

    private static LookupCandidate ToCandidate(CatalogEntry entry, double score)
    {
        EnvironmentalProductDeclaration epd = entry.Epd;
        AdditionalEPDData? additional = epd.Fragments
            .OfType<AdditionalEPDData>()
            .FirstOrDefault();
        EPDDensity? density = epd.Fragments.OfType<EPDDensity>().FirstOrDefault();
        ClimateChangeTotalMetric? climate = epd.EnvironmentalMetrics
            .OfType<ClimateChangeTotalMetric>()
            .FirstOrDefault();
        double? a1ToA3 = null;
        if (climate is not null && climate.Indicators.TryGetValue(Module.A1toA3, out double value))
            a1ToA3 = double.IsFinite(value) ? value : null;

        return new LookupCandidate
        {
            CatalogId = epd.BHoM_Guid.ToString(),
            Name = epd.Name,
            DatasetName = entry.DatasetName,
            Description = additional?.Description ?? "",
            Manufacturer = additional?.Manufacturer ?? "",
            PlantName = additional?.PlantName ?? "",
            QuantityType = epd.QuantityType.ToString(),
            DensityKgM3 = density is not null && double.IsFinite(density.Density)
                ? density.Density
                : null,
            A1ToA3 = a1ToA3,
            MatchScore = Math.Round(score, 4),
            EpdJson = BHoMSerialiser.ToJson(epd),
        };
    }

    private static double MatchScore(string query, CatalogEntry entry)
    {
        string normalizedQuery = Normalize(query);
        if (normalizedQuery.Length == 0)
            return 0;

        string normalizedName = Normalize(entry.Epd.Name);
        AdditionalEPDData? additional = entry.Epd.Fragments
            .OfType<AdditionalEPDData>()
            .FirstOrDefault();
        string searchable = Normalize(string.Join(
            " ",
            entry.Epd.Name,
            entry.DatasetName,
            additional?.Description,
            additional?.Manufacturer,
            additional?.PlantName
        ));
        HashSet<string> queryTokens = Tokens(normalizedQuery);
        HashSet<string> nameTokens = Tokens(normalizedName);
        HashSet<string> searchableTokens = Tokens(searchable);

        double score = queryTokens.Count == 0
            ? 0
            : queryTokens.Count(token => searchableTokens.Contains(token)) / (double)queryTokens.Count;

        if (normalizedName == normalizedQuery)
            score += 3;
        else if (normalizedName.Contains(normalizedQuery, StringComparison.Ordinal)
            || normalizedQuery.Contains(normalizedName, StringComparison.Ordinal))
            score += 2;

        score += queryTokens.Count(token => nameTokens.Contains(token)) * 0.2;
        return score;
    }

    private static string Normalize(string? value) =>
        Whitespace().Replace(NonAlphaNumeric().Replace((value ?? "").ToLowerInvariant(), " "), " ").Trim();

    private static HashSet<string> Tokens(string normalized) =>
        normalized.Split(' ', StringSplitOptions.RemoveEmptyEntries)
            .Where(token => token.Length > 1)
            .ToHashSet(StringComparer.Ordinal);

    private static void Validate(LookupRequest request)
    {
        if (request.SchemaVersion != "1.0")
            throw new InvalidDataException("lookup request must use schema_version 1.0.");
        if (!Guid.TryParse(request.JobId, out _))
            throw new InvalidDataException("job_id must be a valid UUID.");
        if (!LibraryPaths.ContainsKey(request.DatasetScope))
            throw new InvalidDataException(
                "dataset_scope must be one of: " + string.Join(", ", LibraryPaths.Keys) + "."
            );
        if (request.Searches.Count is < 1 or > 100)
            throw new InvalidDataException("searches must contain between 1 and 100 items.");
        foreach (SearchRequest search in request.Searches)
        {
            if (string.IsNullOrWhiteSpace(search.SourceMaterial))
                throw new InvalidDataException("Every search requires source_material.");
            if (string.IsNullOrWhiteSpace(search.Query))
                throw new InvalidDataException("Every search requires query.");
            if (search.Count is < 1 or > 20)
                throw new InvalidDataException("Every search count must be between 1 and 20.");
        }
    }

    private sealed record CatalogEntry(
        string DatasetName,
        EnvironmentalProductDeclaration Epd
    );

    private sealed record RankedEntry(CatalogEntry Entry, double Score);

    [GeneratedRegex("[^a-z0-9]+")]
    private static partial Regex NonAlphaNumeric();

    [GeneratedRegex("\\s+")]
    private static partial Regex Whitespace();
}
