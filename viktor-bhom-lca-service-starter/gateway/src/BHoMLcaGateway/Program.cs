namespace BHoMLcaGateway;

public static class Program
{
    public static int Main(string[] args)
    {
        CommandLineOptions? options = null;
        EventLog eventLog = new();
        string? jobId = null;

        try
        {
            options = CommandLineOptions.Parse(args);

            if (options.Command == "diagnose")
            {
                eventLog.Note(
                    "diagnose.completed",
                    "The runtime manifest was created."
                );
                JsonIO.Write(
                    options.RuntimeManifestPath,
                    RuntimeManifestFactory.Create()
                );
                JsonIO.Write(
                    options.EventsPath,
                    eventLog.ToDocument(jobId)
                );
                return 0;
            }

            jobId = AnalysisRunner.Run(options, eventLog);
            JsonIO.Write(
                options.RuntimeManifestPath,
                RuntimeManifestFactory.Create()
            );
            JsonIO.Write(
                options.EventsPath,
                eventLog.ToDocument(jobId)
            );
            return 0;
        }
        catch (ArgumentException error)
        {
            Console.Error.WriteLine(error.Message);
            eventLog.Error("command.invalid", error.Message);
            WriteFailureFiles(options, eventLog, jobId);
            return 2;
        }
        catch (InvalidDataException error)
        {
            Console.Error.WriteLine(error.Message);
            eventLog.Error("input.invalid", error.Message);
            WriteFailureFiles(options, eventLog, jobId);
            return 3;
        }
        catch (Exception error)
        {
            string message =
                $"{error.GetType().Name}: {error.Message}";
            Console.Error.WriteLine(message);
            eventLog.Error("analysis.failed", message);
            WriteFailureFiles(options, eventLog, jobId);
            return 4;
        }
    }

    private static void WriteFailureFiles(
        CommandLineOptions? options,
        EventLog eventLog,
        string? jobId
    )
    {
        if (options is null)
        {
            return;
        }

        try
        {
            JsonIO.Write(
                options.EventsPath,
                eventLog.ToDocument(jobId)
            );
        }
        catch (Exception writeError)
        {
            Console.Error.WriteLine(
                "Could not write the event file: "
                + writeError.Message
            );
        }

        try
        {
            JsonIO.Write(
                options.RuntimeManifestPath,
                RuntimeManifestFactory.Create()
            );
        }
        catch (Exception writeError)
        {
            Console.Error.WriteLine(
                "Could not write the runtime manifest: "
                + writeError.Message
            );
        }
    }
}
