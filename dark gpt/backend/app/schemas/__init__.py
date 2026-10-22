"""Modelli Pydantic v2 per le richieste e le risposte API."""

from .common import ErrorResponse, HealthResponse, PaginatedResponse
from .chat import ChatHistoryResponse, ChatMessageRead, ChatRequest
from .finding import (
    EvidenceCreate,
    EvidenceRead,
    FindingCreate,
    FindingRead,
    FindingTransitionRequest,
    FindingUpdate,
    StateChangeRead,
)
from .project import (
    FileRecordRead,
    ProjectCreate,
    ProjectModeUpdate,
    ProjectRead,
    ProjectSummary,
    ProjectUpdate,
    ReportRead,
)
from .scope import (
    ScopeAssetRead,
    ScopeCheckRequest,
    ScopeCheckResponse,
    ScopePolicyImport,
    ScopePolicyRead,
    ScopeRuleCreate,
    ScopeRuleRead,
)
from .tool import (
    ScanRequest,
    ToolDescribe,
    ToolRunRead,
    ToolRunResult,
)

__all__ = [
    "ChatHistoryResponse",
    "ChatMessageRead",
    "ChatRequest",
    "ErrorResponse",
    "EvidenceCreate",
    "EvidenceRead",
    "FileRecordRead",
    "FindingCreate",
    "FindingRead",
    "FindingTransitionRequest",
    "FindingUpdate",
    "HealthResponse",
    "PaginatedResponse",
    "ProjectCreate",
    "ProjectModeUpdate",
    "ProjectRead",
    "ProjectSummary",
    "ProjectUpdate",
    "ReportRead",
    "ScanRequest",
    "ScopeAssetRead",
    "ScopeCheckRequest",
    "ScopeCheckResponse",
    "ScopePolicyImport",
    "ScopePolicyRead",
    "ScopeRuleCreate",
    "ScopeRuleRead",
    "StateChangeRead",
    "ToolDescribe",
    "ToolRunRead",
    "ToolRunResult",
]
