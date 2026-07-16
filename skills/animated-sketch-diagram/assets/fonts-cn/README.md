# CJK font (downloaded on demand)

`LXGWWenKaiScreen.ttf` (~24 MB, SIL OFL 1.1) is not committed here to keep the
repository light. Download it once before rendering diagrams with Chinese/CJK
labels:

```bash
curl -L -o LXGWWenKaiScreen.ttf \
  https://github.com/OLDyade/animated-sketch-diagram/raw/main/assets/fonts-cn/LXGWWenKaiScreen.ttf
```

The build step subsets it to only the characters actually used (a few dozen KB
inlined into the output HTML). Latin-only diagrams do not need this file.
