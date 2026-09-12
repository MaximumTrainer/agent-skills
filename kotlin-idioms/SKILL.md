---
name: kotlin-idioms
description: Write idiomatic Kotlin for a Spring Boot / JPA service — immutability by default, nullability handled at the type level with no `!!`, expression-oriented domain code, and the ktlint/detekt/JSR-305 toolchain that enforces it. Use when writing or reviewing Kotlin, when a `!!` or a needless `var` appears in a diff, when deciding between a nullable type and `Optional` at a port boundary, when data classes meet JPA entities, or when ktlint/detekt fails and the cause is a version coupling rather than the code. Covers the project conventions shared across the Kotlin services here and the gotchas that cost build time.
license: MIT
metadata:
  version: "1.0.0"
---

# Kotlin idioms for a Spring Boot service

Most general Kotlin advice is already well known. What follows is the subset that is **enforced** across the Kotlin services in this space, plus the specific traps that have cost build time — the things a reviewer will actually send a change back for.

Two rules carry most of the weight, and both are checkable mechanically:

> **No `var` where `val` is possible. No `!!` at all.**

## Immutability first

- **Prefer `val` everywhere.** Use `var` only where mutation is provably necessary, and where it is, keep its scope as small as possible. A `var` at class scope is a design decision; a `var` inside a function is usually a fold or a `map` waiting to be written.
- **`data class` for domain entities and value objects**, with `copy()` to produce modified versions. A domain object that mutates in place cannot be shared across a call safely and cannot be compared by value.
- **Immutable collections** — `listOf`, `mapOf`, `setOf`. Reach for `mutableListOf` only where a framework requires it, and convert back at the boundary (`toList()`), because exposing a `MutableList` from a domain type hands a caller the ability to change your state.
- **Declare collection properties as the read-only interface** (`List<T>`, not `ArrayList<T>`), even when the backing instance is mutable.

Note the compiler does not stop `val` from referring to a mutable object. `val items: MutableList<T>` is an immutable reference to a mutable list, which is not immutability.

## Null safety

- **Handle nullability at the type level** with `?` and the Elvis operator (`?:`). The type is the documentation.
- **Never use `!!`.** If the compiler cannot prove non-nullness, either redesign the data flow so the nullable value never reaches that point, or handle the null explicitly. Every `!!` is a `NullPointerException` with a delay on it, and — worse — one that throws with no message about what was null.

  ```kotlin
  // no
  val flow = repository.findByName(name)!!

  // yes — the absence is part of the contract, and the error is legible
  val flow = repository.findByName(name)
      ?: throw NotFoundException("no flow named '$name'")
  ```

- **`Optional<T>` only at a JPA port boundary**, and only for compatibility with Spring Data's generated methods. Prefer Kotlin's nullable types everywhere else — an outbound port should read `fun findByName(name: String): Flow?`, not `Optional<Flow>`. An `Optional` crossing into the domain is a Java idiom leaking through a port. See `hexagonal-architecture`.
- **Prefer `?.let { }` for "do this if present"**, and a `when`/Elvis for "produce a value either way". Do not chain more than two scope functions — `a?.let { it.b }?.run { … }?.also { … }` is harder to read than the `if` it replaced.
- **`lateinit` is a `!!` with extra steps.** Acceptable for framework-injected fields in an adapter; never in the domain. Constructor injection avoids it entirely.
- **Enable JSR-305 strict mode** so platform types from Java libraries are treated as nullable according to their annotations rather than as unchecked:

  ```kotlin
  freeCompilerArgs.addAll("-Xjsr305=strict")
  ```

  Without it, an annotated Java API's nullability is advisory and `!!`-free code can still NPE.

## Expression-oriented code

Favour expressions over statement sequences. The payoff is not brevity — it is that an expression must produce a value on every path, so the compiler finds the case you forgot.

```kotlin
// exhaustive when over a sealed hierarchy: adding a subtype breaks the build
val response = when (result) {
    is Masked      -> MaskedResponse(result.value)
    is Skipped     -> SkippedResponse(result.reason)
    is Failed      -> throw MaskingException(result.cause)
}
```

- **`when` as an expression over a `sealed class` or enum**, with no `else` branch. Omitting `else` is the point: it makes the `when` exhaustive, so a new subtype becomes a compile error at every decision site rather than a silent fall-through.
- **Single-expression functions** where the body is one expression — but keep an explicit return type on anything public. Inferred public return types make a breaking change invisible in the diff.
- **`map`/`filter`/`fold` over accumulation loops.** Use `asSequence()` for long chains over large collections to avoid materialising each intermediate list.
- **No side effects in pure domain functions.** No logging, no clock reads, no I/O. Push them to the adapter layer, which is what makes the domain suite fast and deterministic. See `outside-in-tdd`.
- **Prefer a typed error to an exception for an expected failure.** A sealed result type the caller must handle beats an exception the caller may forget, for failures that are part of the contract. Keep exceptions for genuine faults, and map them centrally.

## Data classes and JPA together

These two conventions conflict, and resolving it badly is a recurring source of subtle bugs.

JPA requires a no-arg constructor, non-final properties and mutable state; `data class` gives you `equals`/`hashCode` over all properties, which breaks Hibernate's identity semantics for entities with generated ids — two unsaved entities with null ids compare equal, and an entity's hash changes when it is persisted.

**Keep them apart.** The domain model is a `data class` with `val`s; the JPA entity is a separate class in the persistence adapter, with a mapping function between them:

