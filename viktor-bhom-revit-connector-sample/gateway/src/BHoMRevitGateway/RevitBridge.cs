using System.Diagnostics;
using System.Text.Json;
using System.Text.Json.Nodes;
using BH.Adapter.Revit;
using BH.oM.Adapters.Revit;
using BH.oM.Adapters.Revit.Requests;
using BH.oM.Adapters.Revit.Settings;
using BHoMSerialiser = BH.Engine.Serialiser.Convert;

namespace BHoMRevitGateway;

public static class RevitBridge
{
    private const int PushPort = 14128;
    private const int PullPort = 14129;

    public static string Run(CommandLineOptions options, EventLog eventLog)
    {
        PullRequest request = JsonIO.Read<PullRequest>(options.RequestPath);
        RequestValidator.Validate(request);

        string documentName = ConfirmActiveDocument(
            request.ExpectedDocumentName
        );
        eventLog.Note(
            "revit.pull.started",
            $"Pulling read-only snapshot for job '{request.JobId}'."
        );

        RevitSettings settings = new()
        {
            ConnectionSettings = new ConnectionSettings
            {
                PushPort = PushPort,
                PullPort = PullPort,
                MaxMinutesToWait = 10,
            },
        };
        RevitAdapter adapter = new(settings, active: true);
        if (!adapter.IsValid())
        {
            throw new InvalidOperationException(
                "The BHoM Revit adapter could not initialize its local socket links."
            );
        }

        RevitPullConfig pullConfig = new()
        {
            PullMaterialTakeOff = true,
            GeometryConfig = new PullGeometryConfig
            {
                PullEdges = false,
                PullSurfaces = false,
                PullMeshes = false,
            },
            RepresentationConfig = new PullRepresentationConfig
            {
                PullRenderMesh = false,
            },
        };

        List<object> pulledObjects = [];
        bool truncated = false;
        foreach (string category in request.Filters.Categories)
        {
            eventLog.Note(
                "revit.category.started",
                $"Pulling Revit category '{category}'."
            );
            IEnumerable<object> categoryObjects = adapter.Pull(
                new FilterByCategory
                {
                    CategoryName = category,
                    CaseSensitive = true,
                },
                actionConfig: pullConfig
            );

            foreach (object item in categoryObjects)
            {
                if (pulledObjects.Count >= request.Options.ElementLimit)
                {
                    truncated = true;
                    break;
                }

                pulledObjects.Add(item);
            }

            if (truncated)
            {
                break;
            }
        }

        if (pulledObjects.Count == 0)
        {
            throw new InvalidOperationException(
                "The Revit listener returned no BHoM objects. Confirm that Revit "
                + "2025 has an active document, the BHoM listener is activated, "
                + "and the selected categories contain model elements."
            );
        }

        if (truncated)
        {
            eventLog.Warning(
                "revit.pull.truncated",
                $"The snapshot was limited to {request.Options.ElementLimit} elements."
            );
        }

        string serializedObjects = BHoMSerialiser.ToJsonArray(pulledObjects);
        JsonArray elements = BHoMJsonProjection.ParseElementArray(
            serializedObjects
        );
        if (!request.Options.IncludeParameters)
        {
            BHoMJsonProjection.RemovePulledParameters(elements);
        }

        string bHoMVersion =
            typeof(BH.oM.Base.IBHoMObject).Assembly.GetName().Version?.ToString()
            ?? "unknown";
        MetadataDocument metadata = BHoMJsonProjection.BuildMetadata(
            elements,
            request,
            documentName,
            bHoMVersion
        );
        JsonObject takeoff = BHoMJsonProjection.BuildGeneralMaterialTakeoff(
            elements,
            documentName
        );

        JsonSerializerOptions bHoMJsonOptions = new() { WriteIndented = true };
        JsonIO.WriteText(
            options.ElementsPath,
            elements.ToJsonString(bHoMJsonOptions) + Environment.NewLine
        );
        JsonIO.Write(options.MetadataPath, metadata);
        JsonIO.WriteText(
            options.TakeoffPath,
            takeoff.ToJsonString(bHoMJsonOptions) + Environment.NewLine
        );

        eventLog.Note(
            "revit.pull.completed",
            $"Created a snapshot containing {elements.Count} BHoM objects."
        );
        return request.JobId;
    }

    private static string ConfirmActiveDocument(string? expectedDocumentName)
    {
        Process[] processes = Process.GetProcessesByName("Revit")
            .Where(process => !process.HasExited)
            .ToArray();
        if (processes.Length != 1)
        {
            throw new InvalidOperationException(
                "Exactly one Revit process must be running before a live pull."
            );
        }

        string title = processes[0].MainWindowTitle.Trim();
        string expected = expectedDocumentName?.Trim() ?? string.Empty;
        if (!string.IsNullOrWhiteSpace(expected))
        {
            string stem = Path.GetFileNameWithoutExtension(expected);
            if (
                string.IsNullOrWhiteSpace(title)
                || !title.Contains(stem, StringComparison.OrdinalIgnoreCase)
            )
            {
                throw new InvalidOperationException(
                    $"The active Revit window does not match expected document '{expected}'. "
                    + $"Active window title: '{title}'."
                );
            }

            return expected;
        }

        return string.IsNullOrWhiteSpace(title) ? "Active Revit document" : title;
    }
}
