---
name: container-integration-tests
description: Test an adapter against a real database, cloud emulator or external service using Testcontainers, with honest readiness checks and a start guard that fails when the container should have started and did not. Use when asked to test a repository or adapter against a real instance, add an emulator or integration test, replace mocks with the real thing, or when an adapter has only ever run against a mock. Covers image choice, why log-line wait strategies break, seeding through the production parser, cross-provider fixtures, and the Windows Docker pipe.
license: MIT
metadata:
  version: "1.0.0"
---

# Container-backed integration tests

The goal is an adapter exercised against the real thing, in CI, with no cloud account and no shared test environment.

An adapter that has only ever run against a mock has not been tested. Its query syntax, its type mapping, its connection-string parsing, its pagination and its error codes are all still guesses — and they are exactly the things a mock cannot check, because the mock was written from the same assumptions as the code.

## 1. Prefer an emulator to an account

Nearly everything has one, and a local container beats a shared cloud account on every axis that matters: no credentials in CI, no cross-run interference, no cost, and it works offline.

| Service | Image |
|---|---|
| PostgreSQL | `postgres:16` |
| MySQL / MariaDB | `mysql:8` |
| MongoDB | `mongo:7` |
| Redis | `redis:7-alpine` |
| DynamoDB | `amazon/dynamodb-local` |
| Firestore | `gcr.io/google.com/cloudsdktool/google-cloud-cli:emulators` |
| Cosmos DB | `azure-cosmos-emulator:vnext-preview` |
| S3 | MinIO (`minio/minio`) |
| Azure Blob | Azurite (`mcr.microsoft.com/azure-storage/azurite`) |
| GCS | `fsouza/fake-gcs-server` |
| Kafka | `confluentinc/cp-kafka` or Redpanda |
| An arbitrary HTTP dependency | WireMock, or a purpose-built stub container |

**Pin the tag.** Never `:latest` — an image that silently moves turns a green suite red on an unrelated day, and worse, can change a behaviour your test was asserting. Use the image-parameter constructor (`new MongoDbBuilder("mongo:7")`, `new PostgreSqlBuilder("postgres:16")`); the parameterless overloads are obsolete in current Testcontainers and fail the build.

Image choice can dominate the cost of the whole suite. Two concrete traps worth knowing in advance:

- **Cosmos DB:** use `vnext-preview`, not the older emulator image. The old one is 3 GB, writes its log to a file *inside* the container — so no log-based wait strategy can ever match — and then spins at full CPU without ever serving under WSL2. `vnext-preview` is 1.7 GB and serves in about ten seconds.
- Heavy images belong behind an opt-in variable and in a separate scheduled or labelled workflow, not on every push.

## 2. Readiness is a real client call, not a log line

This is the single most common cause of a container suite that appears to work and does not.

A container reports *running* long before it accepts a request, and a log-line wait strategy breaks silently whenever an image changes its output — or logs to a file, in which case the wait can never match and the timeout gets swallowed as a skip.

Build with no wait strategy and let the first real call **through the production client** be the readiness check, retrying against a deadline:

```csharp
var deadline = DateTime.UtcNow + timeout;
while (true)
{
    try { await SeedAsync(client); return; }
    catch when (DateTime.UtcNow < deadline) { await Task.Delay(TimeSpan.FromSeconds(2)); }
}
```

Readiness then means "the thing the test needs works", not "the image printed a string".

Where a service does log a stable, documented line, a log wait is fine — the Firestore emulator's `"Dev App Server is now running"` is reliable. Prefer the library's protocol-aware strategies (`UntilPortIsAvailable`, an HTTP probe against a health endpoint) over a message match where they exist.

## 3. Seed through the production parser

Where the adapter accepts a connection string, connection options or a URI, seed the fixture through **the adapter's own** parser rather than constructing a client by hand. That tests the format inbound as well as outbound.

This is how a real defect surfaced: a schema discoverer parsed `region=...;serviceUrl=...` while the data profiler treated the whole string as a service URL — and the CLI passed the identical `--connection` value to both commands. Neither had ever connected to anything, so nothing caught it. A hand-built client in the fixture would not have caught it either.

Put the shared parser somewhere both production and test can reach (`InternalsVisibleTo`, an internal module export), and use it in the fixture.

## 4. One fixture shape across providers

Seed every provider with the same shaped data, so a difference between providers is a real difference and not a difference of fixture. The shape that keeps earning its place:

