import argparse
import subprocess
from unittest import mock

import pytest

from dashboard import launcher


def arguments(**overrides):
    return argparse.Namespace(app_port=None, dashboard_port=None, no_brokers=False, **overrides)


def test_env_precedence_and_missing_upstream_follow_gateway_port():
    env = launcher.configure(arguments(), {"APP_PORT": "8001", "DASHBOARD_PORT": "8090", "IGNORED": None}, {"APP_PORT": "8002"})
    assert env["APP_PORT"] == "8002"
    assert env["OAH_LIVE_BASE_URL"] == "http://127.0.0.1:8002"
    assert "IGNORED" not in env
    assert "oah-ingestion" in env["PYTHONPATH"]


def test_existing_upstream_is_preserved_until_explicit_port_override():
    existing = {"APP_PORT": "8001", "OAH_LIVE_BASE_URL": "http://remote-gateway:8001"}
    assert launcher.configure(arguments(), existing, {})["OAH_LIVE_BASE_URL"] == existing["OAH_LIVE_BASE_URL"]
    args = arguments()
    args.app_port = 18001
    args.no_brokers = True
    env = launcher.configure(args, existing, {})
    assert env["OAH_LIVE_BASE_URL"] == "http://127.0.0.1:18001"
    assert env["INGESTION_WORKERS_ENABLED"] == "false"


@pytest.mark.parametrize("settings", [{"APP_PORT": "bad"}, {"APP_PORT": "0"}, {"DASHBOARD_PORT": "70000"}, {"APP_PORT": "8090", "DASHBOARD_PORT": "8090"}])
def test_invalid_ports_fail_before_startup(settings):
    with pytest.raises(ValueError):
        launcher.configure(arguments(), settings, {})


def test_port_check_refuses_to_take_over_existing_service():
    with mock.patch.object(launcher.socket, "create_connection") as connect:
        with pytest.raises(RuntimeError, match="already in use"):
            launcher.check_port("0.0.0.0", "8001")
        connect.assert_called_once_with(("127.0.0.1", 8001), timeout=0.5)
    with mock.patch.object(launcher.socket, "create_connection", side_effect=ConnectionRefusedError):
        launcher.check_port("127.0.0.1", "8090")


def test_startup_failure_stops_service_already_started():
    first = mock.Mock()
    first.poll.return_value = None
    env = launcher.configure(arguments(), {}, {})
    with mock.patch.object(launcher.subprocess, "Popen", side_effect=[first, OSError("cannot start")]), mock.patch.object(launcher, "wait_ready"), mock.patch.object(launcher, "stop_services") as stop:
        assert launcher.supervise(env, 5) == 1
    stop.assert_called_once_with([("Gateway", first)])


def test_keyboard_interrupt_stops_both_services():
    first, second = mock.Mock(), mock.Mock()
    env = launcher.configure(arguments(), {}, {})
    with mock.patch.object(launcher.subprocess, "Popen", side_effect=[first, second]), mock.patch.object(launcher, "wait_ready", side_effect=[None, KeyboardInterrupt]), mock.patch.object(launcher, "stop_services") as stop:
        assert launcher.supervise(env, 5) == 0
    stop.assert_called_once_with([("Gateway", first), ("Dashboard", second)])


@pytest.mark.parametrize("host,expected", [("0.0.0.0", "127.0.0.1"), ("192.168.1.20", "192.168.1.20"), ("::", "[::1]")])
def test_dashboard_readiness_uses_configured_listen_address(host, expected):
    first, second = mock.Mock(), mock.Mock()
    env = launcher.configure(arguments(), {"DASHBOARD_HOST": host}, {})
    with mock.patch.object(launcher.subprocess, "Popen", side_effect=[first, second]), mock.patch.object(launcher, "wait_ready", side_effect=[None, KeyboardInterrupt]) as ready, mock.patch.object(launcher, "stop_services"):
        assert launcher.supervise(env, 5) == 0
    assert ready.call_args_list[1] == mock.call("Dashboard", second, f"http://{expected}:8090/api/config", 5)


@pytest.mark.parametrize("host", [None, "0.0.0.0", "192.168.1.20"])
def test_dashboard_entrypoint_honors_configured_host(host):
    from dashboard import server

    settings = {"DASHBOARD_PORT": "18090"}
    if host is not None:
        settings["DASHBOARD_HOST"] = host
    with mock.patch.object(server.os, "getenv", side_effect=lambda key, default=None: settings.get(key, default)), mock.patch("uvicorn.run") as run:
        server.main()
    run.assert_called_once_with("dashboard.server:app", host=host or "127.0.0.1", port=18090, reload=False)


def test_child_exit_stops_sibling_and_returns_failure():
    first, second = mock.Mock(), mock.Mock()
    first.poll.return_value = 7
    second.poll.return_value = None
    env = launcher.configure(arguments(), {}, {})
    with mock.patch.object(launcher.subprocess, "Popen", side_effect=[first, second]), mock.patch.object(launcher, "wait_ready"), mock.patch.object(launcher, "stop_services") as stop:
        assert launcher.supervise(env, 5) == 7
    stop.assert_called_once_with([("Gateway", first), ("Dashboard", second)])


def test_shutdown_signals_children_and_kills_only_a_stalled_child():
    first, second = mock.Mock(), mock.Mock()
    first.poll.return_value = second.poll.return_value = None
    first.wait.side_effect = [subprocess.TimeoutExpired("gateway", 8), 0]
    launcher.stop_services([("Gateway", first), ("Dashboard", second)])
    first.kill.assert_called_once()
    second.kill.assert_not_called()
    first.wait.assert_called()
    second.wait.assert_called()


def test_readiness_rejects_early_exit_and_timeout():
    process = mock.Mock()
    process.poll.return_value = 1
    process.returncode = 1
    with pytest.raises(RuntimeError, match="exited during startup"):
        launcher.wait_ready("Gateway", process, "http://127.0.0.1:8001/health", 5)
    process.poll.return_value = None
    with mock.patch.object(launcher.time, "monotonic", side_effect=[0, 6]):
        with pytest.raises(RuntimeError, match="did not become ready"):
            launcher.wait_ready("Gateway", process, "http://127.0.0.1:8001/health", 5)
