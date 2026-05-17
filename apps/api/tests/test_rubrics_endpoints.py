"""Integration tests for ``POST /api/v2/rubrics/check`` and
``GET /api/v2/rubrics`` (Task 2.15).

Validates Requirements:

* **R2.6** — the loader keeps prior versions readable; ``GET /rubrics``
  surfaces each loaded rubric with its ``domain``, ``version``,
  ``author``, ``source``, ``cited_evidence_ids`` and dimensions.
* **R11.5** — ``POST /rubrics/check`` is a dry-run path
  (``metadata.mode == "dry-run"``); ``GET /rubrics`` is read-only
  (``metadata.mode == "read-only"``); neither path mutates persistent
  state on disk or in the loader cache.
"""

from __future__ import annotations

import textwrap

from fastapi.testclient import TestClient

from apps.api.app import expert_rubric


# A minimal but schema-valid rubric body. Mirrors the on-disk
# ``apps/api/expert_rubrics/default.yaml`` structure but keeps the
# domain unique so the dry-run does not accidentally collide with a
# shipped rubric in the loader cache.
_VALID_YAML = textwrap.dedent(
    """
    domain: dryrun_test_domain
    version: "0.1.0"
    author: Test Author
    source: tests/test_rubrics_endpoints.py
    cited_evidence_ids: []
    dimensions:
      - id: framing
        weight: 0.5
        anchors:
          - "scope"
          - "假设"
      - id: review
        weight: 0.5
        anchors:
          - "复盘"
          - "next-step"
    examples:
      - "A good answer states scope and a review trigger."
    """
).strip()


# Missing the ``author`` and ``source`` fields → must fail validation
# per R2.1 / R2.5.
_MALFORMED_YAML = textwrap.dedent(
    """
    domain: dryrun_test_domain
    version: "0.1.0"
    cited_evidence_ids: []
    dimensions:
      - id: framing
        weight: 1.0
        anchors:
          - "scope"
    """
).strip()


# Syntactically broken YAML — exercises the parser-error branch of the
# admin dry-run.
_BROKEN_YAML = "domain: [unterminated\n  - bad"


# ---------------------------------------------------------------------------
# POST /api/v2/rubrics/check — dry-run metadata + valid/invalid branches
# ---------------------------------------------------------------------------


def test_rubrics_check_returns_dry_run_metadata(client: TestClient) -> None:
    """The admin dry-run endpoint validates a YAML body without persisting.

    Steps:

    1. Submit a valid YAML body — assert ``200`` with
       ``metadata.mode == "dry-run"``, ``valid == True``, no errors,
       and a ``rubric`` preview echoing the parsed fields.
    2. Submit a YAML missing required fields — assert ``200`` with
       ``valid == False`` and a non-empty ``errors`` list. The
       ``rubric`` preview is ``None`` so a partial rubric cannot leak
       through.
    3. Submit broken YAML — assert ``valid == False`` with an error
       describing the parser failure.
    4. After all three calls, the loader cache must not contain the
       dry-run domain (R11.5: dry-run never mutates state).
    """

    expert_rubric.reset_cache_for_tests()
    expert_rubric.load_all(refresh=True)

    headers = {"X-Tenant-ID": "tnt-rubrics-dryrun", "X-User-ID": "admin"}

    # (1) Valid payload.
    ok = client.post(
        "/api/v2/rubrics/check",
        json={"domain": "dryrun_test_domain", "yaml_text": _VALID_YAML},
        headers=headers,
    )
    assert ok.status_code == 200, ok.text
    body = ok.json()

    assert body["metadata"]["adapter"] == "v2.rubrics.check"
    assert body["metadata"]["mode"] == "dry-run"  # R11.5
    assert body["metadata"]["read_only"] is False
    assert body["valid"] is True
    assert body["errors"] == []

    rubric_preview = body["rubric"]
    assert rubric_preview is not None
    assert rubric_preview["domain"] == "dryrun_test_domain"
    assert rubric_preview["version"] == "0.1.0"
    assert rubric_preview["author"] == "Test Author"
    assert rubric_preview["source"] == "tests/test_rubrics_endpoints.py"
    assert rubric_preview["cited_evidence_ids"] == []
    assert {dim["id"] for dim in rubric_preview["dimensions"]} == {"framing", "review"}
    # is_default is a UI convenience flag; for a non-default domain it
    # must be False.
    assert rubric_preview["is_default"] is False

    # (2) Malformed payload — missing author/source.
    bad = client.post(
        "/api/v2/rubrics/check",
        json={"domain": "dryrun_test_domain", "yaml_text": _MALFORMED_YAML},
        headers=headers,
    )
    assert bad.status_code == 200, bad.text
    bad_body = bad.json()

    assert bad_body["metadata"]["mode"] == "dry-run"
    assert bad_body["valid"] is False
    assert bad_body["rubric"] is None
    assert bad_body["errors"], "expected at least one error message"
    # The error message should reference one of the missing required
    # fields so admins know what to fix.
    joined_errors = " ".join(bad_body["errors"])
    assert ("author" in joined_errors) or ("source" in joined_errors)

    # (3) Broken YAML — parser error path.
    broken = client.post(
        "/api/v2/rubrics/check",
        json={"domain": "dryrun_test_domain", "yaml_text": _BROKEN_YAML},
        headers=headers,
    )
    assert broken.status_code == 200, broken.text
    broken_body = broken.json()
    assert broken_body["valid"] is False
    assert broken_body["rubric"] is None
    assert any(
        "yaml" in err.lower() or "parse" in err.lower()
        for err in broken_body["errors"]
    ), broken_body["errors"]

    # (4) The loader cache must not have learned the dry-run domain.
    # R11.5: ``mode="dry-run"`` is a hard contract — *no* persistent
    # state mutation.
    assert expert_rubric.get_rubric("dryrun_test_domain") is None
    assert "dryrun_test_domain" not in {r.domain for r in expert_rubric.list_loaded()}


