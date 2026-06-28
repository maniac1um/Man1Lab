import unittest
from pathlib import Path

from models.paper import PaperModel
from validation.exceptions import PaperValidationError
from validation.paper import build_paper_model, normalize_paper_dict, validate_paper_dict

_FULL_DATA = {
    "title": "Diffusion Policy",
    "abstract": "An abstract.",
    "method": "Diffusion control.",
    "dataset": "Robomimic.",
    "model": "Diffusion network.",
    "framework": "pytorch",
    "optimizer": "adamw",
    "loss": "BC loss.",
    "training_pipeline": "Train and evaluate.",
    "evaluation_metric": "Success rate.",
}


class PaperValidationTest(unittest.TestCase):
    def test_build_paper_model_success(self) -> None:
        paper = build_paper_model(_FULL_DATA, Path("paper.pdf"))
        self.assertIsInstance(paper, PaperModel)
        self.assertEqual(paper.title, "Diffusion Policy")
        self.assertEqual(paper.framework, "PyTorch")
        self.assertEqual(paper.optimizer, "AdamW")
        self.assertEqual(paper.source_path, Path("paper.pdf"))

    def test_missing_required_field_raises(self) -> None:
        data = dict(_FULL_DATA)
        del data["title"]
        with self.assertRaises(PaperValidationError):
            validate_paper_dict(data)

    def test_empty_title_raises(self) -> None:
        data = dict(_FULL_DATA)
        data["title"] = "   "
        with self.assertRaises(PaperValidationError):
            build_paper_model(data, Path("paper.pdf"))

    def test_normalization(self) -> None:
        data = dict(_FULL_DATA)
        data["framework"] = "tensorflow"
        data["optimizer"] = "adam"
        normalized = normalize_paper_dict(data)
        self.assertEqual(normalized["framework"], "TensorFlow")
        self.assertEqual(normalized["optimizer"], "Adam")

    def test_optional_fields_default_to_empty_string(self) -> None:
        paper = build_paper_model({"title": "Only Title"}, Path("paper.pdf"))
        self.assertEqual(paper.abstract, "")
        self.assertEqual(paper.method, "")


if __name__ == "__main__":
    unittest.main()
