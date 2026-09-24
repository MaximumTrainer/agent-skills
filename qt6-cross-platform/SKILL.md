---
name: qt6-cross-platform
description: The Qt6 traps that cost real time in this codebase - initialisation that must happen before QApplication, libraries Qt dlopens that packaging misses, and verifying the packaged artefact somewhere other than the build machine. Use when working on a Qt6 C++ desktop or WASM build, migrating from Qt5, packaging an AppImage, or debugging something that works locally and fails for users.
license: MIT
metadata:
  version: "2.0.0"
---

# Qt6 cross-platform

Measured note: an eval run without this skill already identified the removed `QComboBox::currentIndexChanged(const QString&)` overload and its silent auto-slot failure, named NSS modules as the cause of a QtWebEngine crash on first HTTPS, and diagnosed `QDialog::exec()` blocking the WASM main thread. Those are well-documented and the model knows them. What follows is what it did not produce.

## Initialisation order — before `QApplication`

Several things are silently ignored if set after the `QApplication` object exists. Each line below fixes a specific reproducible failure, so comment it with the failure it prevents or it will be removed as superstition. See `deliberate-decisions`.

```cpp
int main(int argc, char *argv[]) {
    // Required before QApplication, or embedded QtWebEngine views tear down
    // their host widget.
    QCoreApplication::setAttribute(Qt::AA_ShareOpenGLContexts);

    // QtWebEngine + native child widgets are unstable on the Wayland QPA
    // plugin. xcb works via XWayland. Guard it so a user or test can override.
    if (qEnvironmentVariableIsEmpty("QT_QPA_PLATFORM"))
        qputenv("QT_QPA_PLATFORM", "xcb");

    // Under xcb the app otherwise ignores the desktop light/dark scheme and is
    // always Light.
    qputenv("QT_QPA_PLATFORMTHEME", "xdgdesktopportal");

    QApplication app(argc, argv);
}
```

## The diagnostic for a migrated app

`connectSlotsByName` matches auto-slots by *name*, so a slot bound to a removed signal signature simply never fires — clean build, dead feature. Grep the startup output:

```bash
./app 2>&1 | grep -i 'no matching signal'
```

**Every one of those lines is a dead slot.** This is the highest-value single check on a Qt5→Qt6 migration, and it costs one command. Prefer pointer-to-member `connect` in new code so the whole class becomes a compile error instead.

## Verify the package somewhere other than the build machine

`linuxdeploy` finds what the binary links against. It cannot find what Qt `dlopen`s at runtime, so those must be bundled by hand — NSS modules, the matched `libssl`/`libcrypto` pair, the platform theme plugin, anything loaded by name.

Knowing that is not the hard part. **The hard part is that the build machine has all of it system-wide, so the packaged artefact appears to work.** Bundling without verification just moves discovery to a user:

```bash
./MyApp.AppImage --appimage-extract >/dev/null
ls squashfs-root/usr/lib | grep -E 'libssl|libcrypto|libsoftokn|libfreebl'
ldd squashfs-root/usr/bin/MyApp | grep 'not found'

# the actual test: a machine that is not yours
docker run --rm -v "$PWD:/w" -w /w ubuntu:22.04 ./MyApp.AppImage --version
```

> **Whenever you add a feature that `dlopen`s anything, bundle it explicitly and add a verify step in the same change.**

## Build a headless screenshot mode

The highest-value testing affordance a Qt desktop app can have: run a real scripted workload, dump PNGs, quit. It makes UI changes verifiable on a headless machine and doubles as the documentation screenshot generator.

```bash
LD_LIBRARY_PATH=/tmp/qwt6/lib ./build/release/MyApp --screenshots /tmp/shots
```

Two constraints: a packaged build may bundle only the `xcb` platform plugin and not `offscreen` (locally `xcb` works via XWayland), and a non-standard library prefix needs `LD_LIBRARY_PATH`. Keep the exact invocation in the README — nobody reconstructs it from memory. See `screenshot-verify`.

## WASM: structure, not just symptoms

The blocking-dialog problem is known. The structural answer is what matters: a **shared core plus platform adapters**, so the WASM build differs by which adapters compile in, not by `#ifdef` scattered through business logic. Then "no filesystem, no `QProcess`, no direct sockets, no nested event loops" becomes a list of adapters you do not build, rather than a migration that touches every file. See `hexagonal-architecture`.

The domain suite is only fast if the core has no widget dependency — which is the same property that makes the WASM port tractable.

## Checklist

- [ ] Startup log grepped for `connectSlotsByName: No matching signal`
- [ ] Pre-`QApplication` attributes present and commented with the failure each prevents
- [ ] Anything newly `dlopen`ed is bundled, with a verify step added in the same change
- [ ] Packaged artefact run on a clean system, not the build machine
- [ ] Change verified via headless screenshot mode, not only by reasoning
- [ ] Platform-specific code behind an adapter, not `#ifdef` in the domain
- [ ] README build commands match the CI workflow

## Related skills

- `hexagonal-architecture` — shared core, platform adapters
- `screenshot-verify` — headless capture for verification and docs
- `deliberate-decisions` — the pre-`QApplication` lines and the dormant-feature list
- `docs-drift-guard` — keeping build instructions truthful
