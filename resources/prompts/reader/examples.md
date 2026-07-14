## Example (illustrative structure only — do not copy values into your output)

Paper excerpt (abbreviated):

> We train ResNet-50 on ImageNet using SGD with batch size 256. Top-1 accuracy is reported in Table 1. Code will be released.

Expected extraction pattern:

```json
{
  "schema_version": "1.0",
  "metadata": {
    "title": "Deep Residual Learning for Image Recognition",
    "authors": ["Kaiming He"],
    "venue": "",
    "year": null,
    "arxiv_id": ""
  },
  "goal": {
    "scope": "training",
    "research_goal": "Train very deep residual networks for image classification.",
    "target_experiment": "ResNet-50 training on ImageNet",
    "expected_outcome": "Match top-1 accuracy in Table 1"
  },
  "resources": {
    "datasets": [
      {
        "name": "ImageNet",
        "description": "Image classification dataset used for training",
        "link": "",
        "split_or_variant": ""
      }
    ],
    "models": [
      {
        "name": "ResNet-50",
        "description": "50-layer residual network",
        "role": "primary model"
      }
    ],
    "dependencies": [],
    "external_resources": [],
    "artifacts": []
  },
  "method": {
    "framework": "",
    "architecture": "Residual blocks with shortcut connections",
    "training_pipeline": "Train ResNet-50 on ImageNet",
    "optimizer": "SGD",
    "loss": "",
    "hyperparameters": [
      {"name": "batch_size", "value": "256", "notes": ""}
    ],
    "data_processing": ""
  },
  "evaluation": {
    "metrics": [
      {
        "name": "top-1 accuracy",
        "definition": "",
        "reported_value": "see Table 1"
      }
    ],
    "benchmarks": ["ImageNet"],
    "evaluation_protocol": "",
    "baselines": []
  },
  "reproduction_gaps": [
    {
      "category": "repository",
      "description": "Paper states code will be released but provides no repository URL."
    },
    {
      "category": "hyperparameter",
      "description": "Learning rate and training epochs are not specified in the provided excerpt."
    }
  ]
}
```

Note: `"Code will be released"` without a URL → `reproduction_gaps`, not `external_resources`.
