using System.Text.Json;
using System.Text.Json.Serialization;

namespace BHoMMaterialLookupGateway;

public static class JsonIO
{
    public static readonly JsonSerializerOptions Options = new()
    {
        PropertyNameCaseInsensitive = true,
        WriteIndented = true,
        DefaultIgnoreCondition = JsonIgnoreCondition.Never,
    };

    public static T Read<T>(string path)
    {
        string text = File.ReadAllText(ResolveJobFile(path));
        return JsonSerializer.Deserialize<T>(text, Options)
            ?? throw new InvalidDataException($"File '{path}' is empty.");
    }

    public static void Write<T>(string path, T value)
    {
        string fullPath = ResolveJobFile(path);
        string temporaryPath = fullPath + "." + Guid.NewGuid().ToString("N") + ".tmp";
        File.WriteAllText(temporaryPath, JsonSerializer.Serialize(value, Options) + Environment.NewLine);
        File.Move(temporaryPath, fullPath, overwrite: true);
    }

    public static string ResolveJobFile(string path)
    {
        if (string.IsNullOrWhiteSpace(path) || Path.IsPathRooted(path) || Path.GetFileName(path) != path)
            throw new InvalidDataException($"Only a file name in the job directory is allowed: '{path}'.");
        return Path.GetFullPath(Path.Combine(Environment.CurrentDirectory, path));
    }
}
