using System.Globalization;
using System.Reflection;
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

        foreach (MaterialResult materialResult in materialResults)
        {
            Type resultType = materialResult.GetType();
            string metric = MetricName(resultType);
            string materialName =
                StringProperty(materialResult, "MaterialName") ?? "Unspecified";
            string epdName =
                StringProperty(
                    materialResult,
                    "EnvironmentalProductDeclarationName"
                ) ?? "Unspecified";

            foreach (string module in selectedModules)
            {
                PropertyInfo? moduleProperty = resultType.GetProperty(
                    module,
                    BindingFlags.Instance | BindingFlags.Public
                );

                if (moduleProperty is null)
                {
                    eventLog.Warning(
                        "result.module_missing",
                        $"Result type '{resultType.FullName}' has no public "
                        + $"property named '{module}'."
                    );
                    continue;
                }

                object? rawValue = moduleProperty.GetValue(materialResult);
                if (!TryToDouble(rawValue, out double value))
                {
                    eventLog.Warning(
                        "result.module_not_numeric",
                        $"Property '{resultType.FullName}.{module}' did not "
                        + "contain a finite numeric value."
                    );
                    continue;
                }

                records.Add(
                    new ResultRecord
                    {
                        Material = materialName,
                        EnvironmentalProductDeclaration = epdName,
                        Metric = metric,
                        Module = module,
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

    private static string? StringProperty(object value, string propertyName)
    {
        object? propertyValue = value
            .GetType()
            .GetProperty(
                propertyName,
                BindingFlags.Instance | BindingFlags.Public
            )
            ?.GetValue(value);
        return propertyValue as string;
    }

    private static bool TryToDouble(object? rawValue, out double value)
    {
        value = 0;
        if (rawValue is null)
        {
            return false;
        }

        try
        {
            value = System.Convert.ToDouble(
                rawValue,
                CultureInfo.InvariantCulture
            );
            return !double.IsNaN(value) && !double.IsInfinity(value);
        }
        catch (Exception error)
            when (
                error is FormatException
                or InvalidCastException
                or OverflowException
            )
        {
            return false;
        }
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
