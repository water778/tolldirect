"""Vercel Python entry. Read-only simulation dashboard."""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "backend"))
from tolldirect.readonly import handle


class handler:
    def __init__(self, request, response):
        self.request = request
        self.response = response

    def __call__(self):
        method = self.request.method
        path = self.request.path.split("?", 1)[0]
        auth = self.request.headers.get("authorization", "")
        status, content_type, body = handle(method, path, auth)
        self.response.status_code = status
        if status == 401:
            self.response.headers["WWW-Authenticate"] = 'Basic realm="TollDirect simulation"'
        self.response.headers["Content-Type"] = content_type
        self.response.headers["Cache-Control"] = "no-store"
        return body
