---
name: screenshot-verify
description: Capture what an application actually renders, and verify the capture is truthful before drawing conclusions from it. Use whenever a change touches the UI, when asked to run or screenshot an app, before claiming a visual change works, and when regenerating screenshots for documentation. Covers the capture flags that silently produce wrong images — virtual time blanking animated charts, captureBeyondViewport crushing responsive layouts — checking the DOM before reporting a rendering bug, headless capture for desktop apps, and credential hygiene for authenticated captures.
license: MIT
metadata:
  version: "1.0.0"
---

# Screenshot the app, then verify the screenshot

A screenshot is evidence only if the capture itself is sound. Several standard headless-capture options produce images that look exactly like application bugs, and they have already caused non-existent defects to be reported as real.

So the discipline has two halves, and the second is the one people skip:

> Capture the app. Then **check the DOM** before believing what the image shows.

If the DOM is healthy and the image is not, the capture is lying. Fix the capture, not the app.

## The capture traps

### 1. `--virtual-time-budget` blanks animated content

Chart libraries animate their paths on mount. Under virtual time the animation **never completes**, so `chrome --headless --screenshot` captures axes and gridlines with no data lines at all.

It looks exactly like "the chart has no data" — and that is how it gets reported.

Use **real time** and a real wait. Poll for the rendered artefact rather than guessing a duration:

```js
// wait for the thing you are about to photograph
await waitFor(() => document.querySelectorAll('.recharts-line-curve').length > 0);
await sleep(1500);   // then let the animation finish
```

### 2. `captureBeyondViewport: true` crushes responsive layouts

It resizes the viewport to capture the full page, which re-triggers any `ResizeObserver` — so a responsive container is mid-relayout when the capture lands. Content ends up compressed into a narrow strip on the left.

It looks exactly like "the component is rendering at the wrong width".

Use a **tall window and a plain viewport capture** instead:

```js
'--window-size=1300,2600'    // tall enough that the target is in view
// then Page.captureScreenshot with no captureBeyondViewport
```

To capture one component, measure its rect and pass a `clip` — do not resize the page:

```js
const box = JSON.parse(await ev(`(() => {
  const el = [...document.querySelectorAll('.card')].find(e => e.textContent.includes('Next 48 Hours'));
  const r = el.getBoundingClientRect();
  return JSON.stringify({ x: r.x, y: r.y, width: r.width, height: r.height });
})()`));
await send('Page.captureScreenshot', { format: 'png', clip: { ...box, scale: 2 } });
```

### 3. The port may not be your app

A conventional dev-server port (5173, 3000, 8080) is frequently already occupied by an unrelated project. Navigating to it screenshots **someone else's product**, convincingly.

Pick an unusual port, pin it, and **verify the identity of what answered**:

```bash
npx vite --port 5199 --strictPort
curl -s http://localhost:5199 | grep -i '<title>'    # is this actually our app?
```

`--strictPort` is essential: without it the server silently picks a different port and your capture hits whatever is on the one you expected.

### 4. A backgrounded server with a shell redirect dies silently

`npx vite & > log 2>&1` exits the wrapper and takes the server with it. Use the harness's own background mechanism on the server command itself (`run_in_background: true`), not a shell `&`.

Then **poll, never sleep**:

```bash
timeout 45 bash -c 'until curl -sf http://localhost:5199 >/dev/null 2>&1; do sleep 1; done'
```

## Verify before believing

If something looks empty, squashed or missing, interrogate the DOM before reporting a bug:

```js
document.querySelectorAll('.recharts-line-curve').length                    // paths present?
[...document.querySelectorAll('.recharts-line-curve')].map(p => p.getAttribute('d').length)
document.querySelector('.recharts-surface').getBoundingClientRect().width   // laid out?
[...document.querySelectorAll('.recharts-line-curve')].map(p => p.style.strokeDasharray)
```

A `stroke-dasharray` of `"845px 0px"` means the animation completed and the line is fully drawn. If the elements exist, have non-trivial path data, and the container has a sensible width — the DOM is healthy and the screenshot is wrong.

Also **collect page errors** and report them alongside the image. A blank region is often an exception during render, and the console says so immediately:

