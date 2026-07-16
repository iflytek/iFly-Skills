# Animated Sketch Diagram

Generates hand-drawn "ink on beige paper" animated architecture and flow
diagrams as a single self-contained HTML (pure SVG + CSS, zero JS runtime),
with flowing dots that trace the system's real topology — branches, merges,
feedback loops. A bundled headless-Chrome renderer exports pixel-perfect,
seamlessly-looping GIFs.

![demo](https://github.com/OLDyade/animated-sketch-diagram/raw/main/examples/agent-loop.gif)

More demos (all unretouched exports):
[examples gallery](https://github.com/OLDyade/animated-sketch-diagram/tree/main/examples).

## Highlights

- **Motion that narrates.** The animation retells the architecture instead of decorating it.
- **One file, zero runtime.** `@keyframes` + `offset-path`; double-click to play, works offline.
- **Seamless-loop GIF export.** All durations divide one global loop; frames are stepped deterministically.
- **Token design system.** Fixed palette / stroke / rhythm — consistent output, not style roulette.
- **Self-check loop.** Renders, reads frames back, fixes, re-renders before delivering.
- **CJK-ready.** OFL LXGW WenKai Screen, auto-subsetted (see `assets/fonts-cn/README.md`).

## Usage

Ask the agent, in any project:

> Draw me an animated sketch diagram of how a RAG pipeline works.

GIF export (once: `npm ci` inside `scripts/`; needs Node.js, Chrome/Chromium, ffmpeg):

```bash
node scripts/render-gif.mjs diagram.html diagram.gif --fps 25 --loop 3000 --scale 2
```

## Credits & Licenses

Skill code MIT (upstream: [OLDyade/animated-sketch-diagram](https://github.com/OLDyade/animated-sketch-diagram)).
Bundled fonts (Kalam, Patrick Hand, Caveat, Excalifont, LXGW WenKai Screen) are
SIL OFL 1.1; [rough.js](https://roughjs.com/) is MIT.
