---
name: hexagonal-architecture
description: Structure an application as ports and adapters so business rules never depend on frameworks, databases, HTTP or vendor SDKs, and can be tested without them. Use when adding a feature, endpoint, repository, integration or masking/transform strategy to a layered codebase; when asked where a class belongs, how to wire dependencies, or to review whether the dependency rule holds; and when a domain class is importing Spring, JPA, Axios, Qt or an SDK type. Covers the layer rules, the order to add a feature in, DI at the composition root, and how to enforce the rule mechanically.
license: MIT
metadata:
  version: "1.0.0"
---

# Hexagonal architecture (ports and adapters)

Business rules go in the middle. Everything the outside world provides — a database, an HTTP client, a message broker, a filesystem, a clock, a random source, a Bluetooth radio — is represented inside as an interface the domain owns, and implemented outside as an adapter.

One rule does all the work:

> **Dependencies always point inward.** Adapters know about ports; ports know about the domain. The domain and application layers know about nothing outside themselves.

The payoff is not architectural purity. It is that the domain becomes a pure function of its inputs, so the tests that cover your actual business rules run in milliseconds with no database, no network and no container — which is what makes `outside-in-tdd` affordable enough to actually do.

## The layers

```
   ┌───────────────────────────────────────────────┐
   │            Driving adapters                    │
   │   REST controllers, CLI, jobs, UI, gRPC        │
   └────────────────────┬──────────────────────────┘
                        │ calls via inbound port
   ┌────────────────────▼──────────────────────────┐
   │             Inbound ports                      │
   │   IFlowService, ISyncApplication, use cases     │
   └────────────────────┬──────────────────────────┘
                        │ implemented by
   ┌────────────────────▼──────────────────────────┐
   │           Application layer                    │
   │   FlowService — orchestration, no business rule │
   └────────────────────┬──────────────────────────┘
                        │ calls via outbound port
   ┌────────────────────▼──────────────────────────┐
   │             Outbound ports                     │
   │   IFlowRepository, Clock, EventPublisher        │
   └────────────────────┬──────────────────────────┘
                        │ implemented by
   ┌────────────────────▼──────────────────────────┐
   │            Driven adapters                     │
   │   JPA adapters, HTTP clients, file storage      │
   └───────────────────────────────────────────────┘
```

The domain sits inside the application layer and is depended on by everything, depending on nothing.

## Layer rules

| Layer | May import | Must never import |
|---|---|---|
| `core/domain/` | Its own language stdlib only | Application, adapters, any framework, ORM or SDK type |
| `core/port/inbound/` | Domain, shared DTOs | Anything else |
| `core/port/outbound/` | Domain, shared DTOs | Anything else |
| `application/` | Core, DTOs, domain exceptions | Any `adapter.*` type, any framework annotation beyond DI |
| `adapter/inbound/*` | Inbound **port interfaces**, DTOs | Concrete application classes, outbound adapters |
| `adapter/outbound/*` | Outbound **port interfaces**, domain | Inbound adapters, other outbound adapters |

Two rules that are easy to get wrong and quietly destroy the benefit:

- **Controllers depend on the port interface, not the concrete service.** `FlowController(private val flows: IFlowService)`, never `FlowService`. If a controller names a concrete class, the compiler will let the next person put a query in it.
- **Adapters depend on the port, not on each other.** An adapter calling another adapter is a hidden coupling the composition root cannot see.

The same shape appears outside server code. In a device or desktop app the ports are a hardware abstraction layer: `Course`, `SplitEvent` and `SplitEngine` need nothing beyond the language's core types, which is exactly what makes them runnable in a bare test harness with no session and no radio.

## Adding a feature — work outward from the port

The order matters, because each step is compiled and tested before the next exists.

1. **Add the outbound port** — declare the data access or side effect the use case will need, in `core/port/outbound/I*Repository`.
2. **Write the in-memory implementation** — `InMemory*Repository` in the test tree. This is a test double the compiler keeps honest, and it comes before the real adapter so the use case can be driven test-first.
3. **Add the inbound port** — declare the use case in `core/port/inbound/I*Service`.
4. **Write the failing unit test** for the service, against the in-memory repository. Watch it fail. (See `outside-in-tdd`.)
5. **Implement the service** in `application/`, injecting only port interfaces.
6. **Implement the real driven adapter** — the JPA/HTTP/file implementation of the outbound port.
7. **Add the driving adapter** — the controller, CLI command or job handler, using the inbound port interface.
8. **Add an integration test** only where HTTP status codes, serialisation or real database behaviour needs coverage.

