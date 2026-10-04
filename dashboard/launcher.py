"""Start and supervise the gateway and evidence dashboard with one command."""

from __future__ import annotations

import argparse
import importlib.util
import os
from pathlib import Path
import signal
import socket
import subprocess
import sys
import time
import urllib.error
import urllib.request
import webbrowser


ROOT = Path(__file__).resolve().parent.parent


def configure(args: argparse.Namespace, file_env: dict, shell_env: dict) -> dict[str, str]:
    env = {**{key: value for key, value in file_env.items() if value is not None}, **shell_env}
    for key, override, default in (("APP_PORT", args.app_port, "8000"),
                                   ("DASHBOARD_PORT", args.dashboard_port, "8090")):
        try:
            port = int(override if override is not None else env.get(key, default))
        except (TypeError, ValueError) as exc:
            raise ValueError(f"{key} must be a port number") from exc
        if not 1 <= port <= 65535:
            raise ValueError(f"{key} must be between 1 and 65535")
        env[key] = str(port)
    if env["APP_PORT"] == env["DASHBOARD_PORT"]:
        raise ValueError("APP_PORT and DASHBOARD_PORT must be different")
    if args.no_brokers:
        env["INGESTION_WORKERS_ENABLED"] = "false"
    if args.app_port is not None or not env.get("OAH_LIVE_BASE_URL"):
        env["OAH_LIVE_BASE_URL"] = f"http://127.0.0.1:{env['APP_PORT']}"
    sources = [ROOT / folder / "src" for folder in
               ("oah-ingestion", "oah-agent", "oah-pydantic-models", "oah-demo-publishers")]
    env["PYTHONPATH"] = os.pathsep.join([str(ROOT), *(str(path) for path in sources),
                                        *([env["PYTHONPATH"]] if env.get("PYTHONPATH") else [])])
    env["PYTHONUNBUFFERED"] = "1"
    return env


def connect_host(host: str) -> str:
    return {"0.0.0.0": "127.0.0.1", "::": "::1"}.get(host, host)


def service_url(host: str, port: str) -> str:
    host = connect_host(host)
    return f"http://{'[' + host + ']' if ':' in host else host}:{port}"


def check_port(host: str, port: str) -> None:
    try:
        with socket.create_connection((connect_host(host), int(port)), timeout=0.5):
            pass
    except ConnectionRefusedError:
        return
    except socket.timeout as exc:
        raise RuntimeError(f"Could not check {host}:{port}; check host and port settings") from exc
    except OSError as exc:
        raise RuntimeError(f"Could not check {host}:{port}: {exc}") from exc
    raise RuntimeError(f"Port {port} is already in use. Stop that service or choose another port.")


def stop_services(children: list[tuple[str, subprocess.Popen]]) -> None:
    # Signal both first, so their graceful shutdowns can happen together.
    for _, process in reversed(children):
        if process.poll() is None:
            try:
                if os.name == "nt":
                    process.send_signal(signal.CTRL_BREAK_EVENT)
                else:
                    process.terminate()
            except OSError:
                if process.poll() is None:
                    process.terminate()
    deadline = time.monotonic() + 8
    for _, process in reversed(children):
        try:
            process.wait(timeout=max(0.1, deadline - time.monotonic()))
        except subprocess.TimeoutExpired:
            process.kill()
            process.wait()


def wait_ready(name: str, process: subprocess.Popen, url: str, timeout: float) -> None:
    deadline = time.monotonic() + timeout
    # Local readiness should not depend on a shell's HTTP proxy configuration.
    opener = urllib.request.build_opener(urllib.request.ProxyHandler({}))
    while time.monotonic() < deadline:
        if process.poll() is not None:
            raise RuntimeError(f"{name} exited during startup (code {process.returncode}). See its logs above.")
        try:
            with opener.open(url, timeout=0.5) as response:
                if response.status == 200:
                    return
        except (urllib.error.URLError, OSError):
            pass
        time.sleep(0.2)
    raise RuntimeError(f"{name} did not become ready within {timeout:g} seconds. See its logs above.")


