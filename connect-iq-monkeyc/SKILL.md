---
name: connect-iq-monkeyc
description: Write, test and ship Garmin Connect IQ apps in Monkey C, including FIT developer fields, BLE scanning, and the API-level restrictions that silently break things. Use when working on a Connect IQ watch app, data field or widget, when writing Monkey C, when recording custom data into a Garmin activity via FitContributor, when handling BLE advertisements on a watch, or when a developer field vanishes from the recorded file. Covers the testability design rules, monkeydo unit tests, and the ecosystem traps that each cost hours.
license: MIT
metadata:
  version: "1.0.0"
---

# Connect IQ / Monkey C

Connect IQ is an unusually unforgiving target: the API level gates the language itself, several failure modes are entirely silent, and the SDK needs an interactive Garmin login so it cannot run on hosted CI. Most of the cost in this ecosystem comes from a small set of traps that are obvious only after you have hit them.

## API level gates the language

`minApiLevel` in `manifest.xml` determines which language and library features exist. Raising it drops support for older devices, so treat it as a deliberate decision with its own issue rather than something to bump when convenient.

At API `3.1.0`, notable absences:

- **No `String.split`.** Write a helper (`Course.splitString`) and use it everywhere.
- Several collection and string conveniences from later levels are missing. Check the API reference for the level you target, not the newest.

Build with type checking at the strictest level, and treat a new type warning as a failing build:

```bash
monkeyc -l 1 -f monkey.jungle -o out/app.prg -y developer_key.der -d <device>
```

Build for **one device at each end of your supported range** — one at the minimum API level and one current — because a feature can compile for one and not the other.

## Numbers: the trap that produces negative time

**A Monkey C `Number` is a signed 32-bit integer.** A protocol's 32-bit unsigned counter does not fit.

```
decodeNumber(UINT32) yields a Long.
```

A chip that has been running for a while decodes **negative** if you narrow it to `Number`. The rule that works:

> Subtract the reference point while still in `Long`, then narrow.

Subtract the rep start from the raw counter as a `Long`, and only then convert to `Number`. Narrowing first overflows; narrowing after the subtraction is safe because the difference is small.

### Units and precision

Be explicit about what a unit means versus what the source can measure. A device tick of 1/1024 s is just under a millisecond. Carrying durations in microseconds because that is finer than the source can measure is correct; believing the source measures microseconds is not — and the distinction matters because:

> **Subtract in native ticks and convert once.** Converting each leg and adding the results accumulates rounding error per leg.

Put that reasoning in a comment. It looks like an over-complication otherwise, and it will be "simplified". See `deliberate-decisions`.

## FIT developer fields — three silent failures

Recording custom data into a Garmin activity via `FitContributor` has three ways to lose data with no error at all.

1. **Hold field references in class scope for the session's lifetime.** A field created in a local variable is garbage collected, and it and its data vanish from the file. The file still validates.

2. **`setData()` and `addLap()`/`save()` must not run in one path with no yield.** Lap and session developer fields are dropped if they do. The fix is to defer by a timer tick:

   ```
   setData(...)  →  [timer tick]  →  addLap()
   ```

   This looks like an unnecessary indirection and is load-bearing. **Do not simplify it away** — the fields silently disappear and the file still validates. Record it in the deliberate-decisions register.

3. **`addLap()` can only happen *now*.** Laps cannot be back-dated. If the upstream source reports events with their own timestamps, you cannot reconstruct history — hence one Garmin lap per source event, created as it arrives.

Test this with a **`FakeSession` that records `createField`/`setData`/`addLap` calls in order**. Do not try to fake `Toybox.FitContributor` itself. Fake at the seam you own, not below it — see `outside-in-tdd`.

## BLE on a watch

- **There is no scan filter in Connect IQ.** Every advertisement from every device in range arrives in `onScanResults`, and must be rejected in Monkey C. Keep that path cheap and **allocation-free** — it runs constantly, in a memory-constrained environment, and allocating per advertisement will cause out-of-memory on a busy street.
- **A broadcast-only device accepts no connection**, so none of the connection-count limits apply. Know which model you are in: a broadcaster needs scanning only, and code written for a connection-oriented protocol against a broadcaster will never work no matter how much it is debugged.
- Keep the frame layout in **one** place, and mirror it in any companion tool with a **vector test that fails when the two drift apart**. Two independent implementations of a byte layout will diverge; a shared vector file is what catches it. See `single-source-constants`.
- Where a layout comes from a specification shared in confidence: implement it, do not reproduce it. No byte tables in public issues, and keep the document out of the repository.

