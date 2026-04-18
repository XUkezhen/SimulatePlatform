import os
import signal
import subprocess
import sys

from django.utils.autoreload import run_with_reloader


def run_daphne():
    host = os.getenv("BACKEND_HOST", "127.0.0.1")
    port = os.getenv("BACKEND_PORT", "8002")
    command = [
        sys.executable,
        "-m",
        "daphne",
        "-b",
        host,
        "-p",
        port,
        "mytest.asgi:application",
    ]

    process = subprocess.Popen(command)
    try:
        process.wait()
    except KeyboardInterrupt:
        pass
    finally:
        if process.poll() is None:
            process.send_signal(signal.SIGTERM)
            process.wait()


if __name__ == "__main__":
    os.environ.setdefault("DJANGO_SETTINGS_MODULE", "mytest.settings")
    run_with_reloader(run_daphne)
