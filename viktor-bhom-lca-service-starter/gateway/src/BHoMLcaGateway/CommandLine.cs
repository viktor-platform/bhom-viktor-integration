namespace BHoMLcaGateway;

public sealed class CommandLineOptions
{
    public string Command { get; init; } = string.Empty;
    public string RequestPath { get; init; } = "analysis-request.json";
    public string OutputPath { get; init; } = "analysis-result.json";
    public string RawOutputPath { get; init; } = "bhom-results.json";
    public string EventsPath { get; init; } = "analysis-events.json";
    public string RuntimeManifestPath { get; init; } = "runtime-manifest.json";

    public static CommandLineOptions Parse(string[] args)
    {
        if (args.Length == 0)
        {
            throw new ArgumentException(
                "A command is required. Use 'run' or 'diagnose'."
            );
        }

        string command = args[0].Trim().ToLowerInvariant();
        if (command is not ("run" or "diagnose"))
        {
            throw new ArgumentException(
                $"Unsupported command '{args[0]}'. Use 'run' or 'diagnose'."
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
                throw new ArgumentException(
                    $"Option '{flag}' requires a value."
                );
            }

            if (!values.TryAdd(flag, args[index + 1]))
            {
                throw new ArgumentException(
                    $"Option '{flag}' was supplied more than once."
                );
            }
        }

        HashSet<string> allowed =
        [
            "--request",
            "--output",
            "--raw-output",
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
            values.TryGetValue(name, out string? value)
                ? value
                : fallback;

        return new CommandLineOptions
        {
            Command = command,
            RequestPath = Get("--request", "analysis-request.json"),
            OutputPath = Get("--output", "analysis-result.json"),
            RawOutputPath = Get("--raw-output", "bhom-results.json"),
            EventsPath = Get("--events", "analysis-events.json"),
            RuntimeManifestPath = Get(
                "--runtime-manifest",
                "runtime-manifest.json"
            ),
        };
    }
}
