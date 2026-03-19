from __future__ import annotations

import json
from dataclasses import asdict, dataclass
from datetime import datetime
from pathlib import Path
from random import Random


@dataclass
class MpesaTransaction:
    checkout_request_id: str
    phone_number: str
    amount_kes: int
    purpose: str
    status: str
    message: str
    created_at: str


class MpesaSimulator:
    """Simulates M-Pesa STK push and persists transaction ledger."""

    def __init__(self, ledger_path: str = "data/mpesa_ledger.json", seed: int = 11) -> None:
        self.ledger_path = Path(ledger_path)
        self.rng = Random(seed)
        self.ledger_path.parent.mkdir(parents=True, exist_ok=True)
        if not self.ledger_path.exists():
            self.ledger_path.write_text("[]", encoding="utf-8")

    def simulate_stk_push(self, phone_number: str, amount_kes: int, purpose: str) -> MpesaTransaction:
        now = datetime.now().strftime("%Y%m%d%H%M%S")
        checksum = sum(int(c) for c in phone_number if c.isdigit()) + amount_kes
        outcome = checksum % 10

        if outcome <= 6:
            status = "SUCCESS"
            message = "STK Push accepted. Payment confirmed."
        elif outcome <= 8:
            status = "PENDING"
            message = "STK Push sent. Awaiting customer PIN confirmation."
        else:
            status = "FAILED"
            message = "Transaction failed due to network timeout. Retry recommended."

        tx = MpesaTransaction(
            checkout_request_id=f"SIM{now}{self.rng.randint(100, 999)}",
            phone_number=phone_number,
            amount_kes=int(amount_kes),
            purpose=purpose,
            status=status,
            message=message,
            created_at=datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        )
        self._append(tx)
        return tx

    def list_transactions(self) -> list[dict[str, str | int]]:
        return json.loads(self.ledger_path.read_text(encoding="utf-8"))

    def summary(self) -> dict[str, int]:
        txs = self.list_transactions()
        successful = [t for t in txs if t["status"] == "SUCCESS"]
        pending = [t for t in txs if t["status"] == "PENDING"]
        failed = [t for t in txs if t["status"] == "FAILED"]
        total_paid = sum(int(t["amount_kes"]) for t in successful)
        return {
            "tx_count": len(txs),
            "successful": len(successful),
            "pending": len(pending),
            "failed": len(failed),
            "total_paid_kes": total_paid,
        }

    def _append(self, tx: MpesaTransaction) -> None:
        txs = self.list_transactions()
        txs.append(asdict(tx))
        self.ledger_path.write_text(json.dumps(txs, indent=2), encoding="utf-8")
