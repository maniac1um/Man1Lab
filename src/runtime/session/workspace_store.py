"""Runtime-owned persistence for session workspace artifacts."""

from __future__ import annotations

import json
from pathlib import Path

from models.decision_trace import DecisionTrace
from models.execution_graph import ExecutionGraph
from models.execution_strategy import ExecutionStrategy
from models.paper_reproduction_analysis import PaperReproductionAnalysis
from models.research_resource_discovery import ResearchResourceDiscovery
from validation.execution_strategy import build_execution_strategy
from validation.paper_reproduction_analysis import build_paper_reproduction_analysis
from validation.research_resource_discovery import build_research_resource_discovery

ANALYSIS_DIR = "analysis"
DISCOVERY_DIR = "discovery"
PLANNING_DIR = "planning"
DECISION_DIR = "decision"

ANALYSIS_JSON = "analysis.json"
ANALYSIS_MD = "analysis.md"
PARSED_DOCUMENT_MD = "parsed_document.md"
PARSED_DOCUMENT_META = "parsed_document_meta.json"
DISCOVERY_JSON = "resources.json"
DISCOVERY_MD = "summary.md"
STRATEGY_JSON = "execution_strategy.json"
PLANNING_MD = "summary.md"
DECISION_TRACE_JSON = "decision_trace.json"
DECISION_TRACE_MD = "decision_trace.md"
EXECUTION_GRAPH_JSON = "execution_graph.json"
EXECUTION_GRAPH_MD = "execution_graph.md"


