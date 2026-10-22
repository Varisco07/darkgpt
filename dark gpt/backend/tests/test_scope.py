"""Test dello Scope Manager: parsing, matching e decisioni deny-by-default."""

from __future__ import annotations

import pytest

from app.core.errors import ScopeError
from app.models.enums import ProjectMode, ScopeRuleEffect, ScopeRuleKind
from app.services.scope import ScopeDecision, ScopeService, parse_policy_text

POLICY = """
# Policy di esempio
in scope: example.com
in scope: *.example.com
in scope: https://api.example.com/v1
out of scope: admin.example.com
do not perform denial of service
"""


def test_parse_policy_text_extracts_rules():
    rules = parse_policy_text(POLICY)
    kinds = [(rule["kind"], rule["effect"], rule["pattern"]) for rule in rules]

    assert (ScopeRuleKind.DOMAIN, ScopeRuleEffect.ALLOW, "example.com") in kinds
    assert (ScopeRuleKind.DOMAIN, ScopeRuleEffect.DENY, "admin.example.com") in kinds
    assert (ScopeRuleKind.URL_PREFIX, ScopeRuleEffect.ALLOW, "https://api.example.com/v1") in kinds
    assert any(rule["kind"] is ScopeRuleKind.TECHNIQUE_DENY for rule in rules)


def test_import_policy_derives_assets_from_rules(session, project):
    service = ScopeService(session)
    policy = service.import_policy(project.id, POLICY)

    assert policy.asset_count == 3
    assets = {asset.value for asset in service.get_assets(project.id)}
    assert assets == {"example.com", "*.example.com", "https://api.example.com/v1"}


def test_import_policy_replaces_previous_rules(session, project):
    service = ScopeService(session)
    service.import_policy(project.id, POLICY)
    service.import_policy(project.id, "in scope: solo.example.org")

    assert len(service.get_rules(project.id)) == 1
    assert service.get_policy(project.id).asset_count == 1


def test_evaluate_allows_domain_in_scope(session, project):
    service = ScopeService(session)
    service.import_policy(project.id, POLICY)

    result = service.evaluate(project, "example.com")
    assert result.decision is ScopeDecision.ALLOWED
    assert result.allowed is True


def test_evaluate_allows_wildcard_subdomain(session, project):
    service = ScopeService(session)
    service.import_policy(project.id, POLICY)

    assert service.evaluate(project, "api.example.com").allowed is True


def test_evaluate_denies_explicitly_excluded_host(session, project):
    service = ScopeService(session)
    service.import_policy(project.id, POLICY)

    result = service.evaluate(project, "admin.example.com")
    assert result.decision is ScopeDecision.DENIED
    assert result.allowed is False


def test_evaluate_is_out_of_scope_without_rules(session, project):
    service = ScopeService(session)
    result = service.evaluate(project, "example.com")

    assert result.decision is ScopeDecision.OUT_OF_SCOPE
    assert "deny-by-default" in result.reason


def test_evaluate_denies_prohibited_technique(session, project):
    service = ScopeService(session)
    service.import_policy(project.id, "in scope: example.com")

    result = service.evaluate(project, "example.com", technique="denial_of_service")
    assert result.decision is ScopeDecision.DENIED
    assert "denial_of_service" in result.prohibited


def test_evaluate_allows_technique_explicitly_permitted(session, project):
    service = ScopeService(session)
    service.import_policy(
        project.id, "in scope: example.com\nallowed techniques: denial of service"
    )

    result = service.evaluate(project, "example.com", technique="denial of service")
    assert result.decision is ScopeDecision.ALLOWED


def test_lab_mode_allows_loopback(session, project):
    project.mode = ProjectMode.LAB
    service = ScopeService(session)

    result = service.evaluate(project, "http://127.0.0.1:8000/search")
    assert result.decision is ScopeDecision.LAB_ALLOWED
    assert result.allowed is True


def test_passive_mode_does_not_allow_loopback(session, project):
    project.mode = ProjectMode.PASSIVE
    service = ScopeService(session)

    result = service.evaluate(project, "http://127.0.0.1:8000/search")
    assert result.decision is ScopeDecision.OUT_OF_SCOPE


def test_require_allowed_raises_for_out_of_scope(session, project):
    service = ScopeService(session)
    with pytest.raises(ScopeError):
        service.require_allowed(project, "not-in-scope.example.org")


def test_url_prefix_rule_matches_subpath(session, project):
    service = ScopeService(session)
    service.import_policy(project.id, "in scope: https://api.example.com/v1")

    assert service.evaluate(project, "https://api.example.com/v1/users").allowed is True
    assert service.evaluate(project, "https://api.example.com/v2/users").allowed is False
