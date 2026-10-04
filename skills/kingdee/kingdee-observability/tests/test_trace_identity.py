import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path


SCRIPTS = Path(__file__).resolve().parents[1] / "scripts"
sys.path.insert(0, str(SCRIPTS))

from analyze_logs import analyze


def event(operation, span="", parent=""):
    return {
        "traceId": "trace-synthetic", "operation": operation,
        "spanId": span, "parentSpanId": parent,
    }


def flatten(roots):
    nodes, parents = {}, {}

    def visit(node, parent=None):
        nodes[node["operation"]] = node
        parents[node["operation"]] = parent["operation"] if parent else None
        for child in node["children"]:
            visit(child, node)

    for node in roots:
        visit(node)
    return nodes, parents


class TraceIdentityTest(unittest.TestCase):
    def inspect(self, events):
        result = analyze(events, slow_sql_ms=1000, n_plus_one_threshold=3)
        roots = result["traceTrees"][0]["roots"]
        nodes, parents = flatten(roots)
        self.assertEqual(len(events), result["summary"]["eventCount"])
        self.assertEqual(len(events), result["traceTrees"][0]["eventCount"])
        self.assertEqual(len(events), len(nodes))
        self.assertEqual(len(events), len({node["nodeId"] for node in nodes.values()}))
        self.assertEqual(list(range(1, len(events) + 1)), sorted(node["sequence"] for node in nodes.values()))
        for siblings in [roots] + [node["children"] for node in nodes.values()]:
            sequences = [node["sequence"] for node in siblings]
            self.assertEqual(sorted(sequences), sequences)
        return result, nodes, parents

    def test_display_id_without_real_span_is_not_a_parent(self):
        _, nodes, parents = self.inspect([
            event("no-span"), event("child", "child", "event-1"),
        ])
        self.assertIsNone(parents["child"])
        self.assertTrue(nodes["child"]["missingParent"])
        self.assertEqual([], nodes["no-span"]["children"])

    def test_real_span_parent_wins_regardless_of_display_collision_order(self):
        for synthetic_first in (True, False):
            with self.subTest(synthetic_first=synthetic_first):
                events = (
                    [event("filler", "filler"), event("no-span"), event("real-parent", "event-2")]
                    if synthetic_first else
                    [event("real-parent", "event-2"), event("no-span")]
                )
                events.append(event("child", "child", "event-2"))
                _, nodes, parents = self.inspect(events)
                self.assertEqual("real-parent", parents["child"])
                self.assertEqual("event-2#2" if synthetic_first else "event-2", nodes["real-parent"]["nodeId"])
                self.assertEqual([], nodes["no-span"]["children"])
                self.assertNotIn("missingParent", nodes["child"])

    def test_generated_suffix_is_not_a_parent_without_matching_real_span(self):
        _, nodes, parents = self.inspect([
            event("no-span"), event("real-parent", "event-1"),
            event("child", "child", "event-1#2"),
        ])
        self.assertEqual("event-1#2", nodes["real-parent"]["nodeId"])
        self.assertIsNone(parents["child"])
        self.assertTrue(nodes["child"]["missingParent"])

    def test_real_span_suffix_collision_and_duplicates_keep_first_real_parent(self):
        _, nodes, parents = self.inspect([
            event("no-span"), event("first-real", "event-1"),
            event("second-real", "event-1"), event("suffix-real", "event-1#2"),
            event("child", "child", "event-1"),
            event("suffix-child", "suffix-child", "event-1#2"),
        ])
        self.assertEqual("event-1", nodes["no-span"]["nodeId"])
        self.assertEqual("event-1#2", nodes["first-real"]["nodeId"])
        self.assertEqual("event-1#3", nodes["second-real"]["nodeId"])
        self.assertEqual("event-1#2#2", nodes["suffix-real"]["nodeId"])
        self.assertEqual("first-real", parents["child"])
        self.assertEqual("suffix-real", parents["suffix-child"])
        self.assertEqual([], nodes["no-span"]["children"])

    def test_real_parent_missing_parent_cycle_and_duplicate_controls(self):
        cases = {
            "real-parent": [event("parent", "parent"), event("child", "child", "parent")],
            "missing-parent": [event("child", "child", "absent")],
            "cycle": [event("a", "a", "b"), event("b", "b", "a")],
            "duplicate": [event("first", "dup"), event("second", "dup"), event("child", "child", "dup")],
            "no-span": [event("first"), event("second")],
        }
        for name, events in cases.items():
            with self.subTest(case=name):
                result, nodes, parents = self.inspect(events)
                if name == "real-parent":
                    self.assertEqual("parent", parents["child"])
                elif name == "missing-parent":
                    self.assertIsNone(parents["child"])
                    self.assertTrue(nodes["child"]["missingParent"])
                elif name == "cycle":
                    self.assertEqual("b", parents["a"])
                    self.assertIsNone(parents["b"])
                    self.assertTrue(nodes["b"]["cycleBroken"])
                    self.assertEqual(["trace trace-synthetic: cycle broken at span b"], result["warnings"])
                elif name == "duplicate":
                    self.assertEqual("first", parents["child"])
                    self.assertEqual("dup#2", nodes["second"]["nodeId"])
                else:
                    self.assertEqual({"first": None, "second": None}, parents)
                    self.assertEqual(["first", "second"], list(nodes))

    def test_cli_report_attaches_child_only_to_real_span(self):
        with tempfile.TemporaryDirectory(prefix="trace identity ") as temp:
            root = Path(temp)
            source, target = root / "events.json", root / "report.json"
            source.write_text(json.dumps([
                event("filler", "filler"), event("no-span"),
                event("real-parent", "event-2"), event("child", "child", "event-2"),
            ]), encoding="utf-8")
            before = source.read_bytes()
            process = subprocess.run(
                [sys.executable, str(SCRIPTS / "analyze_logs.py"), "--input", str(source), "--output", str(target)],
                capture_output=True, text=True, check=False,
            )
            self.assertEqual(0, process.returncode, process.stderr)
            self.assertEqual(before, source.read_bytes())
            result = json.loads(target.read_text(encoding="utf-8"))
            nodes, parents = flatten(result["traceTrees"][0]["roots"])
            self.assertEqual(4, result["summary"]["eventCount"])
            self.assertEqual("real-parent", parents["child"])
            self.assertEqual("event-2#2", nodes["real-parent"]["nodeId"])
            self.assertEqual([], nodes["no-span"]["children"])


if __name__ == "__main__":
    unittest.main()
