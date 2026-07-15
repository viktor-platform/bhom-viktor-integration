namespace BHoMRevitGateway;

public static class RequestValidator
{
    private static readonly HashSet<string> AllowedCategories =
        new(StringComparer.Ordinal)
        {
            "Walls",
            "Floors",
            "Structural Columns",
            "Structural Framing",
            "Roofs",
        };

    public static void Validate(PullRequest request)
    {
        if (request.SchemaVersion != "1.0")
        {
            throw new InvalidDataException(
                $"Unsupported schema_version '{request.SchemaVersion}'."
            );
        }

        if (request.Operation != "pull_model_snapshot")
        {
            throw new InvalidDataException(
                $"Unsupported operation '{request.Operation}'."
            );
        }

        if (request.RevitVersion != "2025")
        {
            throw new InvalidDataException(
                $"Unsupported Revit version '{request.RevitVersion}'."
            );
        }

        if (!Guid.TryParse(request.JobId, out _))
        {
            throw new InvalidDataException("job_id must be a valid UUID.");
        }

        List<string> categories = request.Filters.Categories
            .Where(value => !string.IsNullOrWhiteSpace(value))
            .Distinct(StringComparer.Ordinal)
            .ToList();
        if (categories.Count == 0)
        {
            throw new InvalidDataException("At least one Revit category is required.");
        }

        string[] unsupported = categories
            .Where(category => !AllowedCategories.Contains(category))
            .OrderBy(category => category, StringComparer.Ordinal)
            .ToArray();
        if (unsupported.Length > 0)
        {
            throw new InvalidDataException(
                "Unsupported Revit categories: " + string.Join(", ", unsupported)
            );
        }

        if (!request.Options.IncludeMaterialTakeoff)
        {
            throw new InvalidDataException(
                "include_material_takeoff must be true for this gateway profile."
            );
        }

        if (request.Options.IncludeGeometry)
        {
            throw new InvalidDataException(
                "include_geometry must be false for this gateway profile."
            );
        }

        if (request.Options.ElementLimit is < 1 or > 10000)
        {
            throw new InvalidDataException(
                "element_limit must be between 1 and 10,000."
            );
        }
    }
}
