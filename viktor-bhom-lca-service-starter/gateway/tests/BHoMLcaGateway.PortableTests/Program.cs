using BHoMLcaGateway;

static void Check(bool condition, string message)
{
    if (!condition)
    {
        throw new InvalidOperationException(message);
    }
}

static TException Expect<TException>(Action action)
    where TException : Exception
{
    try
    {
        action();
    }
    catch (TException error)
    {
        return error;
    }

    throw new InvalidOperationException(
        $"Expected {typeof(TException).Name}, but no exception was thrown."
    );
}

CommandLineOptions options = CommandLineOptions.Parse(
    [
        "run",
        "--request",
        "request.json",
        "--output",
        "result.json",
    ]
);
Check(options.Command == "run", "The run command was not parsed.");
Check(options.RequestPath == "request.json", "The request option was not parsed.");
Check(options.OutputPath == "result.json", "The output option was not parsed.");
Expect<ArgumentException>(() => CommandLineOptions.Parse(["unknown"]));
Expect<ArgumentException>(
    () => CommandLineOptions.Parse(["run", "--output", "a", "--output", "b"])
);

IReadOnlyList<string> modules = ModuleSelection.Validate(["A1", "A2", "A1"]);
Check(modules.SequenceEqual(["A1", "A2"]), "Modules were not normalized.");
Expect<InvalidDataException>(
    () => ModuleSelection.Validate(["A1", "A1toA3"])
);

string originalDirectory = Environment.CurrentDirectory;
string temporaryDirectory = Path.Combine(
    Path.GetTempPath(),
    "bhom-lca-portable-tests-" + Guid.NewGuid().ToString("N")
);
Directory.CreateDirectory(temporaryDirectory);

try
{
    Environment.CurrentDirectory = temporaryDirectory;
    Check(
        JsonIO.ResolveJobFile("analysis.json")
            == Path.Combine(temporaryDirectory, "analysis.json"),
        "A job-local file did not resolve inside the current directory."
    );
    Expect<InvalidDataException>(() => JsonIO.ResolveJobFile("../escape.json"));
    Expect<InvalidDataException>(() => JsonIO.ResolveJobFile("nested/file.json"));

    EventLog eventLog = new();
    eventLog.Note("portable.started", "Portable gateway checks started.");
    JsonIO.Write("analysis-events.json", eventLog.ToDocument("portable-test"));
    EventDocument document = JsonIO.Read<EventDocument>("analysis-events.json");
    Check(document.Events.Count == 1, "The event document did not round-trip.");
    Check(document.Events[0].Severity == "note", "Event severity changed.");

    RuntimeManifest manifest = RuntimeManifestFactory.Create();
    Check(
        !string.IsNullOrWhiteSpace(manifest.DotnetVersion),
        "The runtime manifest omitted the .NET version."
    );
    Check(
        !string.IsNullOrWhiteSpace(manifest.OperatingSystem),
        "The runtime manifest omitted the operating system."
    );
}
finally
{
    Environment.CurrentDirectory = originalDirectory;
    Directory.Delete(temporaryDirectory, recursive: true);
}

Console.WriteLine(
    "Portable gateway checks passed: CLI parsing, module validation, "
    + "job-path isolation, JSON I/O, events, and runtime manifest."
);
