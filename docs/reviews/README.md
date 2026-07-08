# Review Documents

Phase implementation audits for Man1Lab platform capabilities. Each directory follows the `x.x_feature_name` naming convention and contains an `audit.md` report.

For current project state, see [CURRENT_STATUS.md](../CURRENT_STATUS.md). For accepted architecture decisions, see [adr/README.md](../adr/README.md).

---

## Release Audits

| Directory | Scope |
|-----------|-------|
| [1.2.2_release_candidate/](1.2.2_release_candidate/) | v1.2.2 release preparation audit |
| [1.2.2_release_readiness/](1.2.2_release_readiness/) | v1.2.2 final release readiness audit |
| [community_health_files/](community_health_files/) | GitHub community health documentation |

---

## Platform Foundation (1.x)

| Directory | Scope |
|-----------|-------|
| [1.0_platform_facade/](1.0_platform_facade/) | Platform Facade |
| [1.0_cli_interface/](1.0_cli_interface/) | CLI interface |
| [1.0_python_sdk/](1.0_python_sdk/) | Python SDK |
| [1.0_package_distribution/](1.0_package_distribution/) | Package distribution |
| [1.0_mlflow_migration/](1.0_mlflow_migration/) | MLflow migration |

---

## Discovery & GitHub (1.x – 4.x)

| Directory | Scope |
|-----------|-------|
| [1.1_discovery_foundation/](1.1_discovery_foundation/) | Discovery foundation |
| [1.1_github_client_foundation/](1.1_github_client_foundation/) | GitHub client |
| [1.2_github_collection_provider/](1.2_github_collection_provider/) | GitHub collection |
| [2.0_github_evidence_provider/](2.0_github_evidence_provider/) | GitHub evidence |
| [2.1_discovery_collection/](2.1_discovery_collection/) | Discovery collection |
| [2.2_discovery_evidence/](2.2_discovery_evidence/) | Discovery evidence |
| [2.3_discovery_verification/](2.3_discovery_verification/) | Discovery verification |
| [2.4_discovery_ranking/](2.4_discovery_ranking/) | Discovery ranking |
| [3.0_github_verification_provider/](3.0_github_verification_provider/) | GitHub verification |
| [4.0_github_ranking_provider/](4.0_github_ranking_provider/) | GitHub ranking |

---

## Execution Planning (2.x – 6.x)

| Directory | Scope |
|-----------|-------|
| [2.0_execution_planning_validation/](2.0_execution_planning_validation/) | Validation layer |
| [3.0_execution_planning_runtime/](3.0_execution_planning_runtime/) | Runtime stage models |
| [4.0_execution_planning_builder/](4.0_execution_planning_builder/) | Strategy builder |
| [5.1_execution_planning_workflow/](5.1_execution_planning_workflow/) | Workflow coordinator |
| [5.2_execution_planning_services/](5.2_execution_planning_services/) | Service layer |
| [5.3_final_platform_integration/](5.3_final_platform_integration/) | Platform integration |
| [6.1_execution_planning_strategy_provider/](6.1_execution_planning_strategy_provider/) | Strategy provider |
| [6.2_execution_planning_binding_provider/](6.2_execution_planning_binding_provider/) | Binding provider |
| [6.3_execution_planning_reuse_provider/](6.3_execution_planning_reuse_provider/) | Reuse provider |
| [6.4_execution_planning_adaptation_provider/](6.4_execution_planning_adaptation_provider/) | Adaptation provider |
| [6.5_execution_planning_generation_provider/](6.5_execution_planning_generation_provider/) | Generation provider |
| [6.6_execution_planning_risk_provider/](6.6_execution_planning_risk_provider/) | Risk provider |
| [6.7_execution_planning_architecture_stabilization/](6.7_execution_planning_architecture_stabilization/) | Architecture stabilization |
| [6.8_execution_planning_document_sync/](6.8_execution_planning_document_sync/) | Document synchronization |

---

## LLM Platform (7.x)

| Directory | Scope |
|-----------|-------|
| [7.1_llm_provider_foundation/](7.1_llm_provider_foundation/) | LLM provider foundation |
| [7.2_model_registry/](7.2_model_registry/) | Model Registry |
| [7.3_anthropic_provider/](7.3_anthropic_provider/) | Anthropic provider |
| [7.4_model_management_cli/](7.4_model_management_cli/) | Model Management CLI |
| [7.5_first_run_experience/](7.5_first_run_experience/) | First-run Experience |

---

## Runtime (8.x)

| Directory | Scope |
|-----------|-------|
| [8.1_runtime_performance_audit/](8.1_runtime_performance_audit/) | Runtime profiling foundation |
| [8.2_runtime_lifecycle/](8.2_runtime_lifecycle/) | Platform runtime lifecycle owner |
| [8.3_runtime_lazy_initialization/](8.3_runtime_lazy_initialization/) | Runtime lazy initialization subsystem |
| [8.4_runtime_resource_management/](8.4_runtime_resource_management/) | Runtime resource manager, descriptors, health, cache policy |
| [8.5_runtime_session/](8.5_runtime_session/) | Runtime session lifecycle and workspace placeholder |

---

## Private work documents

Technology adoption reviews, working roadmaps, and research notes may also exist in `private/` (local, gitignored). See [CONTRIBUTING.md](../../CONTRIBUTING.md#documentation-policy).
