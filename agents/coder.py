import json
import re
import sys

from agents.coder_quality import (
    build_framework_binding,
    collect_python_files,
    collect_required_packages,
    format_validation_log,
    reconcile_requirements_content,
    validate_generated_repository,
)
from llm.coder_mock_provider import CoderMockLLMProvider
from llm.provider import LLMMessage, LLMProvider
from models.paper import PaperModel
from models.review import PatchPlan
from models.routing import RepositoryTarget, TaskRoutingTable
from models.task import TaskModel, TaskStep
from models.workspace import Workspace
from prompt.builder import PromptBuilder
from prompt.loader import PromptLoader
from routing.task_router import TaskRouter
from workspace.manager import WorkspaceManager

_CATEGORY_ORDER = {
    "source": 0,
    "config": 1,
    "script": 2,
    "dependencies": 3,
}

_SCRIPT_ORDER = {
    "scripts/train.py": 0,
    "scripts/evaluate.py": 1,
}

_PYTHON_DEF_PATTERN = re.compile(r"^def ([A-Za-z_]\w*)", re.MULTILINE)
_PYTHON_CLASS_PATTERN = re.compile(r"^class ([A-Za-z_]\w*)", re.MULTILINE)
_YAML_TOP_LEVEL_KEY_PATTERN = re.compile(r"^([A-Za-z_][A-Za-z0-9_]*)\s*:", re.MULTILINE)


