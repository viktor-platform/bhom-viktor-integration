using System.Text.Json;
using System.Text.Json.Serialization;

namespace BHoMRevitGateway;

public static class JsonIO
{
    public static readonly JsonSerializerOptions Options = new()
    {
        PropertyNamingPolicy = JsonNamingPolicy.SnakeCaseLower,
        DictionaryKeyPolicy = JsonNamingPolicy.SnakeCaseLower,
        PropertyNameCaseInsensitive = true,
        WriteIndented = true,
        DefaultIgnoreCondition = JsonIgnoreCondition.Never,
    };

    public static T Read<T>(string path)
    {
        string fullPath = ResolveJobFile(path);
        string text = File.ReadAllText(fullPath);
        T? value = JsonSerializer.Deserialize<T>(text, Options);
        return value ?? throw new InvalidDataException(
            $"File '{path}' did not contain a {typeof(T).Name} object."
        );
    }

    public static void Write<T>(string path, T value)
    {
        string text = JsonSerializer.Serialize(value, Options);
        WriteText(path, text + Environment.NewLine);
    }

    public static string ResolveJobFile(string path)
    {
        if (string.IsNullOrWhiteSpace(path))
        {
            throw new InvalidDataException("A file name cannot be empty.");
        }

        if (Path.IsPathRooted(path) || Path.GetFileName(path) != path)
        {
            throw new InvalidDataException(
                $"Only a file name in the current job directory is allowed: '{path}'."
            );
        }

        string root = Path.GetFullPath(Environment.CurrentDirectory)
            .TrimEnd(Path.DirectorySeparatorChar)
            + Path.DirectorySeparatorChar;
        string fullPath = Path.GetFullPath(Path.Combine(root, path));
        if (!fullPath.StartsWith(root, StringComparison.OrdinalIgnoreCase))
        {
            throw new InvalidDataException(
                $"File '{path}' resolves outside the job directory."
            );
        }

        return fullPath;
    }

    public static void WriteText(string path, string text)
    {
        string fullPath = ResolveJobFile(path);
        string temporaryPath = fullPath + "." + Guid.NewGuid().ToString("N") + ".tmp";
        File.WriteAllText(temporaryPath, text);
        File.Move(temporaryPath, fullPath, overwrite: true);
    }
}
