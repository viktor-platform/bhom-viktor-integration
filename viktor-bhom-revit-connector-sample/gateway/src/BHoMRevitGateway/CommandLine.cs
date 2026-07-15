namespace BHoMRevitGateway;

public sealed class CommandLineOptions
{
    public string Command { get; set; } = string.Empty;
    public string RequestPath { get; set; } = "revit-pull-request.json";
    public string MetadataPath { get; set; } = "revit-metadata.json";
    public string ElementsPath { get; set; } = "revit-elements.bhom.json";
    public string TakeoffPath { get; set; } = "takeoff.bhom.json";
    public string EventsPath { get; set; } = "revit-events.json";
    public string RuntimeManifestPath { get; set; } = "runtime-manifest.json";

    public static CommandLineOptions Parse(string[] args)
    {
        if (args.Length == 0)
        {
            throw new ArgumentException(
                "A command is required. Use 'pull' or 'diagnose'."
            );
        }

        string command = args[0].Trim().ToLowerInvariant();
        if (command is not ("pull" or "diagnose"))
        {
            throw new ArgumentException(
                $"Unsupported command '{args[0]}'. Use 'pull' or 'diagnose'."
            );
        }

        Dictionary<string, string> values = new(StringComparer.OrdinalIgnoreCase);
        for (int index = 1; index < args.Length; index += 2)
        {
            string flag = args[index];
            if (!flag.StartsWith("--", StringComparison.Ordinal))
            {
                throw new ArgumentException(
                    $"Expected an option beginning with '--', received '{flag}'."
                );
            }

            if (index + 1 >= args.Length)
            {
                throw new ArgumentException($"Option '{flag}' requires a value.");
            }

            if (values.ContainsKey(flag))
            {
                throw new ArgumentException(
                    $"Option '{flag}' was supplied more than once."
                );
            }

            values.Add(flag, args[index + 1]);
        }

        HashSet<string> allowed =
        [
            "--request",
            "--metadata",
            "--elements",
            "--takeoff",
            "--events",
            "--runtime-manifest",
        ];
        string[] unknown = values.Keys
            .Where(key => !allowed.Contains(key))
            .OrderBy(key => key, StringComparer.Ordinal)
            .ToArray();
        if (unknown.Length > 0)
        {
            throw new ArgumentException(
                "Unsupported options: " + string.Join(", ", unknown)
            );
        }

        string Get(string name, string fallback) =>
            values.TryGetValue(name, out string? value) ? value : fallback;

        return new CommandLineOptions
        {
            Command = command,
            RequestPath = Get("--request", "revit-pull-request.json"),
            MetadataPath = Get("--metadata", "revit-metadata.json"),
            ElementsPath = Get("--elements", "revit-elements.bhom.json"),
            TakeoffPath = Get("--takeoff", "takeoff.bhom.json"),
            EventsPath = Get("--events", "revit-events.json"),
            RuntimeManifestPath = Get("--runtime-manifest", "runtime-manifest.json"),
        };
    }
}
