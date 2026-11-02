"""Check the actual publication directory over a short-lived loopback HTTP server."""
from functools import partial
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
import json
from pathlib import Path
import threading
import urllib.error
import urllib.request


class Handler(SimpleHTTPRequestHandler):
    def log_message(self, *_):
        pass


def main():
    root = Path(__file__).resolve().parents[1] / "web"
    server = ThreadingHTTPServer(("127.0.0.1", 0), partial(Handler, directory=str(root)))
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    base = f"http://127.0.0.1:{server.server_port}"
    checked = []
    try:
        for name in ["index.html", "styles.css", "app.js", "model.mjs",
                     "data/scenarios.json", "data/geometry.json", "data/roads.json", "data/comparison.csv", "data/history.json"]:
            with urllib.request.urlopen(base + "/" + name, timeout=5) as response:
                body = response.read()
                assert response.status == 200
                assert body == (root / name).read_bytes(), name
                if name.endswith((".js", ".mjs")):
                    assert "javascript" in response.headers["Content-Type"]
                checked.append({"path": name, "bytes": len(body), "mime": response.headers["Content-Type"]})
        for name in ["/../pyproject.toml", "/.env"]:
            try:
                urllib.request.urlopen(base + name, timeout=5)
            except urllib.error.HTTPError as error:
                assert error.code == 404
            else:
                raise AssertionError("unexpected file exposure")
        print(json.dumps({"checked": checked, "scope": "HTTP assets only; does not prove browser rendering"}))
    finally:
        server.shutdown()
        server.server_close()
        thread.join(timeout=5)


if __name__ == "__main__":
    main()
