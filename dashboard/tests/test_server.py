import json

import pytest
from fastapi import HTTPException

from dashboard.server import (
    FIXTURE,
    download_report,
    get_evidence,
    get_config,
    get_graph,
    get_site,
    get_summary,
    index,
    list_reports,
    resolve_default_theme,
    retry_run,
    start_run,
)


def test_fixture_references_resolve():
    observation_ids = {item["id"] for item in FIXTURE["observations"]}
    finding_ids = {item["id"] for item in FIXTURE["findings"]}
    evidence_ids = {item["id"] for item in FIXTURE["evidence"]}
    site_ids = {item["id"] for item in FIXTURE["sites"]}
    node_ids = {item["id"] for item in FIXTURE["graph"]["nodes"]}

    assert all(item["siteId"] in site_ids for item in FIXTURE["observations"])
    assert all(item["siteId"] in site_ids for item in FIXTURE["findings"])
    assert all(set(item.get("evidenceIds", [])) <= evidence_ids for item in FIXTURE["findings"])
    assert all(set(site["observationIds"]) <= observation_ids for site in FIXTURE["sites"])
    assert all(set(site["findingIds"]) <= finding_ids for site in FIXTURE["sites"])
    assert all(edge["source"] in node_ids and edge["target"] in node_ids for edge in FIXTURE["graph"]["edges"])


def test_theme_configuration_is_validated_and_applied_before_paint():
    config = get_config()
    assert config["defaultTheme"] in {theme["id"] for theme in config["themes"]}
    assert [theme["id"] for theme in config["themes"]] == ["aqua", "aqua-dark", "white", "dark"]
    assert resolve_default_theme("dark") == "dark"
    assert resolve_default_theme("not-a-theme") == "aqua"
    page = index().body.decode("utf-8")
    assert f'data-theme="{config["defaultTheme"]}"' in page
    assert "__DEFAULT_THEME__" not in page


def test_viewer_scope_and_evidence_permission_are_enforced():
    summary = get_summary("viewer")
    assert [site["id"] for site in summary["sites"]] == ["site-c1-mondego"]

    with pytest.raises(HTTPException) as denied_site:
        get_site("site-coimbra-t1", "viewer")
    assert denied_site.value.status_code == 404

    with pytest.raises(HTTPException) as denied_evidence:
        get_evidence("evidence-nitrate-observation", "viewer")
    assert denied_evidence.value.status_code == 403


def test_operator_can_start_and_retry_runs_but_not_read_reports():
    started = start_run({"sampleKey": "iot"}, "operator")
    assert started["executionStatus"] == "running"
    assert len(started["stages"]) == 6

    retry = retry_run("run-003", "operator")
    assert retry["retryOf"] == "run-003"
    assert retry["attempt"] == 2

    with pytest.raises(HTTPException) as reports:
        list_reports("operator")
    assert reports.value.status_code == 403


def test_published_report_downloads_are_real_html_and_json_bytes():
    listing = list_reports("viewer")
    report = listing["reports"][0]
    assert report["visibility"] == "published"
    assert {item["format"] for item in report["files"]} == {"html", "json"}

    html_response = download_report("report-001", "html", "viewer")
    assert html_response.media_type == "text/html"
    assert b"Association only, not causation" in html_response.body
    expected_size = next(item["sizeBytes"] for item in report["files"] if item["format"] == "html")
    assert len(html_response.body) == expected_size

    json_response = download_report("report-001", "json", "viewer")
    assert json.loads(json_response.body)["site"]["id"] == "site-c1-mondego"


def test_graph_is_scoped_and_direct_unauthorized_requests_fail():
    graph = get_graph("site-c1-mondego", "analyst")
    node_ids = {node["id"] for node in graph["nodes"]}
    assert all(edge["source"] in node_ids and edge["target"] in node_ids for edge in graph["edges"])

    with pytest.raises(HTTPException) as viewer_graph:
        get_graph("site-c1-mondego", "viewer")
    assert viewer_graph.value.status_code == 403