```kotlin
// core/domain — immutable, no framework
data class Flow(val id: UUID, val name: String, val requiredTypes: List<String>)

// adapter/outbound/persistence — JPA's rules apply here only
@Entity
@Table(name = "flows")
class FlowEntity(
    @Id var id: UUID,
    var name: String,
    @ElementCollection var requiredTypes: MutableList<String> = mutableListOf(),
) {
    fun toDomain() = Flow(id, name, requiredTypes.toList())
}
```

This is more code than annotating the domain class, and it is the reason the domain stays testable with no database and no Spring context. If you must use a `data class` as an entity, exclude the generated id from `equals`/`hashCode` and know why you did.

Also: the `kotlin("plugin.jpa")` compiler plugin synthesises the no-arg constructors JPA needs, and `kotlin("plugin.spring")` opens classes Spring must proxy. Both are needed for a Spring Data project; neither makes a `data class` safe as an entity.

## Comments and KDoc

- **Self-documenting code first.** Comments explain *why*, never *what*. A comment restating the code is a comment that will drift from it.
- Document non-obvious public functions and exported types with the reason they exist, not a paraphrase of the signature.
- **Do not place a `/** … */` KDoc block immediately before a `@Bean` or `@Order` annotated method** on Kotlin 1.9.x — it triggers a compiler issue. Use `//` line comments there. This is a version-specific workaround: check whether it still applies before propagating it, and record it where it is load-bearing. See `deliberate-decisions`.

## Toolchain

**Versions differ between the services here** — 1.9.20 on JVM 17 in one, 2.0.20 on JVM 21 in another, 2.0.20 on JVM 17 in a third. **Read the project's `build.gradle.kts` rather than assuming**, and do not "align" them across repos in passing; a Kotlin or JVM bump is its own change with its own testing.

| Concern | Convention |
|---|---|
| Formatting | [Kotlin coding conventions](https://kotlinlang.org/docs/coding-conventions.html), enforced by ktlint |
| Line length | 120 characters |
| Indentation | 4 spaces, no tabs |
| Static analysis | detekt, `buildUponDefaultConfig = true`, project config plus a baseline |
| Null interop | `-Xjsr305=strict` |
| Commit style | Imperative mood (`add BcryptMasker strategy`) |

Both linters run inside `./gradlew check`, alongside the test suites — so `check`, not `test`, is the command that tells you whether a change passes. See `verify-and-ship`.

### The detekt / Kotlin version coupling

**detekt embeds a specific Kotlin compiler and refuses to run against a different version.** With detekt 1.23.7 (which embeds Kotlin 2.0.10) on a project compiling with a different Kotlin version, the build fails in a way that looks like a configuration error rather than a version conflict.

Pin the Kotlin artifacts on detekt's **own** classpath, which does not affect how the project compiles:

```kotlin
configurations.matching { it.name == "detekt" }.all {
    resolutionStrategy.eachDependency {
        if (requested.group == "org.jetbrains.kotlin") {
            useVersion("2.0.10")
        }
    }
}
```

This is the first thing to check when detekt breaks after a Kotlin bump — it is not your code. See `ci-failure-triage`.

### Using a detekt baseline honestly

A baseline suppresses existing findings so a new rule can be adopted without fixing everything at once. That is legitimate. What is not:

- **Never regenerate the baseline to make a new finding disappear.** That is how a baseline becomes a permanent amnesty. If a finding is wrong, suppress it at the site with a reason, or change the rule.
- Treat the baseline as debt with a direction of travel: it should shrink. A baseline that grew in a PR is a finding in itself.

## Tests

- **Backtick test names that read as English sentences**, describing behaviour:

  ```kotlin
  @Test
  fun `create flow with duplicate name throws ConflictException`() { … }
  ```

- **Prefer an in-memory implementation of the port** over a mocking framework for anything stateful — `InMemoryFlowRepository` implementing `IFlowRepository`. The compiler keeps it honest against the interface, which a mock cannot do. Use `mockk`/`mockito-kotlin` for a one-off collaborator, not for a repository.
- **Unit tests with no Spring context are the default** for business logic — they run instantly and need no database. Reserve `@SpringBootTest` for HTTP-level and real-persistence concerns. See `outside-in-tdd` and `container-integration-tests`.

## Review checklist

- [ ] No `!!` introduced anywhere
- [ ] No `var` where `val` is possible; no `lateinit` in the domain
- [ ] Domain types are `data class`es with `val`s and no framework annotations
- [ ] JPA entities live in the persistence adapter, separate from domain types
- [ ] Nullable Kotlin types across ports; `Optional` only where Spring Data forces it
- [ ] `when` over sealed types is exhaustive with no `else`
- [ ] Public functions have explicit return types
- [ ] No side effects in domain functions
- [ ] Collections exposed as read-only interfaces
- [ ] `./gradlew check` green — ktlint and detekt included, not just `test`
- [ ] detekt baseline not regenerated to hide a new finding
- [ ] Test names are backticked behaviour sentences

```bash
# the two greps worth running on every Kotlin diff
git diff -U0 | grep -nE '^\+.*!!' | grep -v '!!='
git diff -U0 | grep -nE '^\+\s*(private |internal )?var '
```

## Related skills

- `hexagonal-architecture` — the layer rules, ports as nullable-returning interfaces, DI at the composition root
- `outside-in-tdd` — in-memory port implementations and the red-green sequence
- `verify-and-ship` — `check` rather than `test` as the local gate
- `ci-failure-triage` — a detekt failure that is a version coupling, not a code defect
- `container-integration-tests` — testing the JPA adapter against a real database
- `deliberate-decisions` — recording version-specific workarounds so they are not cargo-culted
