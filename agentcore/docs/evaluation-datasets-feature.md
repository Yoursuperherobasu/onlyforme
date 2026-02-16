# Evaluation Datasets Feature

Last updated: February 16, 2026

## Overview
This document describes the Dataset feature that was implemented in the Evaluation module, including:

- what was changed in backend and frontend
- API contracts
- how to use it from the UI
- operational notes and limitations

The feature enables users to:

- create and manage Langfuse datasets
- add dataset items manually or from production traces
- run experiments against those datasets
- optionally evaluate experiment outputs with exact match and/or LLM-as-a-judge criteria

## What Was Implemented

### Backend changes
File: `src/backend/base/agentcore/api/evaluation.py`

#### 1. New request/response models
Added new models for dataset APIs and experiment jobs:

- `DatasetResponse`
- `CreateDatasetRequest`
- `DatasetItemResponse`
- `CreateDatasetItemRequest`
- `DatasetRunResponse`
- `RunDatasetExperimentRequest`
- `DatasetExperimentEnqueueResponse`
- `DatasetExperimentJobResponse`

#### 2. New helper utilities
Added helper functions to support SDK compatibility and robust parsing across Langfuse response variants:

- pagination/response parsing (`_parse_paginated_response`)
- metadata normalization and ownership checks (`_merge_dataset_metadata`, `_dataset_owned_by_user`)
- serializers for dataset/dataset item/run payloads
- background in-memory experiment job state store and serializer
- flow execution helpers for experiment tasks
- output extraction helpers from `simple_run_agent` responses
- LLM evaluator helper for dataset experiment item grading

#### 3. New dataset endpoints
Added these endpoints under `/api/evaluation`:

- `GET /datasets`
  - list datasets for current user
- `POST /datasets`
  - create dataset
- `GET /datasets/{dataset_name}/items`
  - list dataset items
- `POST /datasets/{dataset_name}/items`
  - add dataset item (manual or from trace)
- `GET /datasets/{dataset_name}/runs`
  - list dataset runs/experiments
- `GET /datasets/{dataset_name}/runs/{run_id}`
  - fetch run detail including run items, linked trace snapshot, and score snapshot
- `POST /datasets/{dataset_name}/experiments`
  - queue experiment run in background
- `GET /datasets/experiments/{job_id}`
  - fetch background job status/result

#### 4. Experiment execution behavior
Experiments are executed via `Langfuse.run_experiment(...)`.

Task mode behavior:

- If `agent_id` is provided:
  - each dataset item input is executed against the selected flow using `simple_run_agent`.
- If `agent_id` is not provided:
  - fallback output is the dataset item input (explicit fallback mode).

Evaluators during experiment:

- `exact_match` evaluator (when expected output exists)
- optional LLM evaluator when criteria/model are provided (or selected via evaluator config)

#### 5. Job lifecycle
Experiment jobs are queued and tracked in process memory:

- statuses: `queued`, `running`, `completed`, `failed`
- stores run/result payload and errors for UI polling

Note:

- this in-memory job state resets when backend restarts

### Frontend changes

#### 1. Evaluation API client updates
File: `src/frontend/src/controllers/API/evaluation.ts`

Added dataset types and API functions:

- dataset list/create
- dataset item list/create
- dataset runs list
- experiment run enqueue
- experiment job status fetch

#### 2. Evaluation page UI updates
File: `src/frontend/src/pages/EvaluationPage/index.tsx`

Added new tab:

- `Datasets` (after `LLM Judges`)

Added UI sections:

- why datasets intro
- dataset management (select + create)
- dataset items table and add item form
- experiment form (name, run name, agent, evaluator, criteria/model, concurrency)
- run history table
- clickable run rows with detail modal
- latest background job status display with polling

## Data Storage and Ownership

### Where data is stored

- datasets, dataset items, dataset runs, and experiment traces/scores are stored in Langfuse
- background job tracking state is stored temporarily in the backend process memory only

### User scoping
Dataset ownership is enforced with metadata-based scoping:

- `app_user_id`
- `created_by_user_id`

When creating datasets/items, metadata is augmented with these fields.

## How To Use (UI Guide)

1. Open `Evaluation` page.
2. Click the `Datasets` tab.
3. Create a dataset:
   - provide `New Dataset Name`
   - optional description
   - click `Create Dataset`
4. Add dataset items:
   - manual:
     - enter `Input` and optional `Expected Output` (text or JSON)
     - click `Add Dataset Item`
   - from trace:
     - choose `Add From Existing Trace`
     - optionally set source trace id
     - click `Add Dataset Item`
5. Run experiment:
   - set `Experiment Name`
   - optional `Run Name`, `Description`
   - optional `Agent (Flow)` for real execution
   - optional evaluator selection and/or criteria/model
   - set `Max Concurrency`
   - click `Run Experiment`
6. Monitor status:
   - latest background job state appears in UI
   - run history refreshes after completion
   - click a run row or `View` to open run details (run items, trace IO, and scores)

## API Usage Examples

Base URL examples assume local app:

- backend: `http://localhost:7860`
- frontend proxy route: `/api/...`

### Create dataset
`POST /api/evaluation/datasets`

```json
{
  "name": "support-faq-v1",
  "description": "Support Q&A regression set"
}
```

### Add item manually
`POST /api/evaluation/datasets/support-faq-v1/items`

```json
{
  "input": {"question": "What is your refund policy?"},
  "expected_output": "You can request a refund within 30 days."
}
```

### Add item from trace
`POST /api/evaluation/datasets/support-faq-v1/items`

```json
{
  "trace_id": "3e0a5a6049aa1d45c2238b2b65e30ce7",
  "use_trace_output_as_expected": true
}
```

### Run experiment
`POST /api/evaluation/datasets/support-faq-v1/experiments`

```json
{
  "experiment_name": "Support Agent Regression",
  "run_name": "support-agent-v2-2026-02-16",
  "agent_id": "2f749947-55b8-4653-aaea-0c792cd166a3",
  "max_concurrency": 10,
  "criteria": "Evaluate helpfulness and factual correctness",
  "model": "gpt-4o"
}
```

### Poll experiment job status
`GET /api/evaluation/datasets/experiments/{job_id}`

## Operational Notes

- Langfuse environment must be configured:
  - `LANGFUSE_SECRET_KEY`
  - `LANGFUSE_PUBLIC_KEY`
  - `LANGFUSE_BASE_URL` or `LANGFUSE_HOST`
- For LLM evaluator in experiments:
  - ensure provider model/API key is configured
- Background job state is ephemeral:
  - if backend restarts, queued/running/completed memory state is lost
  - Langfuse dataset runs remain persisted

## Known Limitations

- Job tracking is in-memory and not persisted to application DB.
- If no `agent_id` is selected, experiment uses fallback mode (`output = input`).
- Current project-wide frontend typecheck has unrelated existing errors outside this feature area.

## Recommended Next Enhancements

- persist experiment job state in application DB
- add dataset item edit/delete UI
- add dataset run detail UI (run items, linked traces, score breakdown)
- add cancellation support for queued/running experiment jobs
