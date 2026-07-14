from enum import Enum
from pathlib import Path

from pydantic import BaseModel, ConfigDict, Field

SCHEMA_VERSION = "1.0"


class ReproductionScope(str, Enum):
    FULL_REPRODUCTION = "full_reproduction"
    TRAINING = "training"
    INFERENCE = "inference"
    EVALUATION = "evaluation"
    ABLATION = "ablation"
    BENCHMARK = "benchmark"
    UNKNOWN = "unknown"


class ArtifactType(str, Enum):
    CHECKPOINT = "checkpoint"
    PRETRAINED_WEIGHT = "pretrained_weight"
    TOKENIZER = "tokenizer"
    VOCABULARY = "vocabulary"
    CONFIG = "config"
    CALIBRATION = "calibration"
    OTHER = "other"


class GapCategory(str, Enum):
    HYPERPARAMETER = "hyperparameter"
    REPOSITORY = "repository"
    DATASET_LINK = "dataset_link"
    CONFIG = "config"
    CHECKPOINT = "checkpoint"
    EVALUATION_DETAIL = "evaluation_detail"
    IMPLEMENTATION_DETAIL = "implementation_detail"
    OTHER = "other"


class PaperMetadata(BaseModel):
    model_config = ConfigDict(frozen=True)

    title: str
    source_path: Path | None = None
    authors: list[str] = Field(default_factory=list)
    venue: str = ""
    year: int | None = None
    arxiv_id: str = ""


class AnalysisGoal(BaseModel):
    model_config = ConfigDict(frozen=True)

    scope: ReproductionScope = ReproductionScope.UNKNOWN
    research_goal: str
    target_experiment: str = ""
    expected_outcome: str = ""


class DatasetResource(BaseModel):
    model_config = ConfigDict(frozen=True)

    name: str
    description: str = ""
    link: str = ""
    split_or_variant: str = ""


class ModelResource(BaseModel):
    model_config = ConfigDict(frozen=True)

    name: str
    description: str = ""
    role: str = ""


class DependencyResource(BaseModel):
    model_config = ConfigDict(frozen=True)

    name: str
    version: str = ""
    purpose: str = ""


class ExternalResource(BaseModel):
    model_config = ConfigDict(frozen=True)

    resource_type: str
    name: str
    url: str = ""
    notes: str = ""


class ArtifactReference(BaseModel):
    model_config = ConfigDict(frozen=True)

    artifact_type: ArtifactType
    name: str
    location: str = ""
    notes: str = ""


class AnalysisResources(BaseModel):
    model_config = ConfigDict(frozen=True)

    datasets: list[DatasetResource] = Field(default_factory=list)
    models: list[ModelResource] = Field(default_factory=list)
    dependencies: list[DependencyResource] = Field(default_factory=list)
    external_resources: list[ExternalResource] = Field(default_factory=list)
    artifacts: list[ArtifactReference] = Field(default_factory=list)


class Hyperparameter(BaseModel):
    model_config = ConfigDict(frozen=True)

    name: str
    value: str = ""
    notes: str = ""


class AnalysisMethod(BaseModel):
    model_config = ConfigDict(frozen=True)

    framework: str = ""
    architecture: str = ""
    training_pipeline: str = ""
    optimizer: str = ""
    loss: str = ""
    hyperparameters: list[Hyperparameter] = Field(default_factory=list)
    data_processing: str = ""


class MetricSpec(BaseModel):
    model_config = ConfigDict(frozen=True)

    name: str
    definition: str = ""
    reported_value: str = ""


class BaselineSpec(BaseModel):
    model_config = ConfigDict(frozen=True)

    name: str
    description: str = ""


class AnalysisEvaluation(BaseModel):
    model_config = ConfigDict(frozen=True)

    metrics: list[MetricSpec] = Field(default_factory=list)
    benchmarks: list[str] = Field(default_factory=list)
    evaluation_protocol: str = ""
    baselines: list[BaselineSpec] = Field(default_factory=list)


class ReproductionGap(BaseModel):
    model_config = ConfigDict(frozen=True)

    category: GapCategory
    description: str


class PaperReproductionAnalysis(BaseModel):
    model_config = ConfigDict(frozen=True)

    metadata: PaperMetadata
    goal: AnalysisGoal
    resources: AnalysisResources = Field(default_factory=AnalysisResources)
    method: AnalysisMethod = Field(default_factory=AnalysisMethod)
    evaluation: AnalysisEvaluation = Field(default_factory=AnalysisEvaluation)
    reproduction_gaps: list[ReproductionGap] = Field(default_factory=list)
    schema_version: str = SCHEMA_VERSION
