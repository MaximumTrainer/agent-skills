---
name: kotlin-idioms
description: The Kotlin conventions enforced across the Spring Boot services here, and the toolchain traps that cost build time - the detekt/Kotlin compiler version coupling, versions that differ per repo, and `check` rather than `test` as the real gate. Use when writing or reviewing Kotlin in these repos, when detekt or ktlint fails after a version bump, when a `!!` or an avoidable `var` appears in a diff, or when deciding what belongs in the domain versus the persistence adapter.
license: MIT
metadata:
  version: "2.0.0"
---

# Kotlin conventions and toolchain traps

Most Kotlin guidance is already well known, and measurement bears that out: an eval run without this skill produced the same advice on immutability, null-safety and the `data class`/`@Entity` conflict — and was *better* on the JPA compiler plugins. So this skill carries only the parts that are local to these repos, or that cost real time to rediscover.

For the general material — prefer `val`, handle nullability at the type level, `when` over sealed types, expression-oriented domain code — just write good Kotlin. The two rules below are the ones a reviewer here will actually send a change back for.

## Two rules, enforced

> **No `!!`. No `var` where `val` is possible.**

`!!` throws without saying what was null. If the compiler cannot prove non-nullness, redesign the flow or handle it:

```kotlin
val flow = repository.findByName(name)
    ?: throw NotFoundException("no flow named '$name'")
```

Outbound ports return nullable Kotlin types (`fun findByName(name: String): Flow?`), not `Optional`. `Optional` appears only where Spring Data's generated methods force it — an `Optional` crossing into the domain is a Java idiom leaking through a port. See `hexagonal-architecture`.

Two greps worth running on every Kotlin diff:

```bash
git diff -U0 | grep -nE '^\+.*!!' | grep -v '!!='
git diff -U0 | grep -nE '^\+\s*(private |internal )?var '
```

## Domain and persistence stay separate

The domain model is a `data class` with `val`s and no framework annotations. The JPA entity is a separate class in the persistence adapter, with a mapping function between them.

This costs a mapper. What it buys is a domain that is testable with no database and no Spring context, and a schema that is not the domain's public API. (The `data class`-as-`@Entity` equality problem is real and well documented elsewhere; it is not the reason this convention exists here.)

## The toolchain traps

### Versions differ per repo — read the build file

`OpenDataMask` is Kotlin 1.9.20 on JVM 17. `OpenFactstore` is 2.0.20 on JVM 21. `SdlcKnowledgeGraph` is 2.0.20 on JVM 17.

**Read `build.gradle.kts` rather than assuming**, and do not "align" them in passing — a Kotlin or JVM bump is its own change with its own testing.

### detekt embeds its own Kotlin compiler

**This is the one that looks like a code failure and is not.** detekt refuses to run against a different Kotlin version than the one it embeds, so after a Kotlin bump the build fails in a way that reads as a configuration error.

Pin the Kotlin artifacts on detekt's **own** classpath. This does not affect how the project compiles:

```kotlin
configurations.matching { it.name == "detekt" }.all {
    resolutionStrategy.eachDependency {
        if (requested.group == "org.jetbrains.kotlin") {
            useVersion("2.0.10")   // whatever this detekt release embeds
        }
    }
}
```

Check this first when detekt breaks after a version change. It is not your code.

### `check`, not `test`

ktlint and detekt run inside `./gradlew check`, alongside the suites. `./gradlew test` passes while the linters would have failed, so `check` is the command that tells you whether a change passes. See `verify-and-ship`.

### The detekt baseline is debt, not amnesty

A baseline suppressing existing findings so a new rule can be adopted is legitimate. **Never regenerate it to make a new finding disappear** — that is how a baseline becomes permanent. If a finding is wrong, suppress it at the site with a reason, or change the rule. A baseline that grew in a PR is itself a finding.

## Conventions

| Concern | Convention |
|---|---|
| Formatting | Kotlin coding conventions, enforced by ktlint |
| Line length | 120 characters |
| Static analysis | detekt, `buildUponDefaultConfig = true`, project config plus baseline |
| Null interop | `-Xjsr305=strict`, so annotated Java nullability is enforced rather than advisory |
| Test names | Backticked sentences: ``fun `create flow with duplicate name throws ConflictException`()`` |
| Test doubles | An in-memory implementation of the port, not a mocking framework, for anything stateful |
| Commit style | Imperative mood |

## Related skills

- `hexagonal-architecture` — ports returning nullable types, domain free of framework
- `verify-and-ship` — `check` as the local gate
- `ci-failure-triage` — a detekt failure that is a version coupling, not a defect
- `outside-in-tdd` — in-memory port implementations
