namespace BHoMMaterialLookupGateway;

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
            if (options.Command == "query")
                jobId = LookupRunner.Run(options, eventLog);
            else
                eventLog.Note(
                    "diagnose.completed",
                    "The installed BHoM Library_Engine and LCA datasets are available."
                );

            JsonIO.Write(options.RuntimeManifestPath, RuntimeManifestFactory.Create());
            JsonIO.Write(options.EventsPath, eventLog.ToDocument(jobId));
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
            string message = $"{error.GetType().Name}: {error.Message}";
            Console.Error.WriteLine(message);
            eventLog.Error("lookup.failed", message);
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
            return;
        try { JsonIO.Write(options.EventsPath, eventLog.ToDocument(jobId)); } catch { }
        try { JsonIO.Write(options.RuntimeManifestPath, RuntimeManifestFactory.Create()); } catch { }
    }
}
