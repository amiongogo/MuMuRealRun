"""
Local Web Server for Interactive Route Generator & Map Editor.
Uses Python standard library http.server (zero third-party web framework dependencies).
Automatically opens in browser and interacts with project route files.
"""

import sys
import os
import json
import socket
import webbrowser
from http.server import HTTPServer, BaseHTTPRequestHandler
from urllib.parse import urlparse, parse_qs

# Ensure UTF-8 output
if sys.platform == "win32":
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass

PROJECT_DIR = os.path.dirname(os.path.abspath(__file__))
EDITOR_HTML = os.path.join(PROJECT_DIR, "core", "editor.html")


class RouteEditorHandler(BaseHTTPRequestHandler):
    """Handles HTTP requests from the Route Editor Web UI."""

    def log_message(self, format, *args):
        # Suppress noisy standard HTTP logs
        pass

    def do_GET(self):
        parsed = urlparse(self.path)
        if parsed.path in ["/", "/index.html"]:
            self._serve_editor()
        elif parsed.path == "/api/load_route":
            self._handle_load_route(parsed)
        else:
            self.send_error(404, "Not Found")

    def do_POST(self):
        parsed = urlparse(self.path)
        if parsed.path == "/api/save_route":
            self._handle_save_route()
        else:
            self.send_error(404, "Not Found")

    def _serve_editor(self):
        """Serve the editor HTML file."""
        if not os.path.isfile(EDITOR_HTML):
            self.send_error(500, "Editor HTML not found")
            return

        with open(EDITOR_HTML, "rb") as f:
            content = f.read()

        self.send_response(200)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.send_header("Content-Length", str(len(content)))
        self.end_headers()
        self.wfile.write(content)

    def _handle_load_route(self, parsed):
        """Load an existing route file and return coordinates."""
        params = parse_qs(parsed.query)
        filename = params.get("filename", ["ZJGroute.txt"])[0]
        filepath = os.path.join(PROJECT_DIR, os.path.basename(filename))

        if not os.path.isfile(filepath):
            self._send_json({"success": False, "error": f"File not found: {filename}"})
            return

        try:
            from core.route import Route
            route = Route.load_from_file(filepath)
            points = [{"lat": p.lat, "lng": p.lng} for p in route.points]
            self._send_json({"success": True, "filename": filename, "points": points})
        except Exception as e:
            self._send_json({"success": False, "error": str(e)})

    def _handle_save_route(self):
        """Save coordinates to route file."""
        try:
            content_len = int(self.headers.get("Content-Length", 0))
            body = self.rfile.read(content_len).decode("utf-8")
            data = json.loads(body)

            filename = os.path.basename(data.get("filename", "ZJGroute.txt").strip() or "ZJGroute.txt")
            content = data.get("content", "").strip()

            target_path = os.path.join(PROJECT_DIR, filename)
            with open(target_path, "w", encoding="utf-8") as f:
                f.write(content)

            print(f"[✔] 成功保存路线至: {target_path} (大小: {len(content)} 字符)")
            self._send_json({"success": True, "filepath": filename})
        except Exception as e:
            self._send_json({"success": False, "error": str(e)})

    def _send_json(self, data: dict):
        body = json.dumps(data).encode("utf-8")
        self.send_response(200)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)


def find_free_port(start_port: int = 8765) -> int:
    """Find an available TCP port."""
    for port in range(start_port, start_port + 50):
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
            if s.connect_ex(("127.0.0.1", port)) != 0:
                return port
    return start_port


def start_editor(port: int = 8765, open_browser: bool = True):
    """Start local web server and launch browser."""
    free_port = find_free_port(port)
    server = HTTPServer(("127.0.0.1", free_port), RouteEditorHandler)
    url = f"http://127.0.0.1:{free_port}"

    print("=" * 60)
    print("🗺️  MuMuRealRun 路线可视化生成器已启动！")
    print(f"👉 浏览器访问地址: {url}")
    print("💡 可以在高德卫星图上点击 3 个跑道约束点自动拟合 400m 标准跑道")
    print("   绘制完成后点击【直接保存至项目文件】，即可供模拟器使用。")
    print("   按 Ctrl+C 可停止网页服务。")
    print("=" * 60)

    if open_browser:
        webbrowser.open(url)

    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\n[*] 网页服务已关闭。")
    finally:
        server.server_close()


if __name__ == "__main__":
    start_editor()
