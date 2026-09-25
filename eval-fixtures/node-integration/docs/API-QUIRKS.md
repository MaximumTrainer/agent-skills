# Provider API quirks

| Endpoint | Behaviour | Found | Fixture |
|---|---|---|---|
| `/wellness` | Returns oldest-first, not newest-first | 2026-01 | `wellness-oldest-first.json` |
| `/activities` | `laps` absent entirely when a session has one lap | 2026-02 | `activity-single-lap.json` |