## Memory

The runtime limits are small — tens of kilobytes for a watch app, less for a data field, and they vary by device.

- No large collections, no accumulating history in RAM. Write to the FIT file and let it go.
- Avoid allocation in hot paths (`onScanResults`, `compute()`, `onUpdate()`).
- Reuse buffers rather than creating strings per frame. String concatenation in a loop is the usual culprit.
- Test on the **lowest-memory device** you support, not the newest. `monkeyc` reports the memory ceiling per device; an app that fits a Fenix may not fit a Forerunner.

## Design rules that keep it testable

The testable core is the part that needs nothing from the device.

- **Keep `Toybox` out of the domain.** Domain types should need nothing beyond `Toybox.Lang` and `Toybox.Math`. That is precisely what makes them runnable under `monkeydo -t` with no session, no radio and no GPS.
- **Inject, don't fetch.** Domain objects take configuration as constructor arguments; only the app layer touches `Application.Storage`, `Properties`, `System.getTimer()` or `Time.now()`. The pattern that works:

  ```
  new SplitEngine(course, listener, latencyMs)   // primary — testable
  SplitEngine.fromSettings()                    // app-layer convenience
  ```

  A class that reads a property in its initialiser cannot be tested at two different settings.
- **No module-level mutable state.** A reassembly buffer on a module makes test order significant, and an order-dependent suite fails for reasons nobody can reproduce. Move it onto an instance the delegate owns; failing that, `reset()` as the first line of every test.
- Prefer a pure function over a stateful class, and prefer passing a value in over reading a property inside.

See `hexagonal-architecture`.

## The test rings

```
ring 1  acceptance criterion (the issue)
ring 2  simulator / fake-device end-to-end
ring 3  Monkey C unit test — monkeydo -t          ← usually the entry point
ring 4  pure function / decoder vector
```

Ring 3 is normally where you start. Ring 2 needs the simulator and a scripted fake device; ring 4 is right when the change is purely a decode or a calculation. A companion Python tool can carry the decoder vectors, cross-checked against the Monkey C implementation.

```bash
monkeydo out/app.prg <device> -t     # run the unit tests
```

One criterion, one red test, one green, one commit. See `outside-in-tdd`.

## CI

**Do not put `monkeyc` on GitHub-hosted CI.** The SDK requires a Garmin developer login and a developer key, so hosted runners cannot build. What works:

- Hosted CI runs what does not need the SDK: markdown and shell linting, the companion tool's Python/JS tests, and the decoder vector tests.
- The Monkey C build and `monkeydo` run on a **self-hosted runner** with the SDK installed, or locally before the PR — with the result stated in the PR.

Never commit `*.der`, developer keys, or captures containing phone-identifying data. The device's own address is generally fine; the phone's is not.

## Definition of done

- [ ] Every acceptance criterion is a passing test or a documented manual step with its real result
- [ ] Tests were written first and failed first — say so in the PR
- [ ] `monkeyc -l 1` clean for one minimum-API device and one current device
- [ ] `monkeydo -t` green
- [ ] Hosted CI green
- [ ] Protocol changes ship with the capture, the vector, and the companion-tool update together
- [ ] Design docs still describe the code
- [ ] Memory checked on the lowest-memory supported device
- [ ] PR references its issue with criteria ticked because they are true

## Do not

- Do not add products to `manifest.xml` you cannot build for.
- Do not raise `minApiLevel` casually — it drops devices. Dedicated issue.
- Do not weaken a test to make it pass, or delete a failing test without saying why in the PR.
- Do not extend a module recorded as retired. Check the register — see `deliberate-decisions`.
- Do not claim hardware verification you did not perform. "Not run — no device available" is an acceptable PR line; a fabricated green is not. See `gap-issue`.

## Related skills

- `outside-in-tdd` — the ring discipline and the fake-at-the-seam rule
- `hexagonal-architecture` — keeping `Toybox` out of the domain
- `deliberate-decisions` — the timer-tick deferral and the retired modules
- `single-source-constants` — one frame layout, mirrored with a vector test
- `gap-issue` — recording what could not be verified without hardware
