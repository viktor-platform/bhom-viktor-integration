using System.Text.Json.Nodes;
using BHoMRevitGateway;

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
        "pull",
        "--request",
        "request.json",
        "--metadata",
        "metadata.json",
    ]
);
Check(options.Command == "pull", "The pull command was not parsed.");
Check(options.RequestPath == "request.json", "The request option was not parsed.");
Check(options.MetadataPath == "metadata.json", "The metadata option was not parsed.");
Expect<ArgumentException>(() => CommandLineOptions.Parse(["unknown"]));
Expect<ArgumentException>(
    () => CommandLineOptions.Parse(["pull", "--takeoff", "a", "--takeoff", "b"])
);

PullRequest request = new()
{
    SchemaVersion = "1.0",
    JobId = "2bb20e7b-590d-5a0e-a79c-1ee7d71f87b8",
    Operation = "pull_model_snapshot",
    RevitVersion = "2025",
    Filters = new PullFilters { Categories = ["Walls"] },
    Options = new PullOptions
    {
        IncludeParameters = true,
        IncludeMaterialTakeoff = true,
        IncludeGeometry = false,
        ElementLimit = 100,
    },
};
RequestValidator.Validate(request);
Expect<InvalidDataException>(
    () => RequestValidator.Validate(
        new PullRequest
        {
            SchemaVersion = "1.0",
            JobId = request.JobId,
            Operation = request.Operation,
            RevitVersion = request.RevitVersion,
            Filters = new PullFilters { Categories = ["Doors"] },
            Options = request.Options,
        }
    )
);

string serializedObjects =
    """
    [
      {
        "_t": "BH.oM.Physical.Elements.Wall",
        "BHoM_Guid": "3ff71bc9-f894-41fd-98ca-03f18c56e266",
        "Name": "Wall 1",
        "Fragments": [
          {
            "_t": "BH.oM.Adapters.Revit.Parameters.RevitIdentifiers",
            "PersistentId": "revit-unique-id",
            "ElementId": 100421,
            "CategoryName": "Walls",
            "FamilyName": "Basic Wall",
            "FamilyTypeName": "Concrete"
          },
          {
            "_t": "BH.oM.Adapters.Revit.Parameters.RevitPulledParameters",
            "Parameters": [
              {
                "Name": "Area",
                "Value": 80.0,
                "Unit": "m²",
                "IsReadOnly": true
              }
            ]
          },
          {
            "_t": "BH.oM.Physical.Materials.VolumetricMaterialTakeoff",
            "Materials": {
              "_v": [
                {
                  "_t": "BH.oM.Physical.Materials.Material",
                  "Name": "Concrete",
                  "Density": 2400.0,
                  "Properties": []
                }
              ]
            },
            "Volumes": { "_v": [10.0] }
          }
        ]
      }
    ]
    """;
JsonArray elements = BHoMJsonProjection.ParseElementArray(serializedObjects);
JsonArray nonFiniteNumbers = BHoMJsonProjection.ParseElementArray(
    """
    [{"Name":"NaN remains text","A":NaN,"B":Infinity,"C":-Infinity}]
    """
);
Check(
    nonFiniteNumbers[0]!["Name"]!.GetValue<string>() == "NaN remains text",
    "A non-finite token inside a JSON string was modified."
);
Check(
    nonFiniteNumbers[0]!["A"] is null
        && nonFiniteNumbers[0]!["B"] is null
        && nonFiniteNumbers[0]!["C"] is null,
    "Bare non-finite BHoM numbers were not normalized to JSON null values."
);
MetadataDocument metadata = BHoMJsonProjection.BuildMetadata(
    elements,
    request,
    "Sample.rvt",
    "9.0.0.0"
);
Check(metadata.Elements.Count == 1, "Element metadata was not created.");
Check(
    metadata.Elements[0].RevitElementId == "100421",
    "The Revit element ID was not projected."
);
Check(
    metadata.Elements[0].Materials.Single().MassKg == 24000.0,
    "Element material mass was not calculated."
);

JsonObject takeoff = BHoMJsonProjection.BuildGeneralMaterialTakeoff(
    elements,
    "Sample.rvt"
);
JsonArray takeoffItems = takeoff["MaterialTakeoffItems"]!.AsArray();
Check(takeoffItems.Count == 1, "The material takeoff was not aggregated.");
Check(
    takeoffItems[0]!["Mass"]!.GetValue<double>() == 24000.0,
    "The aggregated takeoff mass is incorrect."
);

BHoMJsonProjection.RemovePulledParameters(elements);
Check(
    elements[0]!["Fragments"]!.AsArray().Count == 2,
    "Pulled parameters were not removed."
);

string originalDirectory = Environment.CurrentDirectory;
string temporaryDirectory = Path.Combine(
    Path.GetTempPath(),
    "bhom-revit-portable-tests-" + Guid.NewGuid().ToString("N")
);
Directory.CreateDirectory(temporaryDirectory);
try
{
    Environment.CurrentDirectory = temporaryDirectory;
    Check(
        JsonIO.ResolveJobFile("revit.json")
            == Path.Combine(temporaryDirectory, "revit.json"),
        "A job-local file did not resolve inside the current directory."
    );
    Expect<InvalidDataException>(() => JsonIO.ResolveJobFile("../escape.json"));

    EventLog eventLog = new();
    eventLog.Note("portable.started", "Portable gateway checks started.");
    JsonIO.Write("revit-events.json", eventLog.ToDocument("portable-test"));
    EventDocument document = JsonIO.Read<EventDocument>("revit-events.json");
    Check(document.Events.Count == 1, "The event document did not round-trip.");

    RuntimeManifest manifest = RuntimeManifestFactory.Create();
    Check(
        !string.IsNullOrWhiteSpace(manifest.DotnetVersion),
        "The runtime manifest omitted the .NET version."
    );
}
finally
{
    Environment.CurrentDirectory = originalDirectory;
    Directory.Delete(temporaryDirectory, recursive: true);
}

Console.WriteLine(
    "Portable Revit gateway checks passed: CLI parsing, request validation, "
    + "BHoM element/material projection, job-path isolation, events, and manifest."
);
