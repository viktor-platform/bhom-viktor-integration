namespace BHoMMaterialLookupGateway;

public sealed class CommandLineOptions
{
    public string Command { get; private init; } = "";
    public string RequestPath { get; private init; } = "lookup-request.json";
    public string OutputPath { get; private init; } = "lookup-result.json";
    public string EventsPath { get; private init; } = "lookup-events.json";
    public string RuntimeManifestPath { get; private init; } = "runtime-manifest.json";

    public static CommandLineOptions Parse(string[] args)
    {
        if (args.Length == 0 || (args[0] != "query" && args[0] != "diagnose"))
            throw new ArgumentException("Command must be 'query' or 'diagnose'.");

        Dictionary<string, string> values = [];
        for (int index = 1; index < args.Length; index += 2)
        {
            if (!args[index].StartsWith("--", StringComparison.Ordinal) || index + 1 >= args.Length)
                throw new ArgumentException($"Invalid option near '{args[index]}'.");
            values[args[index]] = args[index + 1];
        }

        return new CommandLineOptions
        {
            Command = args[0],
            RequestPath = values.GetValueOrDefault("--request", "lookup-request.json"),
            OutputPath = values.GetValueOrDefault("--output", "lookup-result.json"),
            EventsPath = values.GetValueOrDefault("--events", "lookup-events.json"),
            RuntimeManifestPath = values.GetValueOrDefault("--runtime-manifest", "runtime-manifest.json"),
        };
    }
}
