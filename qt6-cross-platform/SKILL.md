---
name: qt6-cross-platform
description: Build, debug and package a Qt6 C++ desktop application across Linux, Windows, macOS and WebAssembly, including the Qt5-to-Qt6 signal changes that silently break auto-connected slots, AppImage bundling of libraries Qt dlopens at runtime, and the WASM single-thread constraints. Use when working on a Qt or QtWidgets application, migrating from Qt5, packaging a desktop release, debugging a slot that never fires or a TLS failure that only happens on another machine, or targeting Qt for WebAssembly.
license: MIT
metadata:
  version: "1.0.0"
---

# Qt6 cross-platform desktop and WASM

Qt gives you one codebase across four very different runtimes, and charges for it in platform-specific failures that appear only on the platform you did not test. The failures below are silent or misattributed — a slot that never fires, a TLS error on someone else's machine, a crash on first HTTPS — which is what makes them expensive.

## Qt5 → Qt6: the silent slot break

**`QComboBox::currentIndexChanged(const QString&)` was removed in Qt6.**

The consequence is not a compile error. Qt's `connectSlotsByName` auto-connection matches slots by *name*, so an auto-slot named `on_myCombo_currentIndexChanged(QString)` simply **never fires**. The build is clean, the code looks connected, and the feature is dead.

```cpp
// dead in Qt6 — no signal with this signature exists
void MainWindow::on_myCombo_currentIndexChanged(const QString &text);

// correct — explicit connection to a signal that exists
connect(ui->myCombo, &QComboBox::currentTextChanged,
        this, &MainWindow::onMyComboTextChanged);
```

**Watch the startup log for `connectSlotsByName: No matching signal for on_...`.** Every one of those lines is either a dead slot or a broken auto-connection. This is the single highest-value diagnostic in a migrated Qt application — grep the startup output for it before believing anything works:

```bash
./app 2>&1 | grep -i 'no matching signal'
```

More generally, prefer the **pointer-to-member-function `connect` syntax** everywhere. It is checked at compile time, so this entire class of failure becomes a build error instead of silence. Auto-connection by name is a Qt4-era convenience that trades compile-time safety for nothing.

Other Qt6 migration points worth checking: `QRegExp` → `QRegularExpression`, `QVariant` implicit conversions tightened, `endl`/`flush` moved into `Qt::`, `QDesktopWidget` removed, `qrand` removed, and the high-DPI attributes now being defaults.

## Platform initialisation — order matters

Several things must be set **before** the `QApplication` object exists, and a setting made afterwards is silently ignored.

```cpp
int main(int argc, char *argv[]) {
    // Required before QApplication, or embedded QtWebEngine views
    // tear down their host widget.
    QCoreApplication::setAttribute(Qt::AA_ShareOpenGLContexts);

    // QtWebEngine + native child widgets are unstable on the Wayland QPA
    // plugin; force xcb, which works via XWayland on a Wayland session.
    if (qEnvironmentVariableIsEmpty("QT_QPA_PLATFORM"))
        qputenv("QT_QPA_PLATFORM", "xcb");

    // Under xcb the app otherwise ignores the desktop light/dark scheme
    // and is always Light.
    qputenv("QT_QPA_PLATFORMTHEME", "xdgdesktopportal");

    QApplication app(argc, argv);
    ...
}
```

Each of those three lines fixes a specific reproducible failure. Comment them with the failure they prevent, or they will be removed as superstition — see `deliberate-decisions`.

Guard `qputenv` on the variable being unset, so a user or a test can still override the platform.

## Verifying a change without a GUI session

A headless screenshot mode is the highest-value testing affordance a Qt desktop app can have: run a real scripted workload, dump PNGs, quit.

```bash
LD_LIBRARY_PATH=/tmp/qwt6/lib ./build/release/MyApp --screenshots /tmp/shots
```

This makes UI changes verifiable in CI and on a headless machine, and it doubles as the screenshot generator for the documentation. Build it early.

Two constraints:

- The `offscreen` platform plugin may not be bundled in a release build (an AppImage commonly ships only `xcb`). Locally, `xcb` works via XWayland on a Wayland session. If you need true offscreen in a packaged build, bundle the plugin deliberately.
- A non-standard library prefix needs `LD_LIBRARY_PATH`. Keep the exact invocation in the README, because nobody reconstructs it from memory.

See `screenshot-verify`.

## AppImage packaging: libraries Qt `dlopen`s

`linuxdeploy`'s static scan finds what the binary links against. It **cannot** find what Qt loads at runtime via `dlopen`, so those libraries must be bundled by hand. Each omission below is a real crash that only happens on a user's machine:

- **NSS modules** (`libsoftokn3`, `libfreebl3`, `libnssckbi` and friends) — without them QtWebEngine **crashes on first HTTPS request**. Works perfectly on the build machine, which has them system-wide.
- **The OpenSSL pair, matched** (`libssl.so.3` *and* `libcrypto.so.3`). Bundling `libcrypto` alone produces `QSslSocket: TLS initialization failed` on any host with a different OpenSSL 3.0.x point release. They must be bundled together, from the same build.
- **The platform theme plugin** (`xdgdesktopportal`) — otherwise dark mode does not work in the packaged build even though it works locally.
- **Image format, SQL driver and multimedia backend plugins** for anything loaded by name rather than linked.

> **Whenever you add a feature that `dlopen`s anything, bundle it explicitly and add a verify step.**

The verify step is what matters. Bundling without verification just moves the discovery to a user:

```bash
# does the AppImage carry what it needs?
./MyApp.AppImage --appimage-extract >/dev/null
ls squashfs-root/usr/lib | grep -E 'libssl|libcrypto|libsoftokn|libfreebl'
ldd squashfs-root/usr/bin/MyApp | grep 'not found'

# then run it somewhere that is NOT the build machine —
# a minimal container is the cheapest proxy for a user's system
docker run --rm -v "$PWD:/w" -w /w ubuntu:22.04 ./MyApp.AppImage --version
```

Test the packaged artefact on a clean system, every release. A release build verified only on the build machine is not verified.

## Qt for WebAssembly

The WASM target is the same code under substantially different rules.

- **Effectively single-threaded.** Blocking the main thread freezes the browser tab — there is no "unresponsive but recoverable" state. Anything long-running must be chunked, moved to an event-driven state machine, or run in a worker where the toolchain supports it.
- **No blocking dialogs, no nested event loops.** `QDialog::exec()`, `QMessageBox::exec()` and `QEventLoop::exec()` do not work. Convert every one to `open()` plus a signal, or an async callback. This is usually the largest single piece of porting work.
- **No filesystem, no direct sockets.** Persistence goes through browser storage via Qt's abstractions; networking is WebSockets or HTTP only, subject to CORS.
- **No `QProcess`**, no shelling out, no native dialogs.
- **Bluetooth, serial and most hardware access are unavailable**, or available only behind a Web API with a different permission model. Feature-gate these paths rather than letting them fail at runtime.
- Binary size matters. It is a download, and it is on the critical path for first use.

Structure the codebase so this is manageable: a **shared core plus platform adapters**, with everything platform-specific behind a port the core does not know about. Then the WASM build differs by which adapters are compiled in, not by `#ifdef` scattered through business logic. See `hexagonal-architecture`.

## Threading and long-running sessions

For an app processing high-frequency sensor or telemetry data over hours:

- Cross-thread communication through **queued signal/slot connections**, not shared mutable state. `QObject` is not thread-safe, and a `QObject` must not be touched from a thread other than the one it lives in.
- A widget may only be touched from the GUI thread. No exceptions, and the failure is a crash somewhere unrelated.
- Watch memory over the whole session, not at startup. An append-only buffer of samples is the usual leak; bound it, downsample, or write through to storage.
- Prefer `QTimer` over sleeping in a thread, and never sleep on the GUI thread.

## Build and test

- Keep the build commands in the README, and **cross-check them against the CI workflow** — the Qt version, the modules, the extra library prefixes, the qmake/cmake invocation. A README build command that no longer works is the first thing a new contributor hits. See `docs-drift-guard`.
- Test suites split naturally into unit tests over the domain (no widgets, fast), service/model tests, integration tests, and browser tests for the WASM build via Playwright. The domain suite is only fast if the domain has no Qt GUI dependency — which is the payoff for keeping the core free of widgets.
- Do not reference removed or dormant features in documentation or the user guide. Check the register first.

## Checklist

- [ ] Startup log grepped for `connectSlotsByName: No matching signal`
- [ ] New connections use pointer-to-member syntax, not auto-connection by name
- [ ] Pre-`QApplication` attributes present and commented with the failure they prevent
- [ ] Change verified via headless screenshot mode, not only by reasoning
- [ ] Anything newly `dlopen`ed is bundled, with a verify step added
- [ ] Packaged artefact run on a clean system, not just the build machine
- [ ] WASM: no blocking dialogs, no nested event loops, no filesystem or socket assumptions
- [ ] Platform-specific code behind an adapter, not `#ifdef` in the domain
- [ ] Build commands in the README match the CI workflow

## Related skills

- `hexagonal-architecture` — shared core, platform adapters, testable domain
- `screenshot-verify` — headless capture for verification and documentation
- `deliberate-decisions` — the pre-`QApplication` lines and the dormant-feature list
- `docs-drift-guard` — keeping build instructions and the user guide truthful
- `ci-failure-triage` — a platform-only failure that is not an infrastructure failure
