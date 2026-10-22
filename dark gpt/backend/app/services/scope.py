"""Scope Manager: parsing delle policy, derivazione degli asset e decisioni.

Il servizio e' l'unico punto in cui si decide se un target puo' essere
toccato. La decisione e' deny-by-default: se non esiste una regola ALLOW
esplicita, il target e' fuori scope.
"""

from __future__ import annotations

import ipaddress
import re
from dataclasses import dataclass, field
from enum import Enum
from urllib.parse import urlparse

from sqlalchemy import select
from sqlalchemy.orm import Session

from ..core.errors import NotFoundError, ScopeError, ScopeRequiredError
from ..core.security import is_loopback_host, normalize_target, target_host
from ..models.enums import ProjectMode, ScopeRuleEffect, ScopeRuleKind
from ..models.project import Project
from ..models.scope import ScopeAsset, ScopePolicy, ScopeRule

#: Tecniche sempre negate se non esplicitamente consentite da una regola.
DEFAULT_PROHIBITED_TECHNIQUES = frozenset(
    {
        "dos",
        "denial_of_service",
        "destructive",
        "data_exfiltration",
        "brute_force",
        "password_spraying",
        "social_engineering",
        "physical_attack",
    }
)

#: Tecniche che, se usate, richiedono conferma esplicita dell'operatore.
CONFIRMATION_REQUIRED_TECHNIQUES = frozenset(
    {"active_scan", "fuzzing", "exploit", "payload_injection"}
)


class ScopeDecision(str, Enum):
    """Esito della valutazione di un target."""

    ALLOWED = "ALLOWED"
    OUT_OF_SCOPE = "OUT_OF_SCOPE"
    DENIED = "DENIED"
    LAB_ALLOWED = "LAB_ALLOWED"


@dataclass(frozen=True)
class ScopeResult:
    """Esito dettagliato della valutazione di un target."""

    decision: ScopeDecision
    reason: str
    matched_rule_id: int | None = None
    matched_pattern: str | None = None
    requires_confirmation: bool = False
    prohibited: list[str] = field(default_factory=list)

    @property
    def allowed(self) -> bool:
        return self.decision in (ScopeDecision.ALLOWED, ScopeDecision.LAB_ALLOWED)


# ---------------------------------------------------------------------------
# Parsing della policy testuale
# ---------------------------------------------------------------------------

# Riconosce righe tipiche di una policy bug bounty.
_DOMAIN_RE = re.compile(r"^\s*[-*]?\s*(?:in[- ]?scope|target|domain|host)\s*[:=]\s*(\S+)", re.I)
_URL_RE = re.compile(r"^\s*[-*]?\s*(?:in[- ]?scope|url|endpoint)\s*[:=]\s*(\S+)", re.I)
_OUT_RE = re.compile(r"^\s*[-*]?\s*(?:out[- ]of[- ]scope|exclude|excluded|not allowed)\s*[:=]\s*(\S+)", re.I)
_DENY_TECHNIQUE_RE = re.compile(r"^\s*[-*]?\s*(?:do not|don't|never|no)\s+(.+?)\s*$", re.I)
_ALLOW_TECHNIQUE_RE = re.compile(
    r"^\s*[-*]?\s*(?:allowed?|permitted?)\s+(?:techniques?|testing)?\s*[:=]?\s*(.+?)\s*$", re.I
)
_CIDR_RE = re.compile(r"^\d{1,3}(?:\.\d{1,3}){3}/\d{1,2}$")


def parse_policy_text(text: str) -> list[dict]:
    """Estrae regole dal testo libero di una policy.

    Riconosce forme comuni: ``in scope: example.com``, ``*.example.com``,
    ``https://api.example.com/v1``, ``out of scope: admin.example.com``,
    ``do not perform denial of service``.

    Restituisce una lista di dict ``{kind, effect, pattern, technique, notes}``.
    """
    rules: list[dict] = []
    for raw_line in (text or "").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#"):
            continue

        match = _OUT_RE.match(line)
        if match:
            rules.append(_rule_from_pattern(match.group(1), ScopeRuleEffect.DENY))
            continue

        match = _URL_RE.match(line)
        if match:
            rules.append(_rule_from_pattern(match.group(1), ScopeRuleEffect.ALLOW))
            continue

        match = _DOMAIN_RE.match(line)
        if match:
            rules.append(_rule_from_pattern(match.group(1), ScopeRuleEffect.ALLOW))
            continue

        match = _DENY_TECHNIQUE_RE.match(line)
        if match:
            technique = match.group(1).strip().lower()
            rules.append(
                {
                    "kind": ScopeRuleKind.TECHNIQUE_DENY,
                    "effect": ScopeRuleEffect.DENY,
                    "pattern": technique,
                    "technique": technique,
                    "notes": line,
                }
            )
            continue

        match = _ALLOW_TECHNIQUE_RE.match(line)
        if match:
            technique = match.group(1).strip().lower()
            rules.append(
                {
                    "kind": ScopeRuleKind.TECHNIQUE_ALLOW,
                    "effect": ScopeRuleEffect.ALLOW,
                    "pattern": technique,
                    "technique": technique,
                    "notes": line,
                }
            )
            continue

        # Riga "nuda" con un dominio: trattata come asset in scope.
        if re.fullmatch(r"[*a-z0-9.\-:/_]+", line, re.I) and "." in line:
            rules.append(_rule_from_pattern(line, ScopeRuleEffect.ALLOW))
    return rules


