"""Reconciliation and lifecycle classification. Simulation is not confirmation."""

from dataclasses import dataclass, field
from enum import Enum
from typing import Dict, List, Optional

from ..models import Settlement, SettlementStatus


class LifecyclePhase(str, Enum):
    UNMATCHED = "unmatched"
    AWAITING_AMOUNT = "awaiting_official_amount"
    PENDING_CHARGE = "pending_charge"
    CHARGED_PENDING_CREDIT = "charged_pending_credit"
    CREDITED = "credited"
    RECONCILED = "reconciled"
    FAILED_UNRESOLVED = "failed_unresolved"
    REFUNDED = "refunded"
    DISPUTED = "disputed"
    INSUFFICIENT_FUNDS_RISK = "insufficient_funds_risk"
    DUPLICATE_BLOCKED = "duplicate_blocked"


@dataclass
class FundsAssessment:
    risk: str
    driver_funding_used: bool = False
    note: str = ""


@dataclass
class Dispute:
    dispute_id: str
    crossing_id: str
    reason: str
    status: str = "open"


@dataclass
class ReconciliationReport:
    charged_cents: int = 0
    credited_cents: int = 0
    refunded_cents: int = 0
    balanced: bool = False
    phases: Dict[str, List[str]] = field(default_factory=dict)
    unresolved: List[str] = field(default_factory=list)
    unmatched: List[str] = field(default_factory=list)
    disputed: List[str] = field(default_factory=list)
    insufficient_funds_risk: List[str] = field(default_factory=list)
    simulation_only: bool = True

    def to_dict(self) -> dict:
        return {
            "charged_cents": self.charged_cents,
            "credited_cents": self.credited_cents,
            "refunded_cents": self.refunded_cents,
            "balanced": self.balanced,
            "phases": self.phases,
            "unresolved": self.unresolved,
            "unmatched": self.unmatched,
            "disputed": self.disputed,
            "insufficient_funds_risk": self.insufficient_funds_risk,
            "simulation_only": self.simulation_only,
        }


class FundsAssessor:
    """Flags zero-balance risk without assuming a grace period or using driver funds."""

    def assess(self, balance_cents: int) -> FundsAssessment:
        if balance_cents <= 0:
            return FundsAssessment(
                risk="insufficient_at_travel",
                note=(
                    "Official EZDriveMA terms require funds on the account at the time of travel. "
                    "No grace period is assumed. The driver is not used as a funding source."
                ),
            )
        return FundsAssessment(risk="none", note="recorded balance was positive at assessment")


class Reconciler:
    """Classifies each settlement and checks that passenger charges equal E-ZPass credits."""

    def __init__(self) -> None:
        self.disputes: Dict[str, Dispute] = {}
        self.funds_risk: Dict[str, FundsAssessment] = {}

    def open_dispute(self, crossing_id: str, reason: str) -> Dispute:
        dispute = Dispute(f"DSP-{len(self.disputes)+1:04d}", crossing_id, reason)
        self.disputes[crossing_id] = dispute
        return dispute

    def mark_funds_risk(self, crossing_id: str, assessment: FundsAssessment) -> None:
        self.funds_risk[crossing_id] = assessment

    def classify(self, settlement: Settlement) -> LifecyclePhase:
        if settlement.crossing_id in self.disputes and self.disputes[settlement.crossing_id].status == "open":
            return LifecyclePhase.DISPUTED
        if settlement.status is SettlementStatus.REFUNDED:
            return LifecyclePhase.REFUNDED
        if settlement.status is SettlementStatus.DUPLICATE_BLOCKED:
            return LifecyclePhase.DUPLICATE_BLOCKED
        if settlement.status is SettlementStatus.FAILED_UNRESOLVED:
            if settlement.failure_reason and "no single active passenger trip" in settlement.failure_reason:
                return LifecyclePhase.UNMATCHED
            return LifecyclePhase.FAILED_UNRESOLVED
        if settlement.crossing_id in self.funds_risk and self.funds_risk[settlement.crossing_id].risk == "insufficient_at_travel":
            if settlement.status not in {SettlementStatus.RECONCILED, SettlementStatus.CREDITED_TO_EZPASS}:
                return LifecyclePhase.INSUFFICIENT_FUNDS_RISK
        if settlement.status is SettlementStatus.AWAITING_OFFICIAL_AMOUNT:
            return LifecyclePhase.AWAITING_AMOUNT
        if settlement.status is SettlementStatus.PASSENGER_CHARGE_PENDING:
            return LifecyclePhase.PENDING_CHARGE
        if settlement.status is SettlementStatus.PASSENGER_CHARGED and not settlement.ezpass_credit_id:
            return LifecyclePhase.CHARGED_PENDING_CREDIT
        if settlement.status is SettlementStatus.CREDITED_TO_EZPASS:
            return LifecyclePhase.CREDITED
        if settlement.status is SettlementStatus.RECONCILED and settlement.passenger_charge_id and settlement.ezpass_credit_id:
            return LifecyclePhase.RECONCILED
        if settlement.status is SettlementStatus.MATCHED:
            return LifecyclePhase.PENDING_CHARGE
        return LifecyclePhase.FAILED_UNRESOLVED

    def report(self, settlements: List[Settlement]) -> ReconciliationReport:
        report = ReconciliationReport()
        for settlement in settlements:
            phase = self.classify(settlement)
            report.phases.setdefault(phase.value, []).append(settlement.crossing_id)
            if phase is LifecyclePhase.UNMATCHED:
                report.unmatched.append(settlement.crossing_id)
            if phase in {LifecyclePhase.FAILED_UNRESOLVED, LifecyclePhase.CHARGED_PENDING_CREDIT}:
                report.unresolved.append(settlement.crossing_id)
            if phase is LifecyclePhase.DISPUTED:
                report.disputed.append(settlement.crossing_id)
            if phase is LifecyclePhase.INSUFFICIENT_FUNDS_RISK:
                report.insufficient_funds_risk.append(settlement.crossing_id)
            if settlement.passenger_charge_id and settlement.status is not SettlementStatus.REFUNDED:
                report.charged_cents += settlement.amount_cents or 0
            if settlement.ezpass_credit_id and settlement.status is not SettlementStatus.REFUNDED:
                report.credited_cents += settlement.amount_cents or 0
            if settlement.status is SettlementStatus.REFUNDED:
                report.refunded_cents += settlement.amount_cents or 0
        report.balanced = report.charged_cents == report.credited_cents
        return report
