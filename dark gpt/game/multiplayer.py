"""Multiplayer Security Research: analisi dell'architettura client-server.

Il modulo aiuta gli sviluppatori dei **propri** giochi a individuare i
problemi di fiducia eccessiva nel client. Non fornisce strumenti per
compromettere altri giocatori ne' per aggirare protezioni: il punto di
partenza e' un manifest dichiarato dall'autore del gioco, non l'analisi di
un servizio di terzi.

Ogni finding indica: la condizione, l'impatto e la correzione lato server.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass
class ActionSpec:
    """Una azione di gioco dichiarata e la sua validazione lato server."""

    name: str
    client_sent_fields: list[str] = field(default_factory=list)
    server_validated: bool = False
    authoritative_fields: list[str] = field(default_factory=list)
    notes: str = ""


@dataclass
class ArchitectureManifest:
    """Descrizione dell'architettura client-server di un gioco."""

    game: str
    transport: str = "TCP"
    encrypted: bool = True
    server_authoritative: bool = True
    actions: list[ActionSpec] = field(default_factory=list)
    notes: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        """Serializza il manifest."""
        return {
            "game": self.game,
            "transport": self.transport,
            "encrypted": self.encrypted,
            "server_authoritative": self.server_authoritative,
            "actions": [
                {
                    "name": action.name,
                    "client_sent_fields": action.client_sent_fields,
                    "server_validated": action.server_validated,
                    "authoritative_fields": action.authoritative_fields,
                    "notes": action.notes,
                }
                for action in self.actions
            ],
            "notes": self.notes,
        }


@dataclass
class ArchitectureFinding:
    """Un problema di sicurezza individuato nell'architettura dichiarata."""

    category: str
    severity: str
    title: str
    detail: str
    remediation: str
    evidence: str = ""

    def to_dict(self) -> dict[str, Any]:
        """Serializza il finding."""
        return {
            "category": self.category,
            "severity": self.severity,
            "title": self.title,
            "detail": self.detail,
            "remediation": self.remediation,
            "evidence": self.evidence,
        }


def analyze_architecture(manifest: ArchitectureManifest) -> list[ArchitectureFinding]:
    """Analizza il manifest e restituisce i problemi individuati.

    Le verifiche riguardano la relazione tra i dati inviati dal client e
    quelli che il server ricalcola: e' la classe di difetti che rende
    sfruttabile un gioco online.
    """
    findings: list[ArchitectureFinding] = []

    if not manifest.encrypted:
        findings.append(
            ArchitectureFinding(
                category="Transport Security",
                severity="HIGH",
                title="Trasporto non cifrato",
                detail=(
                    "Il manifest dichiara un trasporto non cifrato: i messaggi "
                    "viaggiano in chiaro e sono modificabili in transito."
                ),
                remediation=(
                    "Usa TLS per il canale di gioco e autentica il canale "
                    "oltre la sola cifratura del traffico."
                ),
                evidence=f"transport={manifest.transport}, encrypted=false",
            )
        )

    if not manifest.server_authoritative:
        findings.append(
            ArchitectureFinding(
                category="Trust Boundary",
                severity="HIGH",
                title="Il client non e' authoritative",
                detail=(
                    "Il manifest dichiara un modello non server-authoritative: "
                    "il client decide lo stato di gioco e il server lo accetta."
                ),
                remediation=(
                    "Sposta la decisione sul server: il client invia "
                    "intenzioni, il server calcola e valida."
                ),
                evidence="server_authoritative=false",
            )
        )

    for action in manifest.actions:
        if not action.server_validated and action.client_sent_fields:
            findings.append(
                ArchitectureFinding(
                    category="Input Validation",
                    severity="HIGH",
                    title=f"Azione '{action.name}' non validata lato server",
                    detail=(
                        "L'azione riceve campi dal client ma il server non li "
                        "valida: un client modificato puo' inviare valori "
                        "arbitrari."
                    ),
                    remediation=(
                        f"Validare lato server i campi {action.client_sent_fields} "
                        "contro lo stato autorevole, ricalcolando il risultato."
                    ),
                    evidence=(
                        f"azione={action.name}, campi dal client: "
                        f"{', '.join(action.client_sent_fields)}"
                    ),
                )
            )
        elif action.server_validated and not action.authoritative_fields:
            findings.append(
                ArchitectureFinding(
                    category="Trust Boundary",
                    severity="MEDIUM",
                    title=f"Azione '{action.name}' validata senza campi autorevoli",
                    detail=(
                        "L'azione e' dichiarata come validata ma non indica "
                        "quali campi il server ricalcola: la validazione puo' "
                        "essere solo un controllo di intervallo."
                    ),
                    remediation=(
                        "Elencare i campi ricalcolati dal server e rifiutare "
                        "ogni valore non derivabile dallo stato autorevole."
                    ),
                    evidence=f"azione={action.name}",
                )
            )
        conflicting = sorted(set(action.client_sent_fields) & set(action.authoritative_fields))
        if conflicting:
            findings.append(
                ArchitectureFinding(
                    category="Trust Boundary",
                    severity="CRITICAL",
                    title=f"Azione '{action.name}': campo contemporaneamente autorevole e inviato dal client",
                    detail=(
                        f"Il campo {conflicting} e' dichiarato sia autorevole "
                        "lato server sia inviato dal client: due sorgenti di "
                        "verita' in conflitto."
                    ),
                    remediation=(
                        "Rimuovere il campo autorevole dalla lista dei campi "
                        "inviati dal client, oppure ignorare il valore client."
                    ),
                    evidence=f"azione={action.name}, campi: {conflicting}",
                )
            )

    return findings


@dataclass
class MovementAction:
    """Azione di movimento inviata dal client."""

    x: float
    y: float
    z: float
    dt_ms: int
    sprint: bool = False


@dataclass
class ValidationResult:
    """Esito della validazione lato server di un'azione."""

    accepted: bool
    reason: str
    corrected: MovementAction | None = None


def validate_movement(
    action: MovementAction,
    *,
    max_speed: float = 6.0,
    max_delta_ms: int = 100,
) -> ValidationResult:
    """Valida un'azione di movimento lato server.

    Dimostra la regola base: il server non accetta mai la posizione
    dichiarata dal client, ma verifica che sia derivabile dallo stato
    autorevole e dal tempo trascorso.
    """
    if action.dt_ms <= 0 or action.dt_ms > max_delta_ms:
        return ValidationResult(
            accepted=False,
            reason=f"delta temporale non plausibile: {action.dt_ms} ms",
        )

    seconds = action.dt_ms / 1000.0
    speed_limit = max_speed * (1.5 if action.sprint else 1.0)
    distance = (action.x**2 + action.y**2 + action.z**2) ** 0.5
    max_distance = speed_limit * seconds
    if distance > max_distance:
        return ValidationResult(
            accepted=False,
            reason=(
                f"spostamento non plausibile: {distance:.2f} m in {action.dt_ms} ms "
                f"(massimo {max_distance:.2f} m)"
            ),
        )

    return ValidationResult(
        accepted=True,
        reason="azione coerente con il modello di movimento",
        corrected=MovementAction(
            x=action.x,
            y=action.y,
            z=action.z,
            dt_ms=action.dt_ms,
            sprint=action.sprint,
        ),
    )
