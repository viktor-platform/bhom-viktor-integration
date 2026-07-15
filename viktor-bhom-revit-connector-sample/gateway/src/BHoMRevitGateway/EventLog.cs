namespace BHoMRevitGateway;

public sealed class EventLog
{
    private readonly List<GatewayEvent> _events = [];

    public IReadOnlyList<GatewayEvent> Events => _events;

    public void Note(string code, string message) => Add("note", code, message);

    public void Warning(string code, string message) => Add("warning", code, message);

    public void Error(string code, string message) => Add("error", code, message);

    public EventDocument ToDocument(string? jobId) =>
        new() { JobId = jobId, Events = [.. _events] };

    private void Add(string severity, string code, string message)
    {
        _events.Add(
            new GatewayEvent
            {
                TimestampUtc = DateTimeOffset.UtcNow,
                Severity = severity,
                Code = code,
                Message = message,
            }
        );
    }
}
