import sqlite3
import json
import uuid
import logging
from pathlib import Path
from typing import List, Dict, Optional

logger = logging.getLogger(__name__)

class EvidenceGraph:
    """
    Lite Structural Evidence Graph for EORA.
    Stores Entities, Sections, and Claims with their relationships.
    """
    def __init__(self, workspace_path: str):
        self.db_path = Path(workspace_path) / "evidence_graph.db"
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._init_db()

    def _init_db(self):
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            # Nodes Table
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS nodes (
                    id TEXT PRIMARY KEY,
                    type TEXT NOT NULL, -- Entity, Claim, Section, Document
                    label TEXT NOT NULL,
                    content TEXT,
                    metadata TEXT, -- JSON blob
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            """)
            # Edges Table
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS edges (
                    source_id TEXT,
                    target_id TEXT,
                    relation TEXT NOT NULL, -- Mentions, Supports, Contradicts, Part_Of
                    weight REAL DEFAULT 1.0,
                    FOREIGN KEY(source_id) REFERENCES nodes(id),
                    FOREIGN KEY(target_id) REFERENCES nodes(id)
                )
            """)
            conn.commit()

    def add_node(self, node_id: str, node_type: str, label: str, content: str = "", metadata: dict = None):
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            cursor.execute(
                "INSERT OR REPLACE INTO nodes (id, type, label, content, metadata) VALUES (?, ?, ?, ?, ?)",
                (node_id, node_type, label, content, json.dumps(metadata or {}))
            )
            conn.commit()

    def add_edge(self, source_id: str, target_id: str, relation: str, weight: float = 1.0):
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            cursor.execute(
                "INSERT INTO edges (source_id, target_id, relation, weight) VALUES (?, ?, ?, ?)",
                (source_id, target_id, relation, weight)
            )
            conn.commit()

    def find_contradictions(self) -> List[Dict]:
        """Finds pairs of nodes connected by a 'Contradicts' relation."""
        with sqlite3.connect(self.db_path) as conn:
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()
            cursor.execute("""
                SELECT n1.label as source, n2.label as target, n1.content as c1, n2.content as c2
                FROM edges e
                JOIN nodes n1 ON e.source_id = n1.id
                JOIN nodes n2 ON e.target_id = n2.id
                WHERE e.relation = 'Contradicts'
            """)
            return [dict(row) for row in cursor.fetchall()]

    def get_provenance_chain(self, claim_id: str) -> List[Dict]:
        """Back-traces a claim to its source document via sections."""
        chain = []
        current_id = claim_id
        with sqlite3.connect(self.db_path) as conn:
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()
            
            # Simple recursive upward traversal
            for _ in range(5): # Max depth
                cursor.execute("""
                    SELECT n.id, n.type, n.label, n.metadata
                    FROM edges e
                    JOIN nodes n ON e.target_id = n.id
                    WHERE e.source_id = ? AND e.relation = 'Part_Of'
                """, (current_id,))
                row = cursor.fetchone()
                if not row: break
                chain.append(dict(row))
                current_id = row['id']
                
        return chain
