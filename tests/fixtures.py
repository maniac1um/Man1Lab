from pathlib import Path

import fitz

from models.paper_reproduction_analysis import (
    AnalysisEvaluation,
    AnalysisGoal,
    AnalysisMethod,
    AnalysisResources,
    DatasetResource,
    MetricSpec,
    ModelResource,
    PaperMetadata,
    PaperReproductionAnalysis,
    ReproductionScope,
)


def create_sample_paper_pdf(path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    document = fitz.open()
    page = document.new_page()
    page.insert_text(
        (72, 72),
        (
            "Title: Diffusion Policy: Visuomotor Policy Learning via Action Diffusion\n"
            "Abstract: This paper studies visuomotor policy learning via action diffusion.\n"
            "Method: Conditional diffusion model over action sequences.\n"
            "Dataset: Robomimic benchmark tasks.\n"
            "Model: Diffusion policy network.\n"
            "Framework: PyTorch.\n"
            "Optimizer: AdamW.\n"
            "Loss: Behavior cloning diffusion loss.\n"
            "Training: Collect demonstrations, train policy, evaluate success rate.\n"
            "Metric: Task success rate.\n"
        ),
    )
    document.save(path)
    document.close()


def sample_reproduction_analysis(
    source_path: Path | None = None,
) -> PaperReproductionAnalysis:
    return PaperReproductionAnalysis(
        metadata=PaperMetadata(
            title="Diffusion Policy: Visuomotor Policy Learning",
            source_path=source_path,
        ),
        goal=AnalysisGoal(
            scope=ReproductionScope.FULL_REPRODUCTION,
            research_goal="Reproduce visuomotor policy learning via action diffusion.",
            target_experiment="Train and evaluate on Robomimic benchmark tasks.",
            expected_outcome="Match reported task success rate.",
        ),
        resources=AnalysisResources(
            datasets=[DatasetResource(name="Robomimic.", description="Benchmark tasks.")],
            models=[ModelResource(name="Diffusion policy.", description="Policy network.")],
        ),
        method=AnalysisMethod(
            framework="PyTorch",
            architecture="Action diffusion.",
            training_pipeline="Train and evaluate.",
            optimizer="AdamW",
            loss="BC loss.",
        ),
        evaluation=AnalysisEvaluation(
            metrics=[MetricSpec(name="Success rate")],
        ),
    )


def create_empty_paper_pdf(path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    document = fitz.open()
    document.new_page()
    document.save(path)
    document.close()


def create_encrypted_paper_pdf(path: Path, password: str = "secret") -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    document = fitz.open()
    page = document.new_page()
    page.insert_text((72, 72), "Encrypted paper content.")
    document.save(
        path,
        encryption=fitz.PDF_ENCRYPT_AES_256,
        user_pw=password,
    )
    document.close()
