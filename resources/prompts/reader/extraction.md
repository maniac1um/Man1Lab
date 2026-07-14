Extract a `PaperReproductionAnalysis` JSON object from the provided paper text.

Work through the five reproduction modules in order:

## 1. Goal — What must be reproduced?

Extract:
- `scope` — primary reproducible unit (`full_reproduction`, `training`, `inference`, `evaluation`, `ablation`, `benchmark`, or `unknown`)
- `research_goal` — the problem and contribution the paper aims to reproduce
- `target_experiment` — the specific experiment, table, or figure to reproduce
- `expected_outcome` — what success looks like for that experiment

Do not write a generic abstract. State reproduction intent only.

## 2. Resources — What must be prepared?

Extract only resources **explicitly mentioned** in the paper:

- `datasets` — name, description, link (only if paper gives URL/DOI), split/variant
- `models` — model or architecture names, description, role
- `dependencies` — libraries, runtimes, hardware/software named in the paper
- `external_resources` — paper-cited links (code repo, dataset portal, project page)
- `artifacts` — checkpoints, weights, tokenizers, vocabularies, configs, calibration files named in the paper

Do not search for links. Do not add resources from prior knowledge.

## 3. Method — How did the authors run the experiment?

Extract engineering information only:

- `architecture` — structural / implementation description (layers, blocks, inputs, outputs)
- `framework` — e.g. PyTorch, TensorFlow, JAX, Caffe
- `training_pipeline` — training or experimental procedure steps stated in the paper
- `optimizer` — optimizer name
- `loss` — loss function
- `hyperparameters` — only parameters with names/values stated in the paper
- `data_processing` — preprocessing, augmentation, normalization

Do not narrate the algorithm at a survey level. Extract implementable method details only.

## 4. Evaluation — How is success measured?

Extract:
- `metrics` — name, definition, reported value (only if paper reports it)
- `benchmarks` — benchmark or task names
- `evaluation_protocol` — evaluation procedure stated in the paper
- `baselines` — comparison methods named in the paper

Do not add standard metrics the paper does not mention.

## 5. Reproduction Gaps — What is missing?

For each missing reproduction-critical item, add:

```json
{"category": "<gap_category>", "description": "<factual statement of what is absent>"}
```

Valid `category` values: `hyperparameter`, `repository`, `dataset_link`, `config`, `checkpoint`, `evaluation_detail`, `implementation_detail`, `other`.

Record absence only. Do not suggest fixes. Do not infer values.
