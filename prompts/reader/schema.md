Return a single JSON object matching `PaperReproductionAnalysis` schema version `1.0`.

## Top-level shape

```json
{
  "schema_version": "1.0",
  "metadata": { ... },
  "goal": { ... },
  "resources": { ... },
  "method": { ... },
  "evaluation": { ... },
  "reproduction_gaps": [ ... ]
}
```

## metadata

| Field | Type | Required |
|-------|------|----------|
| title | string | yes |
| authors | string[] | no |
| venue | string | no |
| year | integer | no |
| arxiv_id | string | no |

## goal

| Field | Type | Required |
|-------|------|----------|
| scope | string enum | yes |
| research_goal | string | yes |
| target_experiment | string | no |
| expected_outcome | string | no |

`scope` enum: `full_reproduction`, `training`, `inference`, `evaluation`, `ablation`, `benchmark`, `unknown`

## resources

| Field | Type |
|-------|------|
| datasets | `{name, description?, link?, split_or_variant?}[]` |
| models | `{name, description?, role?}[]` |
| dependencies | `{name, version?, purpose?}[]` |
| external_resources | `{resource_type, name, url?, notes?}[]` |
| artifacts | `{artifact_type, name, location?, notes?}[]` |

`artifact_type` enum: `checkpoint`, `pretrained_weight`, `tokenizer`, `vocabulary`, `config`, `calibration`, `other`

## method

| Field | Type |
|-------|------|
| framework | string |
| architecture | string |
| training_pipeline | string |
| optimizer | string |
| loss | string |
| hyperparameters | `{name, value?, notes?}[]` |
| data_processing | string |

## evaluation

| Field | Type |
|-------|------|
| metrics | `{name, definition?, reported_value?}[]` |
| benchmarks | string[] |
| evaluation_protocol | string |
| baselines | `{name, description?}[]` |

## reproduction_gaps

`{category, description}[]`

`category` enum: `hyperparameter`, `repository`, `dataset_link`, `config`, `checkpoint`, `evaluation_detail`, `implementation_detail`, `other`

Use empty strings and empty arrays for absent optional content. `metadata.title` and `goal.research_goal` are the only required content fields.