class Coder:
    def __init__(
        self,
        workspace_manager: WorkspaceManager,
        llm: LLMProvider | None = None,
        task_router: TaskRouter | None = None,
        prompt_builder: PromptBuilder | None = None,
    ) -> None:
        self._workspace_manager = workspace_manager
        self._llm = llm or CoderMockLLMProvider()
        self._task_router = task_router or TaskRouter()
        self._prompt_builder = prompt_builder or PromptBuilder(PromptLoader())

    def run(
        self,
        paper: PaperModel,
        task: TaskModel,
        patch_plan: PatchPlan | None = None,
    ) -> Workspace:
        slug = self._paper_slug(paper.title)
        workspace = self._workspace_manager.create_workspace(slug)
        routing_table = self._task_router.route_task(task)
        self._workspace_manager.store_routing_table(workspace, routing_table)
        self._workspace_manager.initialize_repository(
            workspace,
            paper.title,
            task,
            patch_plan,
        )
        shared_generation_context = self._build_shared_generation_context(
            paper,
            task,
            routing_table,
        )
        repository_contract = self._build_repository_contract(
            routing_table,
            shared_generation_context,
        )
        interface_registry: dict[str, object] = {}
        populated_paths = self._populate_repository(
            workspace,
            task,
            routing_table,
            shared_generation_context,
            repository_contract,
            interface_registry,
        )
        routed_paths = {target.relative_path for target in routing_table.targets}
        if "requirements.txt" in routed_paths:
            self._reconcile_requirements(
                workspace,
                shared_generation_context,
                routed_paths,
            )
            if "requirements.txt" not in populated_paths:
                populated_paths.append("requirements.txt")
        self._validate_and_log(
            workspace,
            routing_table,
            shared_generation_context,
            repository_contract,
            interface_registry,
            routed_paths,
        )
        self._finalize_readme(
            workspace,
            paper.title,
            task,
            patch_plan,
            shared_generation_context,
            populated_paths,
        )
        return workspace

    @staticmethod
    def _build_shared_generation_context(
        paper: PaperModel,
        task: TaskModel,
        routing_table: TaskRoutingTable,
    ) -> dict[str, object]:
        targets = routing_table.targets
        routing_coverage = Coder._compute_routing_coverage(task, routing_table)
        framework_binding = build_framework_binding(paper.framework)
        return {
            "paper_title": paper.title,
            "framework": paper.framework,
            "framework_binding": framework_binding,
            "dataset": paper.dataset,
            "model": paper.model,
            "optimizer": paper.optimizer,
            "loss": paper.loss,
            "training_pipeline": paper.training_pipeline,
            "evaluation_metric": paper.evaluation_metric,
            "python_version": f"{sys.version_info.major}.{sys.version_info.minor}",
            "repository_files": [target.relative_path for target in targets],
            "source_modules": [
                target.relative_path.removesuffix(".py").replace("/", ".")
                for target in targets
                if target.file_category == "source"
            ],
            "config_files": [
                target.relative_path
                for target in targets
                if target.file_category == "config"
            ],
            "script_files": [
                target.relative_path
                for target in targets
                if target.file_category == "script"
            ],
            "train_entrypoint": "scripts/train.py",
            "eval_entrypoint": "scripts/evaluate.py",
            "engineering_tasks": [
                {"id": step.id, "name": step.name, "description": step.description}
                for step in task.steps
            ],
            "routing_coverage": routing_coverage,
        }

    @staticmethod
    def _compute_routing_coverage(
        task: TaskModel,
        routing_table: TaskRoutingTable,
    ) -> dict[str, object]:
        covered_ids: set[str] = set()
        router = TaskRouter()
        for step in task.steps:
            if router.route_step(step):
                covered_ids.add(step.id)
        unrouted = [step.id for step in task.steps if step.id not in covered_ids]
        return {
            "routed_step_ids": sorted(covered_ids),
            "unrouted_step_ids": unrouted,
        }

    @staticmethod
    def _build_repository_contract(
        routing_table: TaskRoutingTable,
        shared_generation_context: dict[str, object],
    ) -> dict[str, object]:
        paths = {target.relative_path for target in routing_table.targets}
        module_roles: dict[str, object] = {}
        configuration_roles: dict[str, object] = {}
        execution_expectations: dict[str, object] = {}
        relationships: list[dict[str, str]] = []

        if "src/dataset.py" in paths:
            consumers: list[str] = []
            if "scripts/train.py" in paths:
                consumers.append("scripts/train.py")
            if "scripts/evaluate.py" in paths:
                consumers.append("scripts/evaluate.py")
            module_roles["src/dataset.py"] = {
                "role": "Dataset Provider",
                "module_path": "src.dataset",
                "provides": [
                    "training data access for the training script",
                    "validation data access for the training script",
                ],
                "expected_interface": (
                    "Callable or factory that returns data structures required "
                    "by downstream scripts (e.g. dataloaders or datasets)."
                ),
                "consumers": consumers,
            }

        if "src/model.py" in paths:
            module_roles["src/model.py"] = {
                "role": "Model Builder",
                "module_path": "src.model",
                "provides": ["trainable model construction from configuration"],
                "expected_interface": (
                    "Callable or class that builds a model object usable by "
                    "the training script."
                ),
                "consumers": ["scripts/train.py"] if "scripts/train.py" in paths else [],
            }

        if "configs/train.yaml" in paths:
            configuration_roles["configs/train.yaml"] = {
                "role": "Training Configuration",
                "serves": ["scripts/train.py"] if "scripts/train.py" in paths else [],
                "must_expose": [
                    "dataset selection or reference",
                    "batch size",
                    f"optimizer hyperparameters ({shared_generation_context['optimizer']})",
                ],
                "style_expectation": (
                    "Use one consistent top-level key layout; scripts will read "
                    "the same keys this file defines."
                ),
            }

        if "configs/dataset.yaml" in paths:
            configuration_roles["configs/dataset.yaml"] = {
                "role": "Dataset Configuration",
                "serves": ["src/dataset.py"] if "src/dataset.py" in paths else [],
                "must_expose": ["dataset paths or download settings"],
                "style_expectation": (
                    "Use top-level keys consumed by the Dataset Provider module."
                ),
            }

        if "scripts/train.py" in paths:
            must_consume = ["Dataset Provider interface", "Training Configuration keys"]
            if "src/model.py" in paths:
                must_consume.insert(1, "Model Builder interface")
            execution_expectations["scripts/train.py"] = {
                "role": "Training Entrypoint",
                "runner_invocation": "python scripts/train.py",
                "must_succeed_without_extra_cli_args": True,
                "loads_configuration_from": (
                    "configs/train.yaml" if "configs/train.yaml" in paths else None
                ),
                "must_consume": must_consume,
            }

        if "scripts/evaluate.py" in paths:
            execution_expectations["scripts/evaluate.py"] = {
                "role": "Evaluation Entrypoint",
                "must_reuse": [
                    "Dataset Provider interface (same access pattern as training)",
                ],
            }

        if "scripts/train.py" in paths and "src/dataset.py" in paths:
            relationships.append(
                {
                    "from": "scripts/train.py",
                    "to": "src/dataset.py",
                    "relationship": "imports dataset access from Dataset Provider",
                }
            )
        if "scripts/train.py" in paths and "src/model.py" in paths:
            relationships.append(
                {
                    "from": "scripts/train.py",
                    "to": "src/model.py",
                    "relationship": "imports model construction from Model Builder",
                }
            )
        if "scripts/train.py" in paths and "configs/train.yaml" in paths:
            relationships.append(
                {
                    "from": "scripts/train.py",
                    "to": "configs/train.yaml",
                    "relationship": "reads training hyperparameters and dataset reference",
                }
            )
        if "scripts/evaluate.py" in paths and "src/dataset.py" in paths:
            relationships.append(
                {
                    "from": "scripts/evaluate.py",
                    "to": "src/dataset.py",
                    "relationship": "reuses dataset access from Dataset Provider",
                }
            )
        if "src/dataset.py" in paths and "configs/dataset.yaml" in paths:
            relationships.append(
                {
                    "from": "src/dataset.py",
                    "to": "configs/dataset.yaml",
                    "relationship": "reads dataset paths and download settings",
                }
            )

        file_responsibilities: dict[str, str] = {}
        if "requirements.txt" in paths:
            file_responsibilities["requirements.txt"] = (
                "Declare packages imported by all generated Python files."
            )
        if "src/dataset.py" in paths:
            file_responsibilities["src/dataset.py"] = (
                "Fulfill Dataset Provider role; no training loop."
            )
        if "src/model.py" in paths:
            file_responsibilities["src/model.py"] = (
                "Fulfill Model Builder role when routed."
            )
        if any(path.startswith("configs/") for path in paths):
            file_responsibilities["configs/"] = (
                "Fulfill configuration roles for served modules and scripts."
            )
        if "scripts/train.py" in paths:
            file_responsibilities["scripts/train.py"] = (
                "Orchestrate training using upstream interfaces only."
            )
        if "scripts/evaluate.py" in paths:
            file_responsibilities["scripts/evaluate.py"] = (
                "Evaluate using Dataset Provider; do not redefine dataset access."
            )

        return {
            "framework_binding": shared_generation_context["framework_binding"],
            "module_roles": module_roles,
            "configuration_roles": configuration_roles,
            "execution_expectations": execution_expectations,
            "relationships": relationships,
            "file_responsibilities": file_responsibilities,
        }

    def _populate_repository(
        self,
        workspace: Workspace,
        task: TaskModel,
        routing_table: TaskRoutingTable,
        shared_generation_context: dict[str, object],
        repository_contract: dict[str, object],
        interface_registry: dict[str, object],
    ) -> list[str]:
        populated_paths: list[str] = []
        llm_targets = [
            target
            for target in routing_table.targets
            if target.file_category != "dependencies"
        ]
        for target in self._sort_targets(llm_targets):
            task_step = self._find_task_step(task, target.task_id)
            repository_context = self._format_repository_context(populated_paths)
            contract_slice = self._contract_slice_for_target(
                repository_contract,
                target,
            )
            system_prompt = self._prompt_builder.build_coder_prompt(target.file_category)
            user_prompt = self._format_generation_request(
                shared_generation_context,
                repository_contract,
                contract_slice,
                interface_registry,
                task_step,
                target,
                repository_context,
            )
            messages = [
                LLMMessage(role="system", content=system_prompt),
                LLMMessage(role="user", content=user_prompt),
            ]
            content = self._llm.complete(messages, temperature=0.0)
            self._workspace_manager.write_file(workspace, target.relative_path, content)
            populated_paths.append(target.relative_path)
            if target.file_category in {"source", "config", "script"}:
                self._record_interface_registry(
                    interface_registry,
                    target.relative_path,
                    content,
                    target.file_category,
                )
        return populated_paths

    def _reconcile_requirements(
        self,
        workspace: Workspace,
        shared_generation_context: dict[str, object],
        routed_paths: set[str],
    ) -> None:
        python_paths = sorted(
            path for path in routed_paths if path.endswith(".py")
        )
        python_files = collect_python_files(workspace.root_path, python_paths)
        framework = str(shared_generation_context.get("framework", ""))
        required = collect_required_packages(python_files, framework)
        existing = ""
        requirements_path = workspace.root_path / "requirements.txt"
        if requirements_path.is_file():
            existing = requirements_path.read_text(encoding="utf-8")
        content = reconcile_requirements_content(existing, required)
        self._workspace_manager.write_file(workspace, "requirements.txt", content)

    def _validate_and_log(
        self,
        workspace: Workspace,
        routing_table: TaskRoutingTable,
        shared_generation_context: dict[str, object],
        repository_contract: dict[str, object],
        interface_registry: dict[str, object],
        routed_paths: set[str],
    ) -> None:
        python_paths = sorted(
            path for path in routed_paths if path.endswith(".py")
        )
        python_files = collect_python_files(workspace.root_path, python_paths)
        requirements_content = ""
        requirements_path = workspace.root_path / "requirements.txt"
        if requirements_path.is_file():
            requirements_content = requirements_path.read_text(encoding="utf-8")
        framework_binding = repository_contract.get("framework_binding", {})
        if not isinstance(framework_binding, dict):
            framework_binding = build_framework_binding(
                str(shared_generation_context.get("framework", ""))
            )
        findings = validate_generated_repository(
            workspace_root=workspace.root_path,
            routed_paths=routed_paths,
            python_files=python_files,
            requirements_content=requirements_content,
            framework_binding=framework_binding,
            interface_registry=interface_registry,
        )
        log_content = format_validation_log(findings)
        logs_dir = workspace.root_path / "logs"
        logs_dir.mkdir(parents=True, exist_ok=True)
        (logs_dir / "generation_validation.log").write_text(
            log_content,
            encoding="utf-8",
        )

    def _finalize_readme(
        self,
        workspace: Workspace,
        paper_title: str,
        task: TaskModel,
        patch_plan: PatchPlan | None,
        shared_generation_context: dict[str, object],
        populated_paths: list[str],
    ) -> None:
        unique_paths = list(dict.fromkeys(populated_paths))
        readme_content = self._format_populated_readme(
            paper_title,
            task,
            patch_plan,
            shared_generation_context,
            unique_paths,
        )
        self._workspace_manager.write_file(workspace, "README.md", readme_content)

    @staticmethod
    def _sort_targets(targets: list[RepositoryTarget]) -> list[RepositoryTarget]:
        def sort_key(target: RepositoryTarget) -> tuple[int, int, str]:
            script_rank = _SCRIPT_ORDER.get(target.relative_path, 50)
            return (
                _CATEGORY_ORDER.get(target.file_category, 99),
                script_rank,
                target.relative_path,
            )

        return sorted(targets, key=sort_key)

    @staticmethod
    def _find_task_step(task: TaskModel, task_id: str) -> TaskStep:
        for step in task.steps:
            if step.id == task_id:
                return step
        raise ValueError(f"Task step not found for routing target: {task_id}")

    @staticmethod
    def _format_repository_context(populated_paths: list[str]) -> str:
        if not populated_paths:
            return "No repository files generated yet."
        lines = ["Existing repository files:"]
        lines.extend(f"- {path}" for path in populated_paths)
        return "\n".join(lines)

    @staticmethod
    def _format_json_block(data: dict[str, object]) -> str:
        return json.dumps(data, indent=2, sort_keys=True)

    @staticmethod
    def _contract_slice_for_target(
        repository_contract: dict[str, object],
        target: RepositoryTarget,
    ) -> dict[str, object]:
        slice_data: dict[str, object] = {}
        module_roles = repository_contract.get("module_roles", {})
        if isinstance(module_roles, dict) and target.relative_path in module_roles:
            slice_data["module_role"] = module_roles[target.relative_path]

        configuration_roles = repository_contract.get("configuration_roles", {})
        if (
            isinstance(configuration_roles, dict)
            and target.relative_path in configuration_roles
        ):
            slice_data["configuration_role"] = configuration_roles[target.relative_path]

        execution_expectations = repository_contract.get("execution_expectations", {})
        if (
            isinstance(execution_expectations, dict)
            and target.relative_path in execution_expectations
        ):
            slice_data["execution_expectation"] = execution_expectations[
                target.relative_path
            ]

        responsibilities = repository_contract.get("file_responsibilities", {})
        if isinstance(responsibilities, dict):
            if target.relative_path in responsibilities:
                slice_data["file_responsibility"] = responsibilities[target.relative_path]
            elif target.file_category == "config" and "configs/" in responsibilities:
                slice_data["file_responsibility"] = responsibilities["configs/"]
            elif (
                target.file_category == "dependencies"
                and "requirements.txt" in responsibilities
            ):
                slice_data["file_responsibility"] = responsibilities["requirements.txt"]

        relationships = repository_contract.get("relationships", [])
        if isinstance(relationships, list):
            related = [
                edge
                for edge in relationships
                if isinstance(edge, dict)
                and (
                    edge.get("from") == target.relative_path
                    or edge.get("to") == target.relative_path
                )
            ]
            if related:
                slice_data["relationships"] = related

        return slice_data

    @staticmethod
    def _extract_python_symbols(content: str) -> dict[str, object]:
        functions = _PYTHON_DEF_PATTERN.findall(content)
        classes = _PYTHON_CLASS_PATTERN.findall(content)
        public_symbols = functions + classes
        symbol_kinds = {name: "function" for name in functions}
        symbol_kinds.update({name: "class" for name in classes})
        return {
            "public_symbols": public_symbols,
            "symbol_kinds": symbol_kinds,
        }

    @staticmethod
    def _extract_yaml_top_level_keys(content: str) -> list[str]:
        keys: list[str] = []
        for line in content.splitlines():
            stripped = line.strip()
            if not stripped or stripped.startswith("#"):
                continue
            if line.startswith((" ", "\t")):
                continue
            match = _YAML_TOP_LEVEL_KEY_PATTERN.match(line)
            if match:
                keys.append(match.group(1))
        return keys

    @classmethod
    def _record_interface_registry(
        cls,
        interface_registry: dict[str, object],
        relative_path: str,
        content: str,
        file_category: str,
    ) -> None:
        if file_category == "source":
            symbols = cls._extract_python_symbols(content)
            symbols["import_roots"] = cls._extract_import_roots_for_registry(content)
            interface_registry[relative_path] = symbols
            return
        if file_category == "config":
            interface_registry[relative_path] = {
                "top_level_keys": cls._extract_yaml_top_level_keys(content),
            }
            return
        if file_category == "script":
            interface_registry[relative_path] = {
                "import_roots": cls._extract_import_roots_for_registry(content),
                "config_keys": cls._extract_config_keys_for_registry(content),
            }

    @staticmethod
    def _extract_import_roots_for_registry(content: str) -> list[str]:
        from agents.coder_quality import extract_python_import_roots

        return extract_python_import_roots(content)

    @staticmethod
    def _extract_config_keys_for_registry(content: str) -> list[str]:
        from agents.coder_quality import extract_config_key_accesses

        return extract_config_key_accesses(content)

    @staticmethod
    def _format_generation_request(
        shared_generation_context: dict[str, object],
        repository_contract: dict[str, object],
        contract_slice: dict[str, object],
        interface_registry: dict[str, object],
        task_step: TaskStep,
        target: RepositoryTarget,
        repository_context: str,
    ) -> str:
        registry_text = (
            Coder._format_json_block(interface_registry)
            if interface_registry
            else "No interfaces recorded yet."
        )
        return "\n".join(
            [
                "Shared generation context:",
                Coder._format_json_block(shared_generation_context),
                "",
                "Repository contract (interface roles):",
                Coder._format_json_block(repository_contract),
                "",
                "Interface registry (commitments from files already generated):",
                registry_text,
                "",
                "Contract obligations for this target:",
                Coder._format_json_block(contract_slice),
                "",
                f"Engineering task: {task_step.id} - {task_step.name}",
                f"Task description: {task_step.description}",
                f"Target file: {target.relative_path}",
                f"File category: {target.file_category}",
                "Repository context:",
                repository_context,
                "",
                "Hard constraints (MANDATORY):",
                (
                    f"- MUST implement using framework "
                    f"'{shared_generation_context.get('framework')}' only. "
                    "NEVER import a different deep-learning framework."
                ),
                (
                    "- MUST NOT import any module root listed in "
                    "framework_binding.forbidden_import_roots."
                ),
                "- MUST fulfill the interface role for this file.",
                (
                    "- If you are a source or config file, MUST expose a stable "
                    "public interface that downstream files will import or read."
                ),
                (
                    "- If you are a script, MUST import ONLY symbols listed in "
                    "the interface registry for upstream modules."
                ),
                (
                    "- If you are a script, MUST read ONLY configuration keys "
                    "listed in the interface registry for config files."
                ),
                (
                    "- MUST NOT invent alternate dataset or model access patterns "
                    "when a provider module exists in the registry."
                ),
                (
                    "- Training entrypoint MUST run as: python scripts/train.py "
                    "with NO required CLI arguments."
                ),
                (
                    "- REQUIRED: Repository contract and interface registry "
                    "obligations override local task wording."
                ),
            ]
        )

    @staticmethod
    def _format_populated_readme(
        paper_title: str,
        task: TaskModel,
        patch_plan: PatchPlan | None,
        shared_generation_context: dict[str, object],
        populated_paths: list[str],
    ) -> str:
        lines = [
            f"# {paper_title}",
            "",
            "## Reproduction Context",
            "",
            f"- **Framework:** {shared_generation_context['framework']}",
            f"- **Dataset:** {shared_generation_context['dataset']}",
            f"- **Model:** {shared_generation_context['model']}",
            f"- **Optimizer:** {shared_generation_context['optimizer']}",
            f"- **Python version:** {shared_generation_context['python_version']}",
            "",
            "## Project Structure",
            "",
            "```text",
            ".",
            "├── src/",
            "├── configs/",
            "├── scripts/",
            "├── outputs/",
            "├── logs/",
            "├── README.md",
            "└── requirements.txt",
            "```",
            "",
            "## Generated Files",
            "",
        ]
        if populated_paths:
            lines.extend(f"- `{path}`" for path in populated_paths)
        else:
            lines.append("- No implementation files generated.")
        lines.extend(
            [
                "",
                "## Engineering Tasks",
                "",
            ]
        )
        for step in task.steps:
            lines.append(
                f"- **{step.id}** ({step.status}): {step.name} — {step.description}"
            )
        if not task.steps:
            lines.append("- No tasks defined.")
        lines.extend(
            [
                "",
                "## Workspace Status",
                "",
                "- **Repository skeleton:** created",
                "- **Source code generation:** complete",
                "- **Configuration generation:** complete",
                "",
                "This workspace contains generated implementation files.",
            ]
        )
        if patch_plan is not None:
            lines.extend(
                [
                    "",
                    "## Patch Planning",
                    "",
                    patch_plan.reason,
                ]
            )
        return "\n".join(lines) + "\n"

    @staticmethod
    def _paper_slug(title: str) -> str:
        slug = re.sub(r"[^a-z0-9]+", "_", title.lower()).strip("_")
        return slug or "paper"
