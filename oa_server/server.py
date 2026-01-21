from __future__ import annotations

import argparse
from pathlib import Path

from . import db
from ._server.http_server import Handler, OAHTTPServer


def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(description="OA demo server (stdlib + sqlite)")
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=8000)
    parser.add_argument("--db", default=str(Path("data") / "oa.sqlite3"))
    parser.add_argument("--frontend", default=str(Path("frontend")))
    args = parser.parse_args(argv)

    db_path = Path(args.db)
    frontend_dir = Path(args.frontend)
    db.init_db(db_path)

    httpd = OAHTTPServer((args.host, args.port), Handler, db_path=db_path, frontend_dir=frontend_dir)
    print(f"OA server running on http://{args.host}:{args.port}/")
    httpd.serve_forever()