"""Hermes Agent Android server - started by HermesService via Chaquopy."""

import os
import sys
import threading
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("hermes_server")

_server_thread: threading.Thread | None = None
_should_stop = threading.Event()


def start_server() -> None:
    """Start the Hermes FastAPI server on localhost.

    Called from Kotlin via Chaquopy's Python.getInstance().getModule("hermes_server").callAttr("start_server")
    """
    from android_bootstrap import bootstrap

    home = bootstrap()
    logger.info(f"Hermes home: {home}")

    os.chdir(home)

    try:
        from hermes_cli.web_server import create_app
        import uvicorn

        app = create_app()
        logger.info("Starting Hermes server on 127.0.0.1:9119")

        config = uvicorn.Config(
            app,
            host="127.0.0.1",
            port=9119,
            log_level="info",
            access_log=False,
        )
        server = uvicorn.Server(config)

        # Run in current thread (blocking) - Kotlin calls this in a background thread
        server.run()

    except Exception as e:
        logger.error(f"Failed to start Hermes server: {e}")
        raise


def stop_server() -> None:
    """Signal the server to stop."""
    logger.info("Stop server requested")
    _should_stop.set()


def get_status() -> str:
    """Return server status for health check."""
    try:
        import urllib.request
        req = urllib.request.Request("http://127.0.0.1:9119/api/status")
        with urllib.request.urlopen(req, timeout=2) as resp:
            return resp.read().decode()
    except Exception:
        return '{"status": "starting"}'
