# HyperSpace-AGI v5.9 - Control Plane Runtime Store
# SQLite store per routing decisions, metriche e audit trail
from __future__ import annotations
import sqlite3
import json
from pathlib import Path
from datetime import datetime
from shared.domain.models import ExecutionPlan


CREATE_TABLE = """
CREATE TABLE IF NOT EXISTS routing_decisions (
    request_id      TEXT PRIMARY KEY,
    workload_type   TEXT NOT NULL,
    routing_level   INTEGER NOT NULL,
    selected_model  TEXT,
    selected_node   TEXT,
    pull_decision   TEXT NOT NULL,
    final_score     REAL,
    fallback_used   INTEGER DEFAULT 0,
    decided_at      TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_rd_model ON routing_decisions(selected_model);
CREATE INDEX IF NOT EXISTS idx_rd_wtype ON routing_decisions(workload_type);

CREATE TABLE IF NOT EXISTS routing_metrics (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    workload_type   TEXT NOT NULL,
    routing_level   INTEGER NOT NULL,
    model_id        TEXT NOT NULL,
    latency_ms      REAL,
    success         INTEGER DEFAULT 1,
    recorded_at     TEXT NOT NULL
);
"""


class ControlPlaneRuntimeStore:
    """SQLite store per routing decisions e metriche."""

    def __init__(self, state_dir: str = '/control-plane/control-plane/runtime') -> None:
        path = Path(state_dir) / 'cp_runtime.db'
        path.parent.mkdir(parents=True, exist_ok=True)
        self.conn = sqlite3.connect(str(path), check_same_thread=False)
        self.conn.executescript(CREATE_TABLE)
        self.conn.commit()

    def record_decision(self, plan: ExecutionPlan, routing_level: int, fallback_used: bool = False) -> None:
        """Persiste una routing decision."""
        best_score = (
            max((c.final_score for c in plan.placement_candidates), default=None)
            if plan.placement_candidates else None
        )
        self.conn.execute(
            'INSERT OR REPLACE INTO routing_decisions VALUES (?,?,?,?,?,?,?,?,?)',
            (
                plan.request_id,
                plan.workload.workload_type.value,
                routing_level,
                plan.selected_model_id,
                plan.selected_node_id,
                plan.pull_decision.decision.value,
                best_score,
                int(fallback_used),
                datetime.utcnow().isoformat(),
            ),
        )
        self.conn.commit()

    def record_metric(
        self,
        workload_type: str,
        routing_level: int,
        model_id: str,
        latency_ms: float,
        success: bool = True,
    ) -> None:
        """Registra una metrica di esecuzione."""
        self.conn.execute(
            'INSERT INTO routing_metrics (workload_type,routing_level,model_id,latency_ms,success,recorded_at) VALUES (?,?,?,?,?,?)',
            (workload_type, routing_level, model_id, latency_ms, int(success), datetime.utcnow().isoformat()),
        )
        self.conn.commit()

    def stats(self) -> dict:
        """Statistiche aggregate sui routing."""
        total = self.conn.execute('SELECT COUNT(*) FROM routing_decisions').fetchone()[0]
        fallbacks = self.conn.execute('SELECT COUNT(*) FROM routing_decisions WHERE fallback_used=1').fetchone()[0]
        by_model = self.conn.execute(
            'SELECT selected_model, COUNT(*) FROM routing_decisions GROUP BY selected_model ORDER BY 2 DESC'
        ).fetchall()
        by_workload = self.conn.execute(
            'SELECT workload_type, COUNT(*) FROM routing_decisions GROUP BY workload_type ORDER BY 2 DESC'
        ).fetchall()
        return {
            'total_decisions': total,
            'fallback_count': fallbacks,
            'by_model': dict(by_model),
            'by_workload': dict(by_workload),
        }

    def recent_decisions(self, limit: int = 20) -> list[dict]:
        """Ultime N routing decisions."""
        rows = self.conn.execute(
            'SELECT request_id,workload_type,routing_level,selected_model,pull_decision,fallback_used,decided_at '
            'FROM routing_decisions ORDER BY rowid DESC LIMIT ?',
            (limit,),
        ).fetchall()
        return [
            {
                'request_id': r[0], 'workload_type': r[1], 'routing_level': r[2],
                'selected_model': r[3], 'pull_decision': r[4],
                'fallback_used': bool(r[5]), 'decided_at': r[6],
            }
            for r in rows
        ]
