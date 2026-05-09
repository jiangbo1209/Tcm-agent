-- Graph service layer schema for nodes and edges
-- Compatible with MySQL 8+

CREATE TABLE IF NOT EXISTS `nodes` (
  `id` VARCHAR(128) NOT NULL,
  `node_type` ENUM('paper', 'record') NOT NULL,
  `title` VARCHAR(512) NOT NULL,
  `metric_value` INT NULL,
  `top_k_value` DECIMAL(10, 4) NOT NULL DEFAULT 1.0000,
  `created_at` TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
  `updated_at` TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
  PRIMARY KEY (`id`),
  INDEX `idx_nodes_type` (`node_type`),
  INDEX `idx_nodes_metric` (`metric_value`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

CREATE TABLE IF NOT EXISTS `edges` (
  `id` CHAR(40) NOT NULL,
  `source_id` VARCHAR(128) NOT NULL,
  `target_id` VARCHAR(128) NOT NULL,
  `edge_type` ENUM('paper-paper', 'paper-record', 'record-record') NOT NULL,
  `similarity_score` DECIMAL(6, 4) NOT NULL,
  `raw_score` DECIMAL(12, 8) NULL,
  `created_at` TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
  `updated_at` TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
  PRIMARY KEY (`id`),
  CONSTRAINT `chk_edges_score_range` CHECK (`similarity_score` >= 0.0000 AND `similarity_score` <= 1.0000),
  CONSTRAINT `fk_edges_source` FOREIGN KEY (`source_id`) REFERENCES `nodes` (`id`) ON DELETE CASCADE ON UPDATE CASCADE,
  CONSTRAINT `fk_edges_target` FOREIGN KEY (`target_id`) REFERENCES `nodes` (`id`) ON DELETE CASCADE ON UPDATE CASCADE,
  UNIQUE KEY `uk_edges_type_pair` (`edge_type`, `source_id`, `target_id`),
  INDEX `idx_edges_source_score` (`source_id`, `similarity_score`),
  INDEX `idx_edges_target_score` (`target_id`, `similarity_score`),
  INDEX `idx_edges_seed_expand` (`source_id`, `target_id`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;
