import json
import unittest
from pathlib import Path

from models.paper_reproduction_analysis import (
    SCHEMA_VERSION,
    AnalysisGoal,
    AnalysisMethod,
    ArtifactType,
    GapCategory,
    PaperMetadata,
    PaperReproductionAnalysis,
    ReproductionScope,
)
from validation.exceptions import AnalysisValidationError
from validation.paper_reproduction_analysis import (
    build_paper_reproduction_analysis,
    normalize_analysis_dict,
    validate_analysis_dict,
)

_FULL_DATA = {
    "schema_version": "1.0",
    "metadata": {
        "title": "Deep Residual Learning for Image Recognition",
        "authors": ["Kaiming He", "Xiangyu Zhang"],
        "venue": "CVPR",
        "year": 2016,
        "arxiv_id": "1512.03385",
    },
    "goal": {
        "scope": "full_reproduction",
        "research_goal": "Train very deep convolutional networks using residual connections.",
        "target_experiment": "ImageNet classification with ResNet-50.",
        "expected_outcome": "Match top-1 accuracy reported in Table 1.",
    },
    "resources": {
        "datasets": [
            {
                "name": "ImageNet",
                "description": "1.28M training images.",
                "link": "http://image-net.org/",
                "split_or_variant": "ILSVRC 2012",
            }
        ],
        "models": [
            {
                "name": "ResNet-50",
                "description": "50-layer residual network.",
                "role": "primary model",
            }
        ],
        "dependencies": [
            {"name": "Caffe", "version": "", "purpose": "training framework cited in paper"},
        ],
        "external_resources": [
            {
                "resource_type": "code_repository",
                "name": "official-release",
                "url": "https://github.com/KaimingHe/deep-residual-networks",
                "notes": "",
            }
        ],
        "artifacts": [
            {
                "artifact_type": "pretrained_weight",
                "name": "ResNet-50 ImageNet weights",
                "location": "",
                "notes": "Mentioned but link not provided.",
            }
        ],
    },
    "method": {
        "framework": "caffe",
        "architecture": "Residual blocks with shortcut connections.",
        "training_pipeline": "SGD with batch normalization.",
        "optimizer": "sgd",
        "loss": "Cross-entropy.",
        "hyperparameters": [
            {"name": "batch_size", "value": "256", "notes": ""},
            {"name": "learning_rate", "value": "0.1", "notes": "divided by 10 at epochs 30, 60."},
        ],
        "data_processing": "Random scale cropping and horizontal flipping.",
    },
    "evaluation": {
        "metrics": [
            {
                "name": "top-1 accuracy",
                "definition": "Classification accuracy on validation set.",
                "reported_value": "76.4%",
            }
        ],
        "benchmarks": ["ImageNet ILSVRC 2012"],
        "evaluation_protocol": "Single-crop validation.",
        "baselines": [
            {"name": "VGG-16", "description": "Plain deep CNN baseline."},
        ],
    },
    "reproduction_gaps": [
        {
            "category": "repository",
            "description": "No official training code URL is provided in the paper body.",
        }
    ],
}


class PaperReproductionAnalysisModelTest(unittest.TestCase):
    def test_direct_construction(self) -> None:
        analysis = PaperReproductionAnalysis(
            metadata=PaperMetadata(title="Test Paper"),
            goal=AnalysisGoal(research_goal="Reproduce benchmark results."),
        )
        self.assertEqual(analysis.metadata.title, "Test Paper")
        self.assertEqual(analysis.goal.scope, ReproductionScope.UNKNOWN)
        self.assertEqual(analysis.schema_version, SCHEMA_VERSION)
        self.assertEqual(analysis.resources.datasets, [])
        self.assertEqual(analysis.method.framework, "")

    def test_frozen_model(self) -> None:
        analysis = PaperReproductionAnalysis(
            metadata=PaperMetadata(title="Frozen"),
            goal=AnalysisGoal(research_goal="Goal."),
        )
        with self.assertRaises(Exception):
            analysis.metadata = PaperMetadata(title="Changed")  # type: ignore[misc]


