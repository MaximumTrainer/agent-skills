# flow-service

Kotlin/Spring service managing flows. Hexagonal layout.

## Build

```bash
./gradlew build
```

## Readiness bands

A flow's staleness is banded for the dashboard:

| Band | Age |
|---|---|
| Fresh | under 7 days |
| Ageing | 7 to 30 days |
| Stale | over 30 days |

## Testing

`./gradlew test` runs the unit suite. Integration tests need Docker.