def _rule_from_pattern(pattern: str, effect: ScopeRuleEffect) -> dict:
    """Classifica un pattern testuale nel tipo di regola appropriato."""
    value = pattern.strip().rstrip(".,;")
    if "://" in value:
        return {
            "kind": ScopeRuleKind.URL_PREFIX,
            "effect": effect,
            "pattern": value,
            "technique": "",
            "notes": "",
        }
    if _CIDR_RE.match(value):
        return {
            "kind": ScopeRuleKind.CIDR,
            "effect": effect,
            "pattern": value,
            "technique": "",
            "notes": "",
        }
    if value.startswith(("/", "./", "../")) or ("\\" in value and ":" not in value):
        return {
            "kind": ScopeRuleKind.FILE_PATH,
            "effect": effect,
            "pattern": value,
            "technique": "",
            "notes": "",
        }
    if "/" in value and not value.startswith("*."):
        return {
            "kind": ScopeRuleKind.API_ENDPOINT,
            "effect": effect,
            "pattern": value,
            "technique": "",
            "notes": "",
        }
    return {
        "kind": ScopeRuleKind.DOMAIN,
        "effect": effect,
        "pattern": value.lower(),
        "technique": "",
        "notes": "",
    }


# ---------------------------------------------------------------------------
# Matching
# ---------------------------------------------------------------------------


def _domain_matches(pattern: str, host: str) -> bool:
    """True se il pattern di dominio copre l'host.

    Supporta il wildcard iniziale (``*.example.com``), che in questo contesto
    include anche il dominio apex, come nella maggior parte delle policy.
    """
    pattern = pattern.lower().strip().lstrip(".")
    host = host.lower()
    if not pattern or not host:
        return False
    if pattern.startswith("*."):
        suffix = pattern[1:]  # ".example.com"
        return host == pattern[2:] or host.endswith(suffix)
    return host == pattern


def _cidr_matches(pattern: str, host: str) -> bool:
    """True se l'host appartiene alla rete indicata."""
    try:
        network = ipaddress.ip_network(pattern, strict=False)
        address = ipaddress.ip_address(host)
    except ValueError:
        return False
    return address in network


def _url_prefix_matches(pattern: str, normalized_target: str) -> bool:
    """True se il target normalizzato inizia con il prefisso URL della regola."""
    pattern_norm = normalize_target(pattern)
    if not pattern_norm:
        return False
    if normalized_target == pattern_norm:
        return True
    return normalized_target.startswith(pattern_norm.rstrip("/") + "/")


def rule_matches(rule: ScopeRule, target: str) -> bool:
    """True se la regola copre il target normalizzato."""
    normalized = normalize_target(target)
    host = target_host(normalized)
    pattern = rule.pattern

    if rule.kind is ScopeRuleKind.DOMAIN:
        return _domain_matches(pattern, host)
    if rule.kind is ScopeRuleKind.CIDR:
        return _cidr_matches(pattern, host)
    if rule.kind is ScopeRuleKind.URL_PREFIX:
        return _url_prefix_matches(pattern, normalized)
    if rule.kind is ScopeRuleKind.API_ENDPOINT:
        return normalized == pattern or normalized.startswith(pattern.rstrip("/") + "/")
    if rule.kind is ScopeRuleKind.FILE_PATH:
        try:
            from pathlib import Path

            from ..core.security import is_path_within  # import locale evita ciclo

            return is_path_within(Path(pattern), Path(normalized))
        except (OSError, ValueError):
            return False
    if rule.kind is ScopeRuleKind.REPOSITORY:
        return normalized.startswith(pattern)
    return False


# ---------------------------------------------------------------------------
# Servizio
# ---------------------------------------------------------------------------