# ---------------------------------------------------------------------------
# GET /api/v2/rubrics — read-only listing of loaded rubrics (R2.6)
# ---------------------------------------------------------------------------


def test_get_rubrics_lists_versions(client: TestClient) -> None:
    """The read-only listing surfaces every loaded rubric with the
    documented fields.

    Asserts:

    * ``metadata.mode == "read-only"`` (design.md endpoint × mode
      table).
    * The shipped ``default`` and ``general_decision`` rubrics are
      present (R2.7 fallback + at least one domain rubric).
    * Each item carries ``domain``, ``version``, ``author``,
      ``source``, ``cited_evidence_ids`` and a ``dimensions`` array
      (R2.1).
    * ``versions_by_domain`` groups versions per domain so a UI can
      render historical pickers without computing the grouping itself
      (R2.6).
    """

    expert_rubric.reset_cache_for_tests()
    expert_rubric.load_all(refresh=True)

    headers = {"X-Tenant-ID": "tnt-rubrics-list", "X-User-ID": "admin"}

    response = client.get("/api/v2/rubrics", headers=headers)
    assert response.status_code == 200, response.text
    body = response.json()

    assert body["metadata"]["adapter"] == "v2.rubrics.list"
    assert body["metadata"]["mode"] == "read-only"  # design Endpoint × mode
    assert body["metadata"]["read_only"] is True

    items = body["items"]
    assert isinstance(items, list)
    assert items, "expected at least one shipped rubric"

    by_domain = {item["domain"]: item for item in items}
    # R2.7 — default fallback always shipped.
    assert "default" in by_domain
    # We ship general_decision per Task 2.6.
    assert "general_decision" in by_domain

    # Validate the documented field set on a known item.
    default_item = by_domain["default"]
    for required_key in (
        "id",
        "domain",
        "version",
        "author",
        "source",
        "dimensions",
        "examples",
        "cited_evidence_ids",
        "is_default",
    ):
        assert required_key in default_item, f"missing {required_key} on default rubric"
    assert default_item["is_default"] is True
    assert default_item["domain"] == "default"
    assert isinstance(default_item["dimensions"], list)
    assert default_item["dimensions"], "default rubric should have at least one dimension"
    first_dim = default_item["dimensions"][0]
    assert {"id", "weight", "anchors"} <= set(first_dim.keys())

    # ``versions_by_domain`` mirrors the items grouping.
    versions_by_domain = body["versions_by_domain"]
    assert default_item["version"] in versions_by_domain["default"]
    assert by_domain["general_decision"]["version"] in versions_by_domain[
        "general_decision"
    ]

    # ``refused`` is a list (may be empty under green CI but the key
    # must always exist so admins can troubleshoot dev mistakes).
    assert isinstance(body["refused"], list)
