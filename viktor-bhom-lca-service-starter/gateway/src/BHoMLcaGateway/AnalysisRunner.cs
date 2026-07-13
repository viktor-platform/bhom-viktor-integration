using BH.Engine.LifeCycleAssessment;
using BH.oM.LifeCycleAssessment;
using BH.oM.LifeCycleAssessment.Results;
using BH.oM.Physical.Materials;
using BHoMSerialiser = BH.Engine.Serialiser.Convert;

namespace BHoMLcaGateway;

public static class AnalysisRunner
{
    private const string SupportedProfile =
        "general_environmental_results";

    public static string Run(
        CommandLineOptions options,
        EventLog eventLog
    )
    {
        AnalysisRequest request = JsonIO.Read<AnalysisRequest>(
            options.RequestPath
        );
        ValidateRequest(request);

        IReadOnlyList<string> modules = ModuleSelection.Validate(
            request.Modules
        );

        string takeoffJson = JsonIO.ReadText(request.TakeoffFilename);
        object? takeoffObject = BHoMSerialiser.FromJson(takeoffJson);
        GeneralMaterialTakeoff takeoff =
            takeoffObject as GeneralMaterialTakeoff
            ?? throw new InvalidDataException(
                $"'{request.TakeoffFilename}' did not deserialize as "
                + "BH.oM.Physical.Materials.GeneralMaterialTakeoff."
            );

        string templateJson = JsonIO.ReadText(
            request.TemplateMaterialsFilename
        );
        IEnumerable<object>? deserializedTemplateObjects =
            BHoMSerialiser.FromJsonArray(templateJson);
        List<object> templateObjects =
            deserializedTemplateObjects?.ToList()
            ?? throw new InvalidDataException(
                $"'{request.TemplateMaterialsFilename}' could not be "
                + "deserialized as a JSON array."
            );

        if (templateObjects.Any(item => item is not Material))
        {
            string invalidTypes = string.Join(
                ", ",
                templateObjects
                    .Where(item => item is not Material)
                    .Select(item => item?.GetType().FullName ?? "null")
                    .Distinct(StringComparer.Ordinal)
            );
            throw new InvalidDataException(
                "Every template array item must deserialize as "
                + "BH.oM.Physical.Materials.Material. Invalid types: "
                + invalidTypes
            );
        }

        List<Material> templates = templateObjects
            .Cast<Material>()
            .ToList();

        List<MetricType> metrics = ParseMetrics(request.MetricFilters);
        eventLog.Note(
            "analysis.started",
            $"Running {SupportedProfile} for job '{request.JobId}'."
        );

        List<MaterialResult> results = takeoff.EnvironmentalResults(
            templateMaterials: templates,
            prioritiseTemplate: request.PrioritiseTemplateMaterials,
            metricFilter: metrics,
            evaluationConfig: null
        );

        if (results.Count == 0)
        {
            eventLog.Warning(
                "analysis.no_results",
                "BHoM returned no material results for the selected metric."
            );
        }

        string rawJson = BHoMSerialiser.ToJsonArray(
            results.Cast<object>()
        );
        JsonIO.WriteText(options.RawOutputPath, rawJson + Environment.NewLine);

        NormalizedResult normalized = ResultNormalizer.Normalize(
            results,
            takeoff,
            request,
            modules,
            eventLog
        );
        JsonIO.Write(options.OutputPath, normalized);

        eventLog.Note(
            "analysis.completed",
            $"Created {normalized.Summary.RecordCount} normalized records."
        );

        return request.JobId;
    }

    private static void ValidateRequest(AnalysisRequest request)
    {
        if (request.SchemaVersion != "1.0")
        {
            throw new InvalidDataException(
                $"Unsupported schema_version '{request.SchemaVersion}'."
            );
        }

        if (request.AnalysisProfile != SupportedProfile)
        {
            throw new InvalidDataException(
                $"Unsupported analysis_profile '{request.AnalysisProfile}'."
            );
        }

        if (!Guid.TryParse(request.JobId, out _))
        {
            throw new InvalidDataException(
                "job_id must be a valid UUID."
            );
        }

        if (string.IsNullOrWhiteSpace(request.Project.ProjectId))
        {
            throw new InvalidDataException(
                "project.project_id is required."
            );
        }

        if (string.IsNullOrWhiteSpace(request.Project.ProjectName))
        {
            throw new InvalidDataException(
                "project.project_name is required."
            );
        }

        if (request.Project.GrossFloorAreaM2 is < 0)
        {
            throw new InvalidDataException(
                "project.gross_floor_area_m2 cannot be negative."
            );
        }

        JsonIO.ResolveJobFile(request.TakeoffFilename);
        JsonIO.ResolveJobFile(request.TemplateMaterialsFilename);
        ModuleSelection.Validate(request.Modules);
        ParseMetrics(request.MetricFilters);
    }

    private static List<MetricType> ParseMetrics(
        IEnumerable<string> metricNames
    )
    {
        List<MetricType> metrics = [];
        foreach (
            string name in metricNames
                .Where(value => !string.IsNullOrWhiteSpace(value))
                .Distinct(StringComparer.Ordinal)
        )
        {
            if (
                !Enum.TryParse(
                    name,
                    ignoreCase: false,
                    out MetricType metric
                )
            )
            {
                throw new InvalidDataException(
                    $"Unknown BHoM MetricType '{name}'."
                );
            }

            if (metric != MetricType.ClimateChangeTotal)
            {
                throw new InvalidDataException(
                    $"MetricType '{name}' is not enabled in this release."
                );
            }

            metrics.Add(metric);
        }

        if (metrics.Count == 0)
        {
            throw new InvalidDataException(
                "At least one metric filter is required."
            );
        }

        return metrics;
    }
}