```js
ws.addEventListener('message', e => { const m = JSON.parse(e.data);
  if (m.method === 'Runtime.exceptionThrown') errors.push(m.params.exceptionDetails.text); });
```

**Always read the resulting image.** A capture you did not look at is not verification, and a report based on one is not honest. See `gap-issue`.

## Driving the app

### React inputs

`el.value = x` does **not** fire React's `onChange` — React tracks the value on the node and sees no change. Use the native setter:

```js
const proto = HTMLInputElement.prototype;
Object.getOwnPropertyDescriptor(proto, 'value').set.call(el, value);
el.dispatchEvent(new Event('input', { bubbles: true }));
// <select>: the same trick on HTMLSelectElement.prototype, then dispatch 'change'
```

### Demo mode over credentials

Prefer a demo or fixture mode where one exists. It needs no credentials, is deterministic, and still exercises the real domain code. It is also the right mode for documentation screenshots, because the numbers in them are then synthetic — see `synthetic-test-data`.

For a real account, inject the session **before app code runs**:

```js
await send('Page.addScriptToEvaluateOnNewDocument', {
  source: `sessionStorage.setItem('app_auth', JSON.stringify({
    athleteId: ${JSON.stringify(process.env.ICU_ID)},
    accessToken: ${JSON.stringify(process.env.ICU_KEY)} }));`,
});
```

Credentials from the environment only. Use a throwaway `--user-data-dir` under the scratchpad and **delete it afterwards** — a Chrome profile holds cookies and tokens. Never commit one, never write credentials to a file. See `live-api-probe`.

## Headless capture for a desktop app

A native application needs the same affordance, and building it in is worth far more than driving the GUI from outside. A screenshot mode that runs a real scripted workload, dumps PNGs and quits makes UI changes verifiable on a headless machine and doubles as the documentation screenshot generator:

```bash
LD_LIBRARY_PATH=/tmp/qwt6/lib ./build/release/MyApp --screenshots /tmp/shots
```

Two constraints: a packaged build may bundle only the `xcb` platform plugin and not `offscreen` (locally `xcb` works via XWayland on a Wayland session), and a non-standard library prefix needs `LD_LIBRARY_PATH`. Keep the exact invocation in the README. See `qt6-cross-platform`.

Where a theme matters, set it explicitly — a dark-mode screenshot generally needs a settings value, not a flag.

## Screenshots for documentation

- **Regenerate them when the UI changes.** An old image beside new prose is a documentation defect, and it is the most-noticed kind. Where a script exists (`scripts/update-screenshots.sh`), use it so every image is captured the same way.
- Keep them in one place the docs reference by relative path.
- Use demo/fixture data, never a real account — a documentation screenshot is published.
- Pin the window size and device scale factor so images stay consistent between runs, and diffs stay reviewable.

See `docs-drift-guard`.

## Clean up

Delete the driver script, the browser profile and the dev server. Write drivers to the scratchpad, not the repository.

```bash
pid=$(netstat -ano | grep ":5199" | grep LISTENING | awk '{print $5}' | head -1)
powershell -Command "Stop-Process -Id $pid -Force -ErrorAction SilentlyContinue"
```

Screenshots may stay in the scratchpad; a browser profile containing session tokens may not.

## Checklist

- [ ] Real time, not virtual time; waited for the rendered artefact, not a fixed guess
- [ ] No `captureBeyondViewport`; tall window, or a measured `clip`
- [ ] Unusual pinned port with `--strictPort`, and the served `<title>` verified as ours
- [ ] Server started via the harness's background mechanism, and polled — not slept
- [ ] DOM interrogated before reporting any rendering bug
- [ ] Page errors collected and reported with the image
- [ ] I actually looked at the resulting image
- [ ] Demo mode preferred; any credentials from the environment only
- [ ] Browser profile and driver script deleted

## Related skills

- `qt6-cross-platform` — headless screenshot mode in a native desktop app
- `docs-drift-guard` — keeping documentation screenshots current
- `live-api-probe` — credential hygiene for an authenticated capture
- `synthetic-test-data` — why documentation screenshots should use fixture data
- `three-best-practices` / `r3f-best-practices` — capturing a WebGL canvas, which needs its own frame wait