- a field **present** on one record
- the same field **explicitly null** on a second
- the same field **absent entirely** from a third
- a nested object
- an array, including an empty one
- a boundary value (zero, empty string, maximum length)
- a recognisable planted secret (`SEEDED-SECRET-DO-NOT-EMIT`), asserted **absent** from any output, log or export

Present / null / absent is three distinct cases that most schema and mapping code conflates, and the conflation is invisible against a fixture that only exercises one of them. See `api-quirk-fixtures`.

## 5. The start guard — mandatory

A suite that self-skips when Docker is unavailable is reasonable. A suite that self-skips when the container *failed* is a green, empty suite.

Every self-skipping fixture needs one test that fails when the container should have started and did not:

```csharp
[Fact]
public void EmulatorStartedWhenDockerIsAvailable()
{
    output.WriteLine(fixture.Report());        // what ran, what did not, and why
    if (!fixture.DockerAvailable) return;      // no Docker at all is a real skip

    fixture.ConnectionString.Should().NotBeNull(
        "the emulator must start when Docker is available; it failed with: {0}", fixture.Failure);
}
```

And a `Report()` naming each dependency as **exercised / failed / not run**, distinguishing "not asked for" from "asked for and broken". Those are different facts, and printing the first when the second is true is the bug.

Store the startup exception on the fixture rather than letting it escape, so one broken emulator does not take the others down with it — but surface it through the guard. Without this, see `test-theatre-audit`.

## 6. Mechanics

- **Reuse the container across the class or module.** Starting a database per test makes the suite unusably slow; isolate with a fresh schema, database, collection or key prefix per test instead.
- **Isolate, do not clean up afterwards.** A unique namespace per test survives a crashed test run; a teardown that deletes rows does not.
- **Disable parallelisation** for any fixture that mutates process-wide state — environment variables, ambient credentials, the default AWS/Azure profile. `[CollectionDefinition("X", DisableParallelization = true)]` or the equivalent.
- **Restore every environment variable** in teardown, unconditionally.
- **Honour a skip variable** (`SKIP_DOCKER_TESTS=1`) so a contributor without Docker can still run the unit suite — and make the report say the suite was skipped.
- **Do not `docker pull` in the test.** Let Testcontainers manage it, and warm the cache in CI with a separate step if startup time matters.
- **Ryuk**, the reaper container, is what cleans up after a killed run. If it is disabled in your environment (`TESTCONTAINERS_RYUK_DISABLED`), containers leak — know which way it is set.

### Windows

Testcontainers needs the Docker Desktop named pipe, or **every** container test fails with "Could not find a valid Docker environment":

```bash
DOCKER_HOST=npipe:////./pipe/dockerDesktopLinuxEngine ./gradlew check --console=plain
```

Run `docker context ls` for the endpoint if that pipe name does not exist. This failure looks like a wall of failing tests and is not a code failure — read the `Caused by` before believing that thirty tests broke. See `ci-failure-triage`.

## 7. Wire it into CI

Decide which workflow the suite belongs in:

| Suite | Workflow |
|---|---|
| No credentials, starts in seconds | The main push/PR workflow |
| Heavy image, or needs an opt-in variable | A separate integration workflow, labelled or scheduled |
| Needs real cloud credentials | Not in CI. File it — see `gap-issue` |

GitHub-hosted Linux runners have Docker; macOS runners do not. If the matrix includes macOS, the container suite must skip there and say so.

Then update the CI documentation — what the suite needs, which variables gate it — and its hand-maintained twin if there is one. See `docs-drift-guard`.

## Checklist

- [ ] Image tag pinned; the parameterised builder constructor used
- [ ] Readiness is a real call through the production client, with a deadline — not a log line
- [ ] Fixture seeds through the adapter's own connection-string/options parser
- [ ] Fixture data covers present / explicitly-null / absent, nesting, arrays, a boundary, a planted secret
- [ ] A start guard fails when Docker is available and the container did not start, carrying the exception
- [ ] A report distinguishes exercised / failed / not run, and "not asked for" from "asked for and broken"
- [ ] Container reused per class; isolation by unique namespace, not by teardown
- [ ] Parallelisation disabled where process-wide state is mutated; environment restored in teardown
- [ ] Placed in the right workflow; documentation and its twin updated

## Related skills

- `test-theatre-audit` — what this suite looks like when the guard is missing
- `api-quirk-fixtures` — making the fixture tell the truth about the real service
- `hexagonal-architecture` — the port/adapter seam these tests exercise
- `ci-failure-triage` — Docker failures that look like code failures
- `gap-issue` — when an adapter genuinely cannot be tested here
