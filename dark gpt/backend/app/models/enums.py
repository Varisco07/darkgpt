"""Enumerazioni di dominio condivise fra modelli, servizi e API."""

from __future__ import annotations

import enum


class ProjectMode(str, enum.Enum):
    """Modalita operative del progetto."""

    PASSIVE = "PASSIVE"
    LAB = "LAB"
    AUTHORIZED_ASSESSMENT = "AUTHORIZED_ASSESSMENT"


class FindingStatus(str, enum.Enum):
    """Stati del ciclo di vita di un finding."""

    INFO = "INFO"
    POTENTIAL = "POTENTIAL"
    NEEDS_VALIDATION = "NEEDS_VALIDATION"
    CONFIRMED = "CONFIRMED"
    FALSE_POSITIVE = "FALSE_POSITIVE"
    FIXED = "FIXED"


class FindingSeverity(str, enum.Enum):
    """Gravita tecnica del finding (indipendente dallo stato)."""

    INFO = "INFO"
    LOW = "LOW"
    MEDIUM = "MEDIUM"
    HIGH = "HIGH"
    CRITICAL = "CRITICAL"


class EvidenceKind(str, enum.Enum):
    """Natura di un'evidenza."""

    HTTP_REQUEST = "HTTP_REQUEST"
    HTTP_RESPONSE = "HTTP_RESPONSE"
    TOOL_OUTPUT = "TOOL_OUTPUT"
    CODE_SNIPPET = "CODE_SNIPPET"
    LOG_LINE = "LOG_LINE"
    SCREENSHOT_REF = "SCREENSHOT_REF"
    MANUAL_NOTE = "MANUAL_NOTE"


class ScopeRuleKind(str, enum.Enum):
    """Tipi di regola di scope."""

    DOMAIN = "DOMAIN"
    URL_PREFIX = "URL_PREFIX"
    CIDR = "CIDR"
    FILE_PATH = "FILE_PATH"
    REPOSITORY = "REPOSITORY"
    API_ENDPOINT = "API_ENDPOINT"
    TECHNIQUE_ALLOW = "TECHNIQUE_ALLOW"
    TECHNIQUE_DENY = "TECHNIQUE_DENY"


class ScopeRuleEffect(str, enum.Enum):
    """Effetto di una regola di scope."""

    ALLOW = "ALLOW"
    DENY = "DENY"


class ToolRunStatus(str, enum.Enum):
    """Esito di un'esecuzione di tool."""

    SUCCESS = "SUCCESS"
    FAILED = "FAILED"
    TIMEOUT = "TIMEOUT"
    UNAVAILABLE = "UNAVAILABLE"
    DENIED = "DENIED"
    INVALID_INPUT = "INVALID_INPUT"


class ReportFormat(str, enum.Enum):
    """Formati di report supportati."""

    MARKDOWN = "MARKDOWN"
    HTML = "HTML"
    JSON = "JSON"


#: Transizioni di stato ammesse per i finding. Chiave = stato di partenza.
ALLOWED_TRANSITIONS: dict[FindingStatus, frozenset[FindingStatus]] = {
    FindingStatus.INFO: frozenset(
        {FindingStatus.POTENTIAL, FindingStatus.FALSE_POSITIVE}
    ),
    FindingStatus.POTENTIAL: frozenset(
        {
            FindingStatus.CONFIRMED,
            FindingStatus.FALSE_POSITIVE,
            FindingStatus.NEEDS_VALIDATION,
        }
    ),
    FindingStatus.NEEDS_VALIDATION: frozenset(
        {
            FindingStatus.CONFIRMED,
            FindingStatus.FALSE_POSITIVE,
            FindingStatus.POTENTIAL,
        }
    ),
    FindingStatus.CONFIRMED: frozenset(
        {FindingStatus.FIXED, FindingStatus.FALSE_POSITIVE}
    ),
    FindingStatus.FALSE_POSITIVE: frozenset({FindingStatus.POTENTIAL}),
    FindingStatus.FIXED: frozenset({FindingStatus.CONFIRMED}),
}
