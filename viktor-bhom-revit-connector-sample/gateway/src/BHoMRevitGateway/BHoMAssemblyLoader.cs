using System.Reflection;

namespace BHoMRevitGateway;

public static class BHoMAssemblyLoader
{
    public static void LoadObjectModelAssemblies(EventLog eventLog)
    {
        List<Assembly> objectModelAssemblies = [];
        IEnumerable<string> candidates = Directory
            .EnumerateFiles(AppContext.BaseDirectory, "*_oM.dll")
            .Prepend(Path.Combine(AppContext.BaseDirectory, "BHoM.dll"))
            .Where(File.Exists)
            .OrderBy(path => path, StringComparer.OrdinalIgnoreCase);

        foreach (string path in candidates)
        {
            try
            {
                AssemblyName name = AssemblyName.GetAssemblyName(path);
                Assembly? assembly = AppDomain.CurrentDomain
                    .GetAssemblies()
                    .FirstOrDefault(loaded => loaded.FullName == name.FullName);
                assembly ??= Assembly.LoadFrom(path);
                objectModelAssemblies.Add(assembly);
            }
            catch (BadImageFormatException)
            {
                // Native files cannot contain BHoM object-model types.
            }
            catch (FileLoadException error)
            {
                throw new InvalidOperationException(
                    $"Could not load BHoM object-model assembly '{Path.GetFileName(path)}'.",
                    error
                );
            }
        }

        foreach (Assembly assembly in objectModelAssemblies)
        {
            BH.Engine.Base.Compute.ExtractAssembly(assembly);
        }

        eventLog.Note(
            "bhom.assemblies.loaded",
            $"Loaded and indexed {objectModelAssemblies.Count} BHoM object-model assemblies."
        );
    }
}