class WorkspaceArtifactStore:
    """Persist and load canonical session artifacts under the workspace root."""

    def __init__(self, workspace_root: Path) -> None:
        self._root = workspace_root

    @property
    def root(self) -> Path:
        return self._root

    def analysis_json_path(self) -> Path:
        return self._root / ANALYSIS_DIR / ANALYSIS_JSON

    def analysis_md_path(self) -> Path:
        return self._root / ANALYSIS_DIR / ANALYSIS_MD

    def parsed_document_md_path(self) -> Path:
        return self._root / ANALYSIS_DIR / PARSED_DOCUMENT_MD

    def parsed_document_meta_path(self) -> Path:
        return self._root / ANALYSIS_DIR / PARSED_DOCUMENT_META

    def discovery_json_path(self) -> Path:
        return self._root / DISCOVERY_DIR / DISCOVERY_JSON

    def strategy_json_path(self) -> Path:
        return self._root / PLANNING_DIR / STRATEGY_JSON

    def decision_trace_json_path(self) -> Path:
        return self._root / DECISION_DIR / DECISION_TRACE_JSON

    def execution_graph_json_path(self) -> Path:
        return self._root / DECISION_DIR / EXECUTION_GRAPH_JSON

    def has_analysis(self) -> bool:
        return self.analysis_json_path().is_file()

    def has_discovery(self) -> bool:
        return self.discovery_json_path().is_file()

    def has_strategy(self) -> bool:
        return self.strategy_json_path().is_file()

    def has_decision_trace(self) -> bool:
        return self.decision_trace_json_path().is_file()

    def has_execution_graph(self) -> bool:
        return self.execution_graph_json_path().is_file()

    def has_parsed_document(self) -> bool:
        return self.parsed_document_md_path().is_file() and self.parsed_document_meta_path().is_file()

    def save_parsed_document(self, paper_path: Path, markdown: str) -> None:
        analysis_dir = self._root / ANALYSIS_DIR
        analysis_dir.mkdir(parents=True, exist_ok=True)
        self.parsed_document_md_path().write_text(markdown, encoding="utf-8")
        meta = {
            "source_path": str(paper_path.resolve()),
            "source_size_bytes": paper_path.stat().st_size if paper_path.is_file() else None,
            "source_mtime_ns": paper_path.stat().st_mtime_ns if paper_path.is_file() else None,
            "markdown_chars": len(markdown),
        }
        self.parsed_document_meta_path().write_text(
            json.dumps(meta, indent=2) + "\n",
            encoding="utf-8",
        )

    def load_parsed_document(self, paper_path: Path) -> str | None:
        if not self.has_parsed_document():
            return None
        try:
            meta = json.loads(self.parsed_document_meta_path().read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            return None
        resolved = paper_path.resolve()
        if meta.get("source_path") != str(resolved):
            return None
        if not resolved.is_file():
            return None
        if meta.get("source_size_bytes") != resolved.stat().st_size:
            return None
        if meta.get("source_mtime_ns") != resolved.stat().st_mtime_ns:
            return None
        return self.parsed_document_md_path().read_text(encoding="utf-8")

    def save_analysis(self, analysis: PaperReproductionAnalysis) -> None:
        analysis_dir = self._root / ANALYSIS_DIR
        analysis_dir.mkdir(parents=True, exist_ok=True)
        json_path = analysis_dir / ANALYSIS_JSON
        md_path = analysis_dir / ANALYSIS_MD
        json_path.write_text(
            json.dumps(analysis.model_dump(mode="json"), indent=2, default=str) + "\n",
            encoding="utf-8",
        )
        md_path.write_text(_format_analysis_summary(analysis), encoding="utf-8")

    def save_discovery(self, discovery: ResearchResourceDiscovery) -> None:
        discovery_dir = self._root / DISCOVERY_DIR
        discovery_dir.mkdir(parents=True, exist_ok=True)
        json_path = discovery_dir / DISCOVERY_JSON
        md_path = discovery_dir / DISCOVERY_MD
        json_path.write_text(discovery.model_dump_json(indent=2) + "\n", encoding="utf-8")
        md_path.write_text(_format_discovery_summary(discovery), encoding="utf-8")

    def save_strategy(self, strategy: ExecutionStrategy) -> None:
        planning_dir = self._root / PLANNING_DIR
        planning_dir.mkdir(parents=True, exist_ok=True)
        json_path = planning_dir / STRATEGY_JSON
        md_path = planning_dir / PLANNING_MD
        json_path.write_text(strategy.model_dump_json(indent=2) + "\n", encoding="utf-8")
        md_path.write_text(_format_strategy_summary(strategy), encoding="utf-8")

    def save_decision_trace(self, trace: DecisionTrace) -> None:
        decision_dir = self._root / DECISION_DIR
        decision_dir.mkdir(parents=True, exist_ok=True)
        json_path = decision_dir / DECISION_TRACE_JSON
        md_path = decision_dir / DECISION_TRACE_MD
        json_path.write_text(trace.model_dump_json(indent=2) + "\n", encoding="utf-8")
        md_path.write_text(_format_decision_trace_summary(trace), encoding="utf-8")

    def save_execution_graph(self, graph: ExecutionGraph) -> None:
        decision_dir = self._root / DECISION_DIR
        decision_dir.mkdir(parents=True, exist_ok=True)
        json_path = decision_dir / EXECUTION_GRAPH_JSON
        md_path = decision_dir / EXECUTION_GRAPH_MD
        json_path.write_text(graph.model_dump_json(indent=2) + "\n", encoding="utf-8")
        md_path.write_text(_format_execution_graph_summary(graph), encoding="utf-8")

    def load_analysis(self) -> PaperReproductionAnalysis | None:
        path = self.analysis_json_path()
        if not path.is_file():
            return None
        data = json.loads(path.read_text(encoding="utf-8"))
        source_path = data.get("metadata", {}).get("source_path")
        return build_paper_reproduction_analysis(
            data,
            source_path=Path(source_path) if source_path else None,
        )

    def load_discovery(self) -> ResearchResourceDiscovery | None:
        path = self.discovery_json_path()
        if not path.is_file():
            return None
        data = json.loads(path.read_text(encoding="utf-8"))
        return build_research_resource_discovery(data)

    def load_strategy(self) -> ExecutionStrategy | None:
        path = self.strategy_json_path()
        if not path.is_file():
            return None
        data = json.loads(path.read_text(encoding="utf-8"))
        return build_execution_strategy(data)

    def load_decision_trace(self) -> DecisionTrace | None:
        path = self.decision_trace_json_path()
        if not path.is_file():
            return None
        return DecisionTrace.model_validate_json(path.read_text(encoding="utf-8"))

    def load_execution_graph(self) -> ExecutionGraph | None:
        path = self.execution_graph_json_path()
        if not path.is_file():
            return None
        return ExecutionGraph.model_validate_json(path.read_text(encoding="utf-8"))


def _format_analysis_summary(analysis: PaperReproductionAnalysis) -> str:
    metadata = analysis.metadata
    goal = analysis.goal
    lines = [
        "# Paper Analysis",
        "",
        f"**Title:** {metadata.title}",
    ]
    if metadata.authors:
        lines.append(f"**Authors:** {', '.join(metadata.authors)}")
    if metadata.year is not None:
        lines.append(f"**Year:** {metadata.year}")
    lines.extend(
        [
            "",
            "## Reproduction Goal",
            "",
            goal.research_goal or "_No research goal recorded._",
            "",
            f"**Scope:** {goal.scope.value}",
        ]
    )
    gap_count = len(analysis.reproduction_gaps)
    lines.extend(["", f"**Reproduction gaps:** {gap_count}", ""])
    return "\n".join(lines)


def _format_discovery_summary(discovery: ResearchResourceDiscovery) -> str:
    metadata = discovery.metadata
    stats = discovery.statistics
    lines = [
        "# Resource Discovery",
        "",
        f"**Discovery ID:** {metadata.discovery_id}",
        f"**Status:** {metadata.status.value}",
        f"**Candidates:** {stats.candidate_count}",
        f"**Selected:** {metadata.selection_count}",
        "",
        metadata.summary or "_No summary recorded._",
        "",
    ]
    return "\n".join(lines)


def _format_strategy_summary(strategy: ExecutionStrategy) -> str:
    metadata = strategy.metadata
    posture = strategy.strategy.primary_posture
    lines = [
        "# Execution Strategy",
        "",
        f"**Strategy ID:** {metadata.strategy_id}",
        f"**Status:** {metadata.status.value}",
        f"**Posture:** {posture.value}",
        "",
        metadata.summary or strategy.strategy.rationale or "_No summary recorded._",
        "",
    ]
    return "\n".join(lines)


def _format_decision_trace_summary(trace: DecisionTrace) -> str:
    lines = [
        "# Decision Trace",
        "",
        f"**Trace ID:** {trace.trace_id}",
        f"**Discovery ID:** {trace.discovery_id or 'n/a'}",
        f"**Strategy ID:** {trace.strategy_id or 'n/a'}",
        "",
        "## Stages",
        "",
    ]
    for stage in trace.stages:
        lines.extend(
            [
                f"### {stage.stage.value}",
                "",
                f"**Rule:** {stage.decision_rule or 'n/a'}",
                "",
                stage.rationale or "_No rationale recorded._",
                "",
            ]
        )
    return "\n".join(lines)


def _format_execution_graph_summary(graph: ExecutionGraph) -> str:
    lines = [
        "# Execution Graph",
        "",
        f"**Graph ID:** {graph.graph_id}",
        f"**Strategy ID:** {graph.strategy_id}",
        "",
        "## Nodes",
        "",
    ]
    for node in graph.nodes:
        deps = ", ".join(node.depends_on) if node.depends_on else "none"
        lines.extend(
            [
                f"### {node.label} (`{node.stage_type.value}`)",
                "",
                f"**Depends on:** {deps}",
                "",
                node.rationale or "_No rationale recorded._",
                "",
            ]
        )
    return "\n".join(lines)
