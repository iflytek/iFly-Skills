"""Credential-free, bounded HTML/SVG/CSS to GIF entry for workflow execution."""
import os
import re
import subprocess
from html.parser import HTMLParser
from pathlib import Path

TAGS = set("html head title body style div span p br h1 h2 h3 svg g path rect circle ellipse line polyline polygon text tspan defs marker clippath".split())
ATTRIBUTES = set("id class style xmlns viewbox width height x y x1 x2 y1 y2 cx cy r rx ry d points fill stroke stroke-width stroke-linecap stroke-linejoin stroke-dasharray stroke-dashoffset opacity transform text-anchor dominant-baseline font-family font-size font-weight preserveaspectratio role aria-label".split())

def validate_css(value):
    # The restricted dialect deliberately excludes escapes, comments and all URL loads.
    if re.search(r"\\|/\*|url\s*\(|@import|@font-face|expression\s*\(", value, re.I):
        raise ValueError("CSS resource loading and escaped CSS are unsupported")

class StaticDiagram(HTMLParser):
    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.count = 0
        self.in_style = False
        self.style = []

    def handle_starttag(self, tag, attrs):
        self.count += 1
        if tag not in TAGS or self.count > 2000:
            raise ValueError("Unsupported diagram element")
        for name, value in attrs:
            if name not in ATTRIBUTES or value is None:
                raise ValueError("Unsupported diagram attribute")
            if name == "xmlns" and value != "http://www.w3.org/2000/svg":
                raise ValueError("Unsupported namespace")
            if name != "xmlns" and re.search(r"[:\\]|url\s*\(", value, re.I) and name != "style":
                raise ValueError("Resource references are unsupported")
            if name == "style":
                validate_css(value)
        if tag == "style":
            self.in_style = True

    def handle_endtag(self, tag):
        if tag not in TAGS:
            raise ValueError("Unsupported diagram element")
        if tag == "style":
            validate_css("".join(self.style))
            self.in_style = False
            self.style = []

    def handle_data(self, data):
        if self.in_style:
            self.style.append(data)

    def handle_decl(self, decl):
        if decl.lower() != "doctype html":
            raise ValueError("Unsupported declaration")

    def handle_pi(self, data):
        raise ValueError("Processing instructions are unsupported")

    def unknown_decl(self, data):
        raise ValueError("Unsupported declaration")

def validate_html(html):
    if not isinstance(html, str) or not html.strip() or len(html.encode("utf-8")) > 256 * 1024:
        raise ValueError("HTML must contain 1 to 262144 UTF-8 bytes")
    parser = StaticDiagram()
    parser.feed(html)
    parser.close()
    if parser.in_style or not parser.count:
        raise ValueError("Incomplete diagram HTML")

def render_html(html, output_dir, width=800, height=500, fps=10, duration_ms=2000, scale=1):
    validate_html(html)
    for value, minimum, maximum in (
        (width, 64, 1600), (height, 64, 1200), (fps, 1, 25),
        (duration_ms, 100, 5000), (scale, 1, 2),
    ):
        if type(value) is not int or not minimum <= value <= maximum:
            raise ValueError("Invalid rendering dimensions or timing")
    frames = max(1, (duration_ms * fps + 999) // 1000)
    if frames * width * height * scale * scale > 120_000_000:
        raise ValueError("Render exceeds the 120 million pixel-frame budget")
    paths = [os.environ.get(name, "") for name in (
        "IFLYTEK_NODE_EXECUTABLE", "IFLYTEK_CHROME_EXECUTABLE", "IFLYTEK_FFMPEG_EXECUTABLE")]
    if any(not Path(value).is_absolute() or not Path(value).is_file() for value in paths):
        raise ImportError("Configure absolute Node, Chromium and ffmpeg executable paths")
    directory = Path(output_dir)
    source = directory / "diagram.html"
    output = directory / "diagram.gif"
    source.write_text(html, encoding="utf-8")
    try:
        # Fixed script/arguments, no shell, no credential or ambient Node option inheritance.
        env = {key: value for key, value in os.environ.items()
               if key.upper() in {"PATH", "SYSTEMROOT", "SYSTEMDRIVE", "WINDIR", "PATHEXT",
                                  "TMP", "TEMP", "TMPDIR", "LANG", "LC_ALL"}}
        env["IFLYTEK_CHROME_EXECUTABLE"] = paths[1]
        env["IFLYTEK_FFMPEG_EXECUTABLE"] = paths[2]
        subprocess.run([
            paths[0], str(Path(__file__).with_name("render-gif.mjs")), str(source), str(output),
            "--restricted", "--width", str(width), "--height", str(height), "--fps", str(fps),
            "--loop", str(duration_ms), "--scale", str(scale),
        ], check=True, shell=False, env=env, stdin=subprocess.DEVNULL,
            stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        if output.is_symlink() or not output.is_file() or not 6 < output.stat().st_size <= 32 * 1024 * 1024:
            raise RuntimeError("Invalid GIF artifact")
        with output.open("rb") as stream:
            if stream.read(6) not in (b"GIF87a", b"GIF89a"):
                raise RuntimeError("Invalid GIF signature")
        return {"width": width * scale, "height": height * scale, "frames": frames, "fps": fps}
    finally:
        source.unlink(missing_ok=True)
