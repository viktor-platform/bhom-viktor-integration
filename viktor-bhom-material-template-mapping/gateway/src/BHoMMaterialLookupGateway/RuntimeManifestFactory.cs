using System.Reflection;
using System.Runtime.InteropServices;

namespace BHoMMaterialLookupGateway;

public static class RuntimeManifestFactory
{
    public static RuntimeManifest Create()
    {
        string[] names =
        [
            "BHoM",
            "Data_oM",
            "Library_Engine",
            "LifeCycleAssessment_oM",
            "Serialiser_Engine",
        ];
        string datasetRoot = Path.Combine(
            Environment.GetFolderPath(Environment.SpecialFolder.CommonApplicationData),
            "BHoM",
            "Datasets",
            "LifeCycleAssessment"
        );
        return new RuntimeManifest
        {
            GeneratedAtUtc = DateTimeOffset.UtcNow,
            GatewayVersion = Assembly.GetExecutingAssembly().GetName().Version?.ToString() ?? "",
            DotnetVersion = Environment.Version.ToString(),
            OperatingSystem = RuntimeInformation.OSDescription,
            DatasetRoot = datasetRoot,
            DatasetFiles = Directory.Exists(datasetRoot)
                ? Directory.EnumerateFiles(datasetRoot, "*.json", SearchOption.AllDirectories).Count()
                : 0,
            Assemblies = names.Select(LoadAssemblyVersion).ToList(),
        };
    }

    private static string LoadAssemblyVersion(string name)
    {
        try
        {
            Assembly? assembly = AppDomain.CurrentDomain.GetAssemblies()
                .FirstOrDefault(item => item.GetName().Name == name);
            assembly ??= Assembly.LoadFrom(Path.Combine(AppContext.BaseDirectory, name + ".dll"));
            return name + ":" + (assembly.GetName().Version?.ToString() ?? "");
        }
        catch (Exception error)
        {
            return name + ":load-failed:" + error.GetType().Name;
        }
    }
}