class ScopeService:
    """Operazioni sullo scope di un progetto."""

    def __init__(self, session: Session) -> None:
        self.session = session

    # -- lettura ---------------------------------------------------------
    def get_policy(self, project_id: int) -> ScopePolicy | None:
        return self.session.scalar(
            select(ScopePolicy).where(ScopePolicy.project_id == project_id)
        )

    def get_rules(self, project_id: int) -> list[ScopeRule]:
        policy = self.get_policy(project_id)
        if policy is None:
            return []
        return list(
            self.session.scalars(select(ScopeRule).where(ScopeRule.policy_id == policy.id))
        )

    def get_assets(self, project_id: int) -> list[ScopeAsset]:
        policy = self.get_policy(project_id)
        if policy is None:
            return []
        return list(
            self.session.scalars(select(ScopeAsset).where(ScopeAsset.policy_id == policy.id))
        )

    # -- scrittura --------------------------------------------------------
    def import_policy(self, project_id: int, text: str, notes: str = "") -> ScopePolicy:
        """Importa (o sostituisce) la policy di scope di un progetto.

        Le regole e gli asset sono ricalcolati da zero: gli asset sono sempre
        derivati dalle regole, mai inseriti a mano.
        """
        parsed = parse_policy_text(text)
        policy = self.get_policy(project_id)
        if policy is None:
            policy = ScopePolicy(project_id=project_id, raw_text=text, notes=notes)
            self.session.add(policy)
            self.session.flush()
        else:
            policy.raw_text = text
            policy.notes = notes
            self.session.flush()
            self.session.query(ScopeRule).filter(ScopeRule.policy_id == policy.id).delete()
            self.session.query(ScopeAsset).filter(ScopeAsset.policy_id == policy.id).delete()
            self.session.flush()

        prohibited: list[str] = []
        asset_count = 0
        for item in parsed:
            rule = ScopeRule(
                policy_id=policy.id,
                kind=item["kind"],
                effect=item["effect"],
                pattern=item["pattern"],
                technique=item["technique"],
                notes=item["notes"],
            )
            self.session.add(rule)
            self.session.flush()
            if item["kind"] is ScopeRuleKind.TECHNIQUE_DENY:
                prohibited.append(item["technique"])
            # Gli asset sono generati solo dalle regole ALLOW di tipo target.
            if item["effect"] is ScopeRuleEffect.ALLOW and item["kind"] not in (
                ScopeRuleKind.TECHNIQUE_ALLOW,
                ScopeRuleKind.TECHNIQUE_DENY,
            ):
                self.session.add(
                    ScopeAsset(
                        policy_id=policy.id,
                        kind=item["kind"],
                        value=item["pattern"],
                        allowed=True,
                        technique=item["technique"],
                        source_rule_id=rule.id,
                    )
                )
                asset_count += 1
        policy.asset_count = asset_count
        policy.prohibited_techniques = sorted(set(prohibited))
        self.session.flush()
        return policy

    def add_rule(
        self,
        project_id: int,
        kind: ScopeRuleKind,
        effect: ScopeRuleEffect,
        pattern: str,
        technique: str = "",
        notes: str = "",
    ) -> ScopeRule:
        """Aggiunge una regola puntuale alla policy (creandola se assente)."""
        policy = self.get_policy(project_id)
        if policy is None:
            policy = ScopePolicy(project_id=project_id, raw_text="", notes="regola manuale")
            self.session.add(policy)
            self.session.flush()
        rule = ScopeRule(
            policy_id=policy.id,
            kind=kind,
            effect=effect,
            pattern=pattern,
            technique=technique,
            notes=notes,
        )
        self.session.add(rule)
        self.session.flush()
        if effect is ScopeRuleEffect.ALLOW and kind not in (
            ScopeRuleKind.TECHNIQUE_ALLOW,
            ScopeRuleKind.TECHNIQUE_DENY,
        ):
            self.session.add(
                ScopeAsset(
                    policy_id=policy.id,
                    kind=kind,
                    value=pattern,
                    allowed=True,
                    technique=technique,
                    source_rule_id=rule.id,
                )
            )
            policy.asset_count = len(self.get_assets(project_id))
        self.session.flush()
        return rule

    # -- decisione --------------------------------------------------------
    def evaluate(
        self,
        project: Project,
        target: str,
        technique: str = "",
    ) -> ScopeResult:
        """Valuta se il target puo' essere coinvolto e con quale esito.

        Pipeline deny-by-default:
        1. tecnica proibita (regola esplicita o default) -> DENIED
        2. regola DENY applicabile al target           -> DENIED
        3. regola ALLOW applicabile al target          -> ALLOWED
        4. progetto in LAB e target loopback            -> LAB_ALLOWED
        5. altrimenti                                   -> OUT_OF_SCOPE
        """
        normalized = normalize_target(target)
        host = target_host(normalized)
        rules = self.get_rules(project.id)
        tech = (technique or "").strip().lower()

        # 1. Tecniche vietate.
        allowed_techniques = {
            r.technique.lower() for r in rules if r.kind is ScopeRuleKind.TECHNIQUE_ALLOW
        }
        denied_techniques = {
            r.technique.lower() for r in rules if r.kind is ScopeRuleKind.TECHNIQUE_DENY
        }
        prohibited: list[str] = []
        if tech:
            if tech in denied_techniques:
                return ScopeResult(
                    decision=ScopeDecision.DENIED,
                    reason=f"tecnica '{tech}' vietata esplicitamente dalla policy",
                    prohibited=[tech],
                )
            if tech in DEFAULT_PROHIBITED_TECHNIQUES and tech not in allowed_techniques:
                prohibited.append(tech)
                return ScopeResult(
                    decision=ScopeDecision.DENIED,
                    reason=(
                        f"tecnica '{tech}' pericolosa non consentita dalla policy "
                        f"(consentite: {sorted(allowed_techniques) or 'nessuna'})"
                    ),
                    prohibited=prohibited,
                )

        # 2. Regole DENY applicabili al target.
        for rule in rules:
            if rule.effect is not ScopeRuleEffect.DENY:
                continue
            if rule.kind in (ScopeRuleKind.TECHNIQUE_ALLOW, ScopeRuleKind.TECHNIQUE_DENY):
                continue
            if rule_matches(rule, normalized):
                return ScopeResult(
                    decision=ScopeDecision.DENIED,
                    reason=f"target escluso da una regola DENY (pattern: {rule.pattern})",
                    matched_rule_id=rule.id,
                    matched_pattern=rule.pattern,
                    prohibited=prohibited,
                )

        # 3. Regole ALLOW applicabili al target.
        for rule in rules:
            if rule.effect is not ScopeRuleEffect.ALLOW:
                continue
            if rule.kind in (ScopeRuleKind.TECHNIQUE_ALLOW, ScopeRuleKind.TECHNIQUE_DENY):
                continue
            if rule_matches(rule, normalized):
                requires_confirmation = tech in CONFIRMATION_REQUIRED_TECHNIQUES
                return ScopeResult(
                    decision=ScopeDecision.ALLOWED,
                    reason=f"target coperto da una regola ALLOW (pattern: {rule.pattern})",
                    matched_rule_id=rule.id,
                    matched_pattern=rule.pattern,
                    requires_confirmation=requires_confirmation,
                    prohibited=prohibited,
                )

        # 4. Modalita' LAB: loopback sempre ammesso.
        if project.mode is ProjectMode.LAB and (is_loopback_host(host) or host == ""):
            return ScopeResult(
                decision=ScopeDecision.LAB_ALLOWED,
                reason="modalita' LAB: target locale ammesso",
                requires_confirmation=tech in CONFIRMATION_REQUIRED_TECHNIQUES,
                prohibited=prohibited,
            )

        # 5. Fuori scope.
        if not rules:
            return ScopeResult(
                decision=ScopeDecision.OUT_OF_SCOPE,
                reason="il progetto non ha regole di scope: deny-by-default",
                prohibited=prohibited,
            )
        return ScopeResult(
            decision=ScopeDecision.OUT_OF_SCOPE,
            reason="nessuna regola ALLOW copre il target richiesto",
            prohibited=prohibited,
        )

    def require_allowed(
        self,
        project: Project,
        target: str,
        technique: str = "",
    ) -> ScopeResult:
        """Come :meth:`evaluate`, ma solleva un errore se il target non e' ammesso."""
        result = self.evaluate(project, target, technique)
        if not result.allowed:
            raise ScopeError(
                f"operazione fuori scope: {result.reason}",
                details={
                    "target": target,
                    "decision": result.decision.value,
                    "rule_id": result.matched_rule_id,
                },
            )
        return result

    def require_scope_for_mode(self, project: Project) -> None:
        """Verifica che il progetto possa operare in AUTHORIZED_ASSESSMENT."""
        if project.mode is not ProjectMode.AUTHORIZED_ASSESSMENT:
            return
        assets = self.get_assets(project.id)
        if not assets:
            raise ScopeRequiredError(
                "modalita' AUTHORIZED_ASSESSMENT richiede almeno una regola ALLOW in scope",
                details={"project_id": project.id},
            )
