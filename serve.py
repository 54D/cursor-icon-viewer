#!/usr/bin/env python3
"""Serve the Cursor icon viewer from the local install.

Reads the packed id catalog and the icon font out of Cursor.app at startup.
Copies neither into this folder. See README.md for the decode.
"""

import json
import os
import re
import sys
import webbrowser
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from itertools import chain
from pathlib import Path
from urllib.parse import urlparse

PRODUCT_FILE_DIR = Path("product.json")
FONT_FILE_DIR = Path("out", "media", "cursor-icons-16.woff2")
MODULE_KEY = '"cursor-icons.js"'


def is_name_tokens(tokens):
    return (
        len(tokens) >= 50
        and all(re.compile(r"[0-9a-z][0-9A-Za-z-]+").fullmatch(token) for token in tokens)
        and sum("-" in token[1:] for token in tokens) >= 10
    )


def decode_names(tokens):
    names = []
    prev = ""
    for token in tokens:
        keep = int(token[0], 36)
        if keep > len(prev):
            raise SystemExit("Packed id prefix is longer than the previous id.")
        prev = prev[:keep] + token[1:]
        names.append(prev)
    if len(set(names)) != len(names):
        raise SystemExit("Decoded icon ids are not unique.")
    return names


def decode_codepoints(tokens):
    points = []
    value = 0
    for token in tokens:
        value += int(token, 36)
        if not 0 <= value <= 0x10FFFF:
            raise SystemExit("Decoded codepoint is outside Unicode.")
        points.append(value)
    return points


def load_install():
    """Find the Cursor install and decode its icon catalog.

    Returns the icon ids, their codepoints, the parsed product.json, the name
    of the workbench bundle the catalog came from, and the icon font path.
    """
    app_env = os.environ.get("CURSOR_APP")
    app_roots = [Path(app_env).expanduser()] if app_env else []
    app_roots += [Path("/Applications/Cursor.app"), Path.home() / "Applications" / "Cursor.app"]
    # A root is either the .app bundle or the resources/app directory inside it.
    app_dir_candidates = list(
        chain.from_iterable(map(lambda root: (root / "Contents" / "Resources" / "app", root), app_roots))
    )
    app_dir = next(
        (d for d in app_dir_candidates if (d / FONT_FILE_DIR).is_file() and (d / PRODUCT_FILE_DIR).is_file()),
        None,
    )
    if app_dir is None:
        raise SystemExit(
            "Cursor was not found. "
            "Install it, or set CURSOR_APP to the .app bundle or to its resources/app directory."
        )

    workbench_dir = app_dir / "out" / "vs" / "workbench"
    bundle_file = next(
        (
            workbench_dir / name
            for name in ("workbench.glass.main.js", "workbench.desktop.main.js")
            if (workbench_dir / name).is_file()
        ),
        None,
    )
    if bundle_file is None:
        raise SystemExit(f"No workbench bundle under {workbench_dir}")

    bundle_text = bundle_file.read_text(encoding="utf-8")
    at = bundle_text.find(MODULE_KEY)
    if at < 0:
        raise SystemExit("cursor-icons.js was not found in the workbench bundle.")
    start = at + len(MODULE_KEY)
    tokenized = [s.split(" ") for s in re.compile(r'"((?:[^"\\\n]|\\[\s\S])*)"').findall(bundle_text, start, start + 100_000)]
    name_lists = [tokens for tokens in tokenized if is_name_tokens(tokens)]
    if len(name_lists) != 1:
        raise SystemExit(f"Expected one packed id string, found {len(name_lists)}.")
    names = decode_names(name_lists[0])
    delta_lists = [
        tokens
        for tokens in tokenized
        if len(tokens) == len(names) and all(re.compile(r"-?[0-9a-z]+").fullmatch(token) for token in tokens)
    ]
    if len(delta_lists) != 1:
        raise SystemExit(f"Expected one codepoint string, found {len(delta_lists)}.")
    points = decode_codepoints(delta_lists[0])

    product = json.loads((app_dir / PRODUCT_FILE_DIR).read_text(encoding="utf-8"))
    return names, points, product, bundle_file.name, app_dir / FONT_FILE_DIR


def serve(catalog, font):
    routes = {
        "/": ((Path(__file__).resolve().parent / "index.html").read_bytes(), "text/html; charset=utf-8"),
        "/api/icons": (json.dumps(catalog).encode("utf-8"), "application/json"),
        "/font/cursor-icons.woff2": (font.read_bytes(), "font/woff2"),
    }

    class Handler(BaseHTTPRequestHandler):
        def do_GET(self):
            route = routes.get(urlparse(self.path).path)
            if route is None:
                self.send_error(404)
                return
            body, content_type = route
            self.send_response(200)
            self.send_header("Content-Type", content_type)
            self.send_header("Content-Length", str(len(body)))
            self.send_header("Cache-Control", "no-store")
            self.end_headers()
            self.wfile.write(body)

    # Threaded, because Chrome holds idle preconnect sockets that would block a serial server.
    server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
    host, port = server.server_address
    url = f"http://{host}:{port}/"
    print(f"Cursor {catalog['version']}  {len(catalog['icons'])} icons  {url}", flush=True)
    webbrowser.open(url)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print()
    finally:
        server.server_close()


def main():
    args = sys.argv[1:]
    if args not in ([], ["--list"]):
        raise SystemExit("usage: python3 serve.py [--list]")
    names, points, product, bundle, font_dir = load_install()
    catalog = {
        "version": product.get("version"),
        "commit": product.get("commit"),
        "bundle": bundle,
        "icons": sorted(
            ({"id": name, "cp": point} for name, point in zip(names, points)),
            key=lambda icon: icon["id"],
        ),
    }
    if args:
        print("\n".join(icon["id"] for icon in catalog["icons"]))
        return
    serve(catalog, font_dir)


if __name__ == "__main__":
    main()
