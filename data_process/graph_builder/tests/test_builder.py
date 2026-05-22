from __future__ import annotations

import unittest

from data_process.graph_builder.builder import (
    Node,
    build_pair_edges,
    normalize_title,
    split_sql_statements,
    stable_node_id,
    tokenize_text,
)


class BuilderTestCase(unittest.TestCase):
    def test_split_sql_statements_skips_comment_lines(self) -> None:
        sql = """
        -- Graph tables
        CREATE TABLE nodes (id text);

        -- Indexes
        CREATE INDEX idx_nodes_id ON nodes (id);
        """

        self.assertEqual(
            split_sql_statements(sql),
            [
                "CREATE TABLE nodes (id text)",
                "CREATE INDEX idx_nodes_id ON nodes (id)",
            ],
        )

    def test_normalize_title_removes_pdf_suffix_and_spaces(self) -> None:
        self.assertEqual(normalize_title("  肝肾 亏虚.PDF "), "肝肾亏虚")
        self.assertEqual(normalize_title("Formula （Case）"), "formula(case)")

    def test_tokenize_text_extracts_ascii_words_and_cjk_bigrams(self) -> None:
        tokens = tokenize_text("肝肾亏虚 Formula A1")

        self.assertTrue({"肝肾", "肾亏", "亏虚", "formula", "a1"}.issubset(tokens))

    def test_stable_node_id_uses_normalized_key(self) -> None:
        self.assertEqual(
            stable_node_id("paper", "  Example.PDF "),
            stable_node_id("paper", "example"),
        )

    def test_build_pair_edges_deduplicates_normalized_pairs(self) -> None:
        nodes = [
            Node("paper:a", "paper", "A", None, {"alpha", "shared"}),
            Node("paper:b", "paper", "B", None, {"beta", "shared"}),
            Node("paper:c", "paper", "C", None, {"gamma"}),
        ]

        edges = build_pair_edges(nodes, "paper-paper", top_k=1, min_score=0.01)

        self.assertEqual(len(edges), 1)
        self.assertEqual(edges[0].source_id, "paper:a")
        self.assertEqual(edges[0].target_id, "paper:b")
        self.assertEqual(edges[0].similarity_score, 0.3333)


if __name__ == "__main__":
    unittest.main()