def supervise(env: dict[str, str], timeout: float, open_browser: bool = False) -> int:
    children: list[tuple[str, subprocess.Popen]] = []
    gateway_url = service_url(env.get("APP_HOST", "0.0.0.0"), env["APP_PORT"])
    dashboard_url = service_url(env.get("DASHBOARD_HOST", "127.0.0.1"), env["DASHBOARD_PORT"])
    services = [("Gateway", "oah_ingestion.app", gateway_url + "/health"),
                ("Dashboard", "dashboard.server", dashboard_url + "/api/config")]
    previous_term = signal.getsignal(signal.SIGTERM)

    def interrupt(signum, frame):
        raise KeyboardInterrupt

    signal.signal(signal.SIGTERM, interrupt)
    try:
        for name, module, health in services:
            print(f"[OAH] Starting {name}…", flush=True)
            options = {"creationflags": subprocess.CREATE_NEW_PROCESS_GROUP} if os.name == "nt" else {"start_new_session": True}
            process = subprocess.Popen([sys.executable, "-m", module], cwd=ROOT, env=env, **options)
            children.append((name, process))
            wait_ready(name, process, health, timeout)
        print(f"\n[OAH] Dashboard: {dashboard_url}\n[OAH] Studio:    {dashboard_url}/studio"
              f"\n[OAH] Gateway:   {gateway_url}\n[OAH] Press Ctrl+C to stop both services.\n", flush=True)
        if env.get("DASHBOARD_HOST") in {"0.0.0.0", "::"}:
            print(f"[OAH] LAN access enabled: open http://<this-computer-LAN-IP>:{env['DASHBOARD_PORT']} on other devices.", flush=True)
        if open_browser:
            webbrowser.open(dashboard_url)
        while True:
            for name, process in children:
                code = process.poll()
                if code is not None:
                    print(f"[OAH] {name} stopped (code {code}); stopping the other service.", file=sys.stderr, flush=True)
                    return code or 1
            time.sleep(0.2)
    except KeyboardInterrupt:
        print("\n[OAH] Stopping services…", flush=True)
        return 0
    except (OSError, RuntimeError) as exc:
        print(f"[OAH] {exc}", file=sys.stderr, flush=True)
        return 1
    finally:
        previous_int = signal.signal(signal.SIGINT, signal.SIG_IGN)
        signal.signal(signal.SIGTERM, signal.SIG_IGN)
        try:
            stop_services(children)
        finally:
            signal.signal(signal.SIGINT, previous_int)
            signal.signal(signal.SIGTERM, previous_term)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--no-brokers", action="store_true", help="Disable MQTT/RabbitMQ consumers; HTTP ingestion and Studio remain available")
    parser.add_argument("--rabbitmq", action="store_true", help="Start the repository's RabbitMQ Docker Compose service before the app")
    parser.add_argument("--open", action="store_true", help="Open the dashboard in your browser after startup")
    parser.add_argument("--app-port", type=int, help="Override APP_PORT and point the dashboard at this local gateway")
    parser.add_argument("--dashboard-port", type=int, help="Override DASHBOARD_PORT")
    parser.add_argument("--startup-timeout", type=float, default=30, help="Seconds to wait for each service (default: 30)")
    args = parser.parse_args()
    if args.startup_timeout <= 0:
        parser.error("--startup-timeout must be positive")
    if args.rabbitmq and args.no_brokers:
        parser.error("Use either --rabbitmq or --no-brokers")
    missing = [name for name in ("dotenv", "uvicorn", "fastapi", "pydantic", "pika", "paho", "openai")
               if importlib.util.find_spec(name) is None]
    if missing:
        print("[OAH] Missing dependencies: " + ", ".join(missing), file=sys.stderr)
        print(f"Install once with:\n  {sys.executable} -m pip install -r requirements.txt\n"
              f"  {sys.executable} -m pip install -e .", file=sys.stderr)
        return 1
    from dotenv import dotenv_values

    try:
        env = configure(args, dotenv_values(ROOT / ".env"), dict(os.environ))
        check_port(env.get("APP_HOST", "0.0.0.0"), env["APP_PORT"])
        check_port(env.get("DASHBOARD_HOST", "127.0.0.1"), env["DASHBOARD_PORT"])
        if args.rabbitmq:
            if env.get("RABBITMQ_HOST", "localhost") not in {"localhost", "127.0.0.1", "::1"}:
                raise ValueError("--rabbitmq starts a local broker; set RABBITMQ_HOST=localhost or use your external broker without this flag")
            subprocess.run(["docker", "compose", "up", "-d", "rabbitmq"], cwd=ROOT, env=env, check=True)
            env["INGESTION_WORKERS_ENABLED"] = "true"
            print("[OAH] RabbitMQ stays running after app shutdown; use docker compose stop rabbitmq to stop it.", flush=True)
        if env.get("INGESTION_WORKERS_ENABLED", "true").strip().lower() not in {"false", "0", "no"}:
            print("[OAH] MQTT/RabbitMQ consumers enabled; configured brokers must be reachable. Use --no-brokers for HTTP-only operation.", flush=True)
    except (OSError, ValueError, RuntimeError, subprocess.CalledProcessError) as exc:
        print(f"[OAH] {exc}", file=sys.stderr)
        return 1
    return supervise(env, args.startup_timeout, args.open)


if __name__ == "__main__":
    raise SystemExit(main())
