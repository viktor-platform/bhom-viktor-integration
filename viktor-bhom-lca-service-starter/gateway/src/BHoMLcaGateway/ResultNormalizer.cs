using System.Globalization;
using BH.oM.LifeCycleAssessment;
using BH.oM.LifeCycleAssessment.Results;
using BH.oM.Physical.Materials;

namespace BHoMLcaGateway;

public static class ResultNormalizer
{
    public static NormalizedResult Normalize(
        IReadOnlyCollection<MaterialResult> materialResults,
        GeneralMaterialTakeoff takeoff,
        AnalysisRequest request,
        IReadOnlyList<string> selectedModules,
        EventLog eventLog
    )
    {
        List<ResultRecord> records = [];

        // Parse the selected module strings into BHoM Module enum values once.
        List<Module> parsedModules = [];
        foreach (string moduleStr in selectedModules)
        {
            if (Enum.TryParse<Module>(moduleStr, out Module parsedModule))
            {
                parsedModules.Add(parsedModule);
            }
            else
            {
                eventLog.Warning(
                    "result.module_unknown",
                    $"Module string '{moduleStr}' could not be parsed as a BHoM Module enum value."
                );
            }
        }

        foreach (MaterialResult materialResult in materialResults)
        {
            Type resultType = materialResult.GetType();
            string metric = MetricName(resultType);
            string materialName = materialResult.MaterialName ?? "Unspecified";
            string epdName = materialResult.EnvironmentalProductDeclarationName ?? "Unspecified";

            // BHoM v9: results are in Indicators dictionary keyed by Module enum.
            if (materialResult.Indicators is not { } indicators)
            {
                eventLog.Warning(
                    "result.no_indicators",
                    $"Material result for '{materialName}' has no Indicators dictionary."
                );
                continue;
            }

            foreach (Module module in parsedModules)
            {
                if (!indicators.TryGetValue(module, out double value))
                {
                    eventLog.Warning(
                        "result.module_missing",
                        $"Result for '{materialName}' has no entry for module '{module}'."
                    );
                    continue;
                }

                if (double.IsNaN(value) || double.IsInfinity(value))
                {
                    eventLog.Warning(
                        "result.module_not_numeric",
                        $"Module '{module}' for '{materialName}' is not a finite value."
                    );
                    continue;
                }

                records.Add(
                    new ResultRecord
                    {
                        Material = materialName,
                        EnvironmentalProductDeclaration = epdName,
                        Metric = metric,
                        Module = module.ToString(),
                        Value = value,
                        Unit = UnitForMetric(metric),
                    }
                );
            }
        }

        HashSet<string> resultMaterials = records
            .Select(record => record.Material)
            .Where(name => !string.IsNullOrWhiteSpace(name))
            .ToHashSet(StringComparer.OrdinalIgnoreCase);

        List<string> takeoffMaterials = (takeoff.MaterialTakeoffItems ?? [])
            .Select(item => item.Material?.Name)
            .Where(name => !string.IsNullOrWhiteSpace(name))
            .Select(name => name!)
            .Distinct(StringComparer.OrdinalIgnoreCase)
            .OrderBy(name => name, StringComparer.OrdinalIgnoreCase)
            .ToList();

        List<string> unmatchedMaterials = takeoffMaterials
            .Where(name => !resultMaterials.Contains(name))
            .ToList();

        foreach (string material in unmatchedMaterials)
        {
            eventLog.Warning(
                "material.unmatched",
                $"No selected environmental result was produced for "
                + $"material '{material}'."
            );
        }

        double total = records.Sum(record => record.Value);
        double? intensity = null;
        if (request.Project.GrossFloorAreaM2 is > 0)
        {
            intensity = total / request.Project.GrossFloorAreaM2.Value;
        }

        List<string> warnings = eventLog.Events
            .Where(item => item.Severity == "warning")
            .Select(item => item.Message)
            .Distinct(StringComparer.Ordinal)
            .ToList();

        return new NormalizedResult
        {
            JobId = request.JobId,
            Project = request.Project,
            Summary = new ResultSummary
            {
                TotalKgCo2E = total,
                TotalTCo2E = total / 1000.0,
                CarbonIntensityKgCo2EPerM2 = intensity,
                RecordCount = records.Count,
                UnmatchedMaterialCount = unmatchedMaterials.Count,
            },
            Records = records,
            UnmatchedMaterials = unmatchedMaterials,
            Warnings = warnings,
        };
    }

    private static string MetricName(Type resultType)
    {
        const string suffix = "MaterialResult";
        return resultType.Name.EndsWith(suffix, StringComparison.Ordinal)
            ? resultType.Name[..^suffix.Length]
            : resultType.Name;
    }

    private static string UnitForMetric(string metric)
    {
        return metric.StartsWith(
            "ClimateChange",
            StringComparison.Ordinal
        )
            ? "kgCO2e"
            : "result unit";
    }
}
