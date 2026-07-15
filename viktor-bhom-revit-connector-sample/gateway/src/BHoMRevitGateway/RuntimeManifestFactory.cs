using System.Diagnostics;
using System.Reflection;
using System.Runtime.InteropServices;
using System.Security.Cryptography;

namespace BHoMRevitGateway;

public static class RuntimeManifestFactory
{
    public static RuntimeManifest Create()
    {
        Assembly gatewayAssembly = Assembly.GetExecutingAssembly();
        string gatewayVersion =
            gatewayAssembly.GetName().Version?.ToString() ?? "unknown";

        List<AssemblyManifestItem> assemblies = [];
        IEnumerable<string> files = Directory
            .EnumerateFiles(AppContext.BaseDirectory, "*.dll")
            .Concat(Directory.EnumerateFiles(AppContext.BaseDirectory, "*.exe"))
            .OrderBy(path => path, StringComparer.OrdinalIgnoreCase);
        foreach (string file in files)
        {
            try
            {
                AssemblyName assemblyName = AssemblyName.GetAssemblyName(file);
                assemblies.Add(
                    new AssemblyManifestItem
                    {
                        Name = assemblyName.Name ?? Path.GetFileNameWithoutExtension(file),
                        Version = assemblyName.Version?.ToString() ?? "unknown",
                        File = Path.GetFileName(file),
                        Sha256 = ComputeSha256(file),
                    }
                );
            }
            catch (BadImageFormatException)
            {
                // Native libraries are omitted from the managed assembly manifest.
            }
            catch (FileLoadException)
            {
                // Unreadable managed files are omitted from the manifest.
            }
        }

        return new RuntimeManifest
        {
            GeneratedAtUtc = DateTimeOffset.UtcNow,
            GatewayVersion = gatewayVersion,
            DotnetVersion = Environment.Version.ToString(),
            OperatingSystem = Environment.OSVersion.VersionString,
            Revit = new RevitRuntimeInfo
            {
                ListenerProcessDetected = Process.GetProcessesByName("Revit").Length == 1,
            },
            Assemblies = assemblies,
        };
    }

    private static string ComputeSha256(string path)
    {
        using FileStream stream = File.OpenRead(path);
        using SHA256 algorithm = SHA256.Create();
        byte[] hash = algorithm.ComputeHash(stream);
        return BitConverter.ToString(hash).Replace("-", string.Empty).ToLowerInvariant();
    }
}
