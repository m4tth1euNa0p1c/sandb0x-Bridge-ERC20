"""Passerelle de consultation à cible fixe, sans CONNECT ni journal de payload."""
import argparse
import http.client
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("target", choices=("chain-a", "chain-b", "docs"))
    args = parser.parse_args()
    target_port = 8000 if args.target == "docs" else 8545

    class Handler(BaseHTTPRequestHandler):
        def log_message(self, *_args):
            pass

        def forward(self):
            if not self.path.startswith("/") or self.path.startswith("//") or len(self.path) > 2048:
                self.send_error(400)
                return
            if self.headers.get("Transfer-Encoding"):
                self.send_error(400)
                return
            try:
                length = int(self.headers.get("Content-Length", "0"))
            except ValueError:
                self.send_error(400)
                return
            if not 0 <= length <= 2 * 1024 * 1024:
                self.send_error(413)
                return
            if self.command == "POST" and not self.headers.get("Content-Type", "").startswith("application/json"):
                self.send_error(415)
                return
            self.connection.settimeout(5)
            connection = http.client.HTTPConnection(args.target, target_port, timeout=5)
            try:
                body = self.rfile.read(length) if length else None
                connection.request(self.command, self.path, body=body,
                                   headers={"Content-Type": self.headers.get("Content-Type", "application/json")})
                response = connection.getresponse()
                data = response.read(8 * 1024 * 1024 + 1)
                if len(data) > 8 * 1024 * 1024:
                    self.send_error(502)
                    return
                self.send_response(response.status)
                for key in ("Content-Type", "Location"):
                    value = response.getheader(key)
                    if value:
                        self.send_header(key, value)
                self.send_header("Content-Length", str(len(data)))
                self.send_header("X-Content-Type-Options", "nosniff")
                self.end_headers()
                if self.command != "HEAD":
                    self.wfile.write(data)
            except (OSError, http.client.HTTPException):
                self.send_error(502, "Upstream unavailable")
            finally:
                connection.close()

        do_GET = forward
        do_HEAD = forward
        do_POST = forward

    ThreadingHTTPServer(("0.0.0.0", 8080), Handler).serve_forever()


if __name__ == "__main__":
    main()