class PaperReproductionAnalysisValidationTest(unittest.TestCase):
    def test_build_success(self) -> None:
        analysis = build_paper_reproduction_analysis(
            _FULL_DATA,
            source_path=Path("paper.pdf"),
        )
        self.assertIsInstance(analysis, PaperReproductionAnalysis)
        self.assertEqual(analysis.metadata.title, _FULL_DATA["metadata"]["title"])
        self.assertEqual(analysis.goal.scope, ReproductionScope.FULL_REPRODUCTION)
        self.assertEqual(analysis.method.optimizer, "SGD")
        self.assertEqual(analysis.resources.datasets[0].name, "ImageNet")
        self.assertEqual(analysis.resources.artifacts[0].artifact_type, ArtifactType.PRETRAINED_WEIGHT)
        self.assertEqual(analysis.reproduction_gaps[0].category, GapCategory.REPOSITORY)
        self.assertEqual(analysis.metadata.source_path, Path("paper.pdf"))
        self.assertEqual(analysis.schema_version, SCHEMA_VERSION)

    def test_minimal_required_fields(self) -> None:
        data = {
            "metadata": {"title": "Minimal Paper"},
            "goal": {"research_goal": "Reproduce the main result."},
        }
        analysis = build_paper_reproduction_analysis(data)
        self.assertEqual(analysis.goal.scope, ReproductionScope.UNKNOWN)
        self.assertEqual(analysis.evaluation.metrics, [])
        self.assertEqual(analysis.reproduction_gaps, [])

    def test_missing_metadata_raises(self) -> None:
        data = {"goal": {"research_goal": "Goal."}}
        with self.assertRaises(AnalysisValidationError):
            validate_analysis_dict(data)

    def test_missing_title_raises(self) -> None:
        data = {"metadata": {}, "goal": {"research_goal": "Goal."}}
        with self.assertRaises(AnalysisValidationError):
            validate_analysis_dict(data)

    def test_missing_research_goal_raises(self) -> None:
        data = {"metadata": {"title": "Paper"}, "goal": {}}
        with self.assertRaises(AnalysisValidationError):
            validate_analysis_dict(data)

    def test_empty_title_raises(self) -> None:
        data = {
            "metadata": {"title": "   "},
            "goal": {"research_goal": "Goal."},
        }
        with self.assertRaises(AnalysisValidationError):
            build_paper_reproduction_analysis(data)

    def test_invalid_scope_raises(self) -> None:
        data = {
            "metadata": {"title": "Paper"},
            "goal": {"research_goal": "Goal.", "scope": "invalid_scope"},
        }
        with self.assertRaises(AnalysisValidationError):
            build_paper_reproduction_analysis(data)

    def test_scope_defaults_to_unknown(self) -> None:
        normalized = normalize_analysis_dict(
            {
                "metadata": {"title": "Paper"},
                "goal": {"research_goal": "Goal."},
            }
        )
        self.assertEqual(normalized["goal"]["scope"], ReproductionScope.UNKNOWN)

    def test_enum_scope_normalization(self) -> None:
        data = dict(_FULL_DATA)
        data["goal"] = dict(data["goal"])
        data["goal"]["scope"] = "TRAINING"
        analysis = build_paper_reproduction_analysis(data)
        self.assertEqual(analysis.goal.scope, ReproductionScope.TRAINING)

    def test_invalid_artifact_type_raises(self) -> None:
        data = json.loads(json.dumps(_FULL_DATA))
        data["resources"]["artifacts"][0]["artifact_type"] = "not_a_type"
        with self.assertRaises(AnalysisValidationError):
            build_paper_reproduction_analysis(data)

    def test_invalid_gap_category_raises(self) -> None:
        data = json.loads(json.dumps(_FULL_DATA))
        data["reproduction_gaps"][0]["category"] = "not_a_category"
        with self.assertRaises(AnalysisValidationError):
            build_paper_reproduction_analysis(data)

    def test_empty_gap_description_raises(self) -> None:
        data = json.loads(json.dumps(_FULL_DATA))
        data["reproduction_gaps"].append({"category": "config", "description": "  "})
        with self.assertRaises(AnalysisValidationError):
            build_paper_reproduction_analysis(data)

    def test_dataset_name_required(self) -> None:
        data = json.loads(json.dumps(_FULL_DATA))
        data["resources"]["datasets"].append({"description": "missing name"})
        with self.assertRaises(AnalysisValidationError):
            build_paper_reproduction_analysis(data)

    def test_optional_string_fields_default_empty(self) -> None:
        analysis = build_paper_reproduction_analysis(
            {
                "metadata": {"title": "Paper"},
                "goal": {"research_goal": "Goal."},
            }
        )
        self.assertEqual(analysis.metadata.venue, "")
        self.assertEqual(analysis.goal.target_experiment, "")
        self.assertEqual(analysis.method.framework, "")
        self.assertEqual(analysis.evaluation.evaluation_protocol, "")

    def test_framework_optimizer_aliases(self) -> None:
        data = {
            "metadata": {"title": "Paper"},
            "goal": {"research_goal": "Goal."},
            "method": {"framework": "pytorch", "optimizer": "adamw"},
        }
        analysis = build_paper_reproduction_analysis(data)
        self.assertEqual(analysis.method.framework, "PyTorch")
        self.assertEqual(analysis.method.optimizer, "AdamW")

    def test_serialization_round_trip(self) -> None:
        original = build_paper_reproduction_analysis(
            _FULL_DATA,
            source_path=Path("paper.pdf"),
        )
        payload = json.loads(original.model_dump_json())
        restored = PaperReproductionAnalysis.model_validate(payload)
        self.assertEqual(restored, original)

    def test_deserialization_from_normalized_dict(self) -> None:
        normalized = normalize_analysis_dict(_FULL_DATA)
        analysis = PaperReproductionAnalysis(
            metadata=PaperMetadata(**normalized["metadata"], source_path=Path("paper.pdf")),
            goal=AnalysisGoal(**normalized["goal"]),
            resources=normalized["resources"],
            method=AnalysisMethod(**normalized["method"]),
            evaluation=normalized["evaluation"],
            reproduction_gaps=normalized["reproduction_gaps"],
            schema_version=normalized["schema_version"],
        )
        self.assertEqual(analysis.metadata.title, _FULL_DATA["metadata"]["title"])
        self.assertEqual(len(analysis.method.hyperparameters), 2)


if __name__ == "__main__":
    unittest.main()
