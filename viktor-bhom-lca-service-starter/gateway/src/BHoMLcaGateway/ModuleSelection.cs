namespace BHoMLcaGateway;

public static class ModuleSelection
{
    private static readonly HashSet<string> Allowed =
        new(StringComparer.Ordinal)
        {
            "A1",
            "A2",
            "A3",
            "A1toA3",
        };

    private static readonly HashSet<string> Components =
        new(StringComparer.Ordinal)
        {
            "A1",
            "A2",
            "A3",
        };

    public static IReadOnlyList<string> Validate(IEnumerable<string> modules)
    {
        List<string> normalized = modules
            .Where(module => !string.IsNullOrWhiteSpace(module))
            .Select(module => module.Trim())
            .Distinct(StringComparer.Ordinal)
            .ToList();

        if (normalized.Count == 0)
        {
            throw new InvalidDataException(
                "At least one life-cycle module is required."
            );
        }

        string[] unsupported = normalized
            .Where(module => !Allowed.Contains(module))
            .OrderBy(module => module, StringComparer.Ordinal)
            .ToArray();
        if (unsupported.Length > 0)
        {
            throw new InvalidDataException(
                "Unsupported modules: " + string.Join(", ", unsupported)
            );
        }

        if (
            normalized.Contains("A1toA3", StringComparer.Ordinal)
            && normalized.Any(Components.Contains)
        )
        {
            throw new InvalidDataException(
                "A1toA3 cannot be selected with A1, A2 or A3."
            );
        }

        return normalized;
    }
}