Note what this order prevents: you cannot write the ORM entity first and let its shape leak into the domain, because the domain already exists and compiles by the time you get to step 6.

## Dependency injection at the composition root

Exactly one place wires the graph, and exactly one place reads the environment.

- A single composition root — `config.ts`, `DomainConfig.java`, a DI module — constructs adapters and hands them to application services.
- **Constructor injection only.** No service locator, no static singleton, no framework field injection into the domain, no global mutable module state.
- **Inject, don't fetch.** Domain objects take their configuration as constructor arguments. Only the application layer touches settings storage, `System.getenv`, `getTimer()` or `Time.now()`. The pattern to reach for is a primary constructor that takes everything (`new SplitEngine(course, listener, latencyMs)`) plus an application-layer convenience that reads settings and delegates (`SplitEngine.fromSettings()`).
- **The clock and the random source are ports.** A domain that calls `now()` directly cannot be tested deterministically, and you will find that out only after the suite starts failing near midnight.
- No module-level mutable state anywhere. A reassembly buffer or cache living on a module makes test order significant, and an order-dependent suite fails for reasons nobody can reproduce.

Every configuration value belongs in the config object, read through an explicit `required()` or with a stated default, and documented in `.env.example` and the README. If two places read the environment, one of them will disagree with the other. See `single-source-constants`.

## Errors at the boundary

- **Typed errors for expected failures**, carrying what the caller needs in order to act — which step failed, which steps completed, whether retrying can help.
- **Map domain errors to transport codes in one place.** A global exception handler turns `NotFoundException` into 404, `ConflictException` into 409, and everything else into a consistent JSON shape. Controllers do not build error responses by hand.
- **Fail loudly at the boundary, degrade precisely inside.** A malformed inbound field drops that field or skips that record — it never becomes a `0` that looks like a measurement. Never fabricate data to keep a happy path happy.
- **No swallowed exceptions.** No empty `catch`. Catch to add context or to compensate, then rethrow.
- Error messages address whoever will read them: user-facing messages say what happened and what to do next; internal ones name the value that was wrong.

## Enforcing the rule mechanically

A convention that is only in a document will drift. Make the build fail instead:

- An architecture test (ArchUnit, Konsist, `dependency-cruiser`, an ESLint boundaries rule, or a custom check) asserting that no type under `core/**` imports `adapter/**` or a framework package.
- A contract test for each port, run against **every** implementation of it — the real adapter and the in-memory fake. When adding a new implementation, make the existing contract test run against it; if it cannot, fix the port, not the test.
- A check that a controller's constructor parameters are all interfaces.

If none of these exists yet, adding the first one is usually a better use of a change than fixing one violation by hand.

## Reviewing an existing codebase

Grep for the violations directly; they are mechanical and quick to find:

```bash
# framework or ORM types inside the domain
grep -rnE 'import (org\.springframework|javax\.persistence|jakarta\.persistence|com\.fasterxml)' \
  --include='*.kt' --include='*.java' src/main/**/core/ src/main/**/domain/

# domain or application reaching outward
grep -rn 'import .*\.adapter\.' src/main/**/core/ src/main/**/application/

# controllers naming concrete services
grep -rnE 'class \w+Controller\(.*: \w+Service[,)]' --include='*.kt' .
```

Report violations with the layer rule each one breaks, and fix by introducing the missing port rather than by moving the class.

## Checklist

- [ ] No class in the domain or ports imports from the application, adapters, or a framework/ORM/SDK
- [ ] No application class imports an adapter type
- [ ] Driving adapters depend on inbound port interfaces; driven adapters implement outbound port interfaces
- [ ] Controllers, UI handlers and job entry points are thin — translate and delegate, no orchestration
- [ ] No business logic in a controller, a repository, or an ORM entity
- [ ] Dependencies wired in one composition root, by constructor, with no static or global state
- [ ] The environment is read in exactly one place
- [ ] Clock, randomness and identity generation are injected ports
- [ ] New ports have a contract test that runs against every implementation
- [ ] New domain exceptions follow the existing pattern and are mapped centrally

## Related skills

- `outside-in-tdd` — the workflow this structure exists to make cheap
- `single-source-constants` — where thresholds and configuration belong
- `container-integration-tests` — testing a driven adapter against a real instance
- `api-quirk-fixtures` — keeping an outbound adapter honest about what the vendor really returns
