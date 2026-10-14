"""Restricted HTML rendering in a credential-free, network-disabled container."""

from dataclasses import asdict
from html.parser import HTMLParser
import json
import os
from pathlib import Path
import re
import shutil
import subprocess
from uuid import uuid4

from .adapters import artifact_store
from .errors import ErrorCode, ServiceError
from .models import Render


TAGS = set("html head meta title body style div span p br h1 h2 h3 svg g path rect circle ellipse line polyline polygon text tspan defs marker clippath".split())
ATTRIBUTES = set("id class style lang charset xmlns viewbox width height x y x1 x2 y1 y2 cx cy r rx ry d points fill stroke stroke-width stroke-linecap stroke-linejoin stroke-dasharray stroke-dashoffset opacity transform text-anchor dominant-baseline font-family font-size font-weight preserveaspectratio role aria-label".split())


def css(value):
    if re.search(r"\\|/\*|url\s*\(|@import|@font-face|expression\s*\(", value, re.I):
        raise ValueError("External resources are unsupported")


class RestrictedHTML(HTMLParser):
    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.count = 0
        self.in_style = False
        self.styles = []

    def handle_starttag(self, tag, attrs):
        self.count += 1
        if tag not in TAGS or self.count > 2000:
            raise ValueError("Unsupported HTML element")
        if tag == "meta" and (len(attrs) != 1 or attrs[0][0] != "charset"
                              or str(attrs[0][1]).lower() != "utf-8"):
            raise ValueError("Only UTF-8 charset metadata is supported")
        for name, value in attrs:
            if name not in ATTRIBUTES or value is None:
                raise ValueError("Unsupported HTML attribute")
            if name == "xmlns":
                if value != "http://www.w3.org/2000/svg":
                    raise ValueError("Unsupported namespace")
            elif name == "style":
                css(value)
            elif re.search(r"[:\\]|url\s*\(", value, re.I):
                raise ValueError("External resources are unsupported")
        if tag == "style":
            self.in_style = True

    def handle_endtag(self, tag):
        if tag not in TAGS:
            raise ValueError("Unsupported HTML element")
        if tag == "style":
            css("".join(self.styles))
            self.in_style = False
            self.styles.clear()

    def handle_data(self, data):
        if self.in_style:
            self.styles.append(data)

    def handle_decl(self, decl):
        if decl.lower() != "doctype html":
            raise ValueError("Unsupported declaration")

    def handle_pi(self, data):
        raise ValueError("Unsupported processing instruction")


def validate_html(html):
    parser = RestrictedHTML()
    parser.feed(html)
    parser.close()
    if not parser.count or parser.in_style:
        raise ValueError("Incomplete HTML")


def container_command(docker, image, name):
    if not re.fullmatch(r"sha256:[a-f0-9]{64}", image):
        raise ServiceError(ErrorCode.DEPENDENCY_UNAVAILABLE)
    return [docker, "run", "--rm", "--pull=never", "--name", name, "-i", "--network=none",
            "--read-only", "--cap-drop=ALL", "--security-opt=no-new-privileges", "--pids-limit=128",
            "--memory=1g", "--cpus=1", "--user=10001:10001", "--tmpfs=/tmp:rw,noexec,nosuid,size=512m",
            "--log-driver=none", image]


def render(payload):
    try:
        model = Render.model_validate({**payload, "request_id": "internal-render"})
        validate_html(model.html)
    except ValueError:
        raise ServiceError(ErrorCode.INVALID_REQUEST) from None
    image = os.environ.get("COZE_RENDER_IMAGE", "")
    docker = shutil.which("docker")
    if not docker:
        raise ServiceError(ErrorCode.DEPENDENCY_UNAVAILABLE)
    store = artifact_store()
    name = os.environ.get("COZE_RENDER_CONTAINER_NAME") or "coze-render-" + uuid4().hex
    if not re.fullmatch(r"coze-render-[a-f0-9]{32}", name):
        raise ServiceError(ErrorCode.DEPENDENCY_UNAVAILABLE)
    env = {key: value for key, value in os.environ.items() if key.upper() in {"PATH", "SYSTEMROOT", "WINDIR", "TEMP", "TMP"}}
    command = container_command(docker, image, name)
    output = Path("diagram.gif")
    try:
        with output.open("wb") as stream:
            result = subprocess.run(command, input=json.dumps(payload).encode(), stdout=stream,
                                    stderr=subprocess.DEVNULL, env=env, timeout=300, check=False,
                                    creationflags=subprocess.CREATE_NO_WINDOW if os.name == "nt" else 0)
        if result.returncode or not 6 < output.stat().st_size <= 32 * 1024 * 1024:
            raise ServiceError(ErrorCode.DEPENDENCY_UNAVAILABLE if result.returncode == 125 else ErrorCode.UPSTREAM_ERROR)
        from PIL import Image
        with Image.open(output) as gif:
            frames = (model.loop_ms * model.fps + 999) // 1000
            if gif.format != "GIF" or gif.size != (model.width * model.scale, model.height * model.scale):
                raise ServiceError(ErrorCode.UPSTREAM_PROTOCOL_ERROR)
            for index in range(gif.n_frames):
                gif.seek(index)
                gif.load()
        return {"gif": asdict(store.put_file(output, "image/gif")), "width": model.width * model.scale,
                "height": model.height * model.scale, "frames": frames, "fps": model.fps}
    except subprocess.TimeoutExpired:
        raise ServiceError(ErrorCode.TIMEOUT) from None
    finally:
        subprocess.run([docker, "rm", "-f", name], env=env, stdin=subprocess.DEVNULL,
                       stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, timeout=15,
                       creationflags=subprocess.CREATE_NO_WINDOW if os.name == "nt" else 0)
