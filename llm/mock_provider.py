import json

from llm.provider import LLMMessage, LLMProvider

MOCK_PAPER_JSON = json.dumps(
    {
        "title": "Diffusion Policy: Visuomotor Policy Learning via Action Diffusion",
        "abstract": "Mock abstract for skeleton execution.",
        "method": "Action diffusion for visuomotor control.",
        "dataset": "Robomimic benchmark tasks.",
        "model": "Conditional diffusion policy network.",
        "framework": "PyTorch",
        "optimizer": "AdamW",
        "loss": "Behavior cloning diffusion loss.",
        "training_pipeline": "Collect demos, train diffusion policy, evaluate success rate.",
        "evaluation_metric": "Task success rate",
    }
)


MOCK_PLANNER_JSON = json.dumps(
    {
        "paper_title": "Diffusion Policy: Visuomotor Policy Learning via Action Diffusion",
        "tasks": [
            {
                "id": "task_1",
                "name": "Environment setup",
                "description": "Create project structure and configure Python environment.",
                "depends_on": [],
            },
            {
                "id": "task_2",
                "name": "Dependency installation",
                "description": "Install PyTorch and required packages.",
                "depends_on": ["task_1"],
            },
            {
                "id": "task_3",
                "name": "Dataset preparation",
                "description": "Load and preprocess Robomimic benchmark tasks.",
                "depends_on": ["task_2"],
            },
            {
                "id": "task_4",
                "name": "Model implementation",
                "description": "Implement the conditional diffusion policy network.",
                "depends_on": ["task_3"],
            },
            {
                "id": "task_5",
                "name": "Training",
                "description": "Train the model with AdamW and behavior cloning diffusion loss.",
                "depends_on": ["task_4"],
            },
            {
                "id": "task_6",
                "name": "Evaluation",
                "description": "Evaluate task success rate on benchmark tasks.",
                "depends_on": ["task_5"],
            },
        ],
    }
)


MOCK_REVIEWER_PASS_JSON = json.dumps(
    {
        "summary": "Reproduction verification passed all deterministic checks.",
        "analysis": (
            "VerificationResult reports PASS for repository, environment, execution, "
            "and output categories with no recorded findings."
        ),
        "identified_issues": [],
        "strengths": [
            "Repository skeleton and required entrypoint are present.",
            "Environment preparation completed successfully.",
            "Training script executed with exit code 0.",
        ],
        "risk_level": "LOW",
        "next_action": (
            "Proceed with deeper reproduction assessment when additional milestones "
            "are available."
        ),
    }
)


MOCK_REVIEWER_FAIL_JSON = json.dumps(
    {
        "summary": "Reproduction verification failed during execution.",
        "analysis": (
            "VerificationResult reports FAIL in execution_status due to a non-zero "
            "exit code from the training script."
        ),
        "identified_issues": [
            "Execution failed with exit code 1.",
            "Training script returned a non-zero exit code.",
        ],
        "strengths": [
            "Repository structure passed verification.",
            "Environment preparation passed verification.",
        ],
        "risk_level": "HIGH",
        "next_action": (
            "Review execution logs to understand the training failure before "
            "continuing reproduction work."
        ),
    }
)


MOCK_PATCH_NO_ITERATION_JSON = json.dumps(
    {
        "requires_patch": False,
        "priority": "LOW",
        "targets": [],
        "reason": "ReviewReport indicates verification passed with low risk.",
        "strategy": "Proceed to final reporting without another workflow iteration.",
    }
)


MOCK_PATCH_ITERATION_JSON = json.dumps(
    {
        "requires_patch": True,
        "priority": "HIGH",
        "targets": ["execution"],
        "reason": (
            "ReviewReport identifies execution failure requiring another "
            "workflow pass."
        ),
        "strategy": (
            "Schedule another reproduction workflow iteration focused on "
            "execution recovery."
        ),
    }
)


class MockLLMProvider(LLMProvider):
    def __init__(self, response: str = MOCK_PAPER_JSON) -> None:
        self._response = response

    def complete(self, messages: list[LLMMessage], *, temperature: float = 0.0) -> str:
        return self._response
