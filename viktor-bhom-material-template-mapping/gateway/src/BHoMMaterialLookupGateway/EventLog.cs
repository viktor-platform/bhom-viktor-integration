namespace BHoMMaterialLookupGateway;

public sealed class EventLog
{
    private readonly List<GatewayEvent> m_events = [];

    public void Note(string code, string message) => Add("note", code, message);
    public void Warning(string code, string message) => Add("warning", code, message);
    public void Error(string code, string message) => Add("error", code, message);

    private void Add(string severity, string code, string message)
    {
        m_events.Add(new GatewayEvent
        {
            TimestampUtc = DateTimeOffset.UtcNow,
            Severity = severity,
            Code = code,
            Message = message,
        });
    }

    public EventDocument ToDocument(string? jobId) => new()
    {
        JobId = jobId,
        Events = [.. m_events],
    };
}
