-- Graph service layer schema for nodes and edges
-- Compatible with PostgreSQL 16+

CREATE TABLE IF NOT EXISTS nodes (
  id VARCHAR(128) PRIMARY KEY,
  node_type VARCHAR(32) NOT NULL,
  title VARCHAR(512) NOT NULL,
  metric_value INT NULL,
  top_k_value NUMERIC(10, 4) NOT NULL DEFAULT 1.0000,
  created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
  updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_nodes_type ON nodes (node_type);
CREATE INDEX IF NOT EXISTS idx_nodes_metric ON nodes (metric_value);

CREATE TABLE IF NOT EXISTS edges (
  id CHAR(40) PRIMARY KEY,
  source_id VARCHAR(128) NOT NULL REFERENCES nodes (id) ON DELETE CASCADE,
  target_id VARCHAR(128) NOT NULL REFERENCES nodes (id) ON DELETE CASCADE,
  edge_type VARCHAR(32) NOT NULL,
  similarity_score NUMERIC(6, 4) NOT NULL,
  raw_score NUMERIC(12, 8) NULL,
  created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
  updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
  CONSTRAINT chk_edges_score_range CHECK (similarity_score >= 0.0000 AND similarity_score <= 1.0000),
  CONSTRAINT chk_edges_type CHECK (edge_type IN ('paper-paper', 'record-record', 'ref'))
);

CREATE UNIQUE INDEX IF NOT EXISTS uk_edges_type_pair ON edges (edge_type, source_id, target_id);
CREATE INDEX IF NOT EXISTS idx_edges_source_score ON edges (source_id, similarity_score);
CREATE INDEX IF NOT EXISTS idx_edges_target_score ON edges (target_id, similarity_score);
CREATE INDEX IF NOT EXISTS idx_edges_seed_expand ON edges (source_id, target_id);
