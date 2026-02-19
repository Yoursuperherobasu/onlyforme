Below is a **ready-to-use `.md` file** you can directly place in your repo (example: `/docs/evaluation_architecture.md`) or feed to an agent.

This is written as an **AGENT PROMPT DOCUMENT** so that a coding agent can read it and generate full backend + frontend implementation inside **Langbuilder** using **Langfuse SDK**.

---

# 📄 `evaluation_with_langfuse_architecture.md`

## 🎯 OBJECTIVE

Build a **Dataset + Evaluation + Experiment system** inside **Langbuilder UI & backend** using **Langfuse SDK**, where:

* Users create datasets
* Add dataset items:

  * input
  * expected output
  * metadata (optional)
* Run experiments on datasets
* Use **LLM-as-a-judge evaluators** (correctness, helpfulness, hallucination etc.)
* Generate evaluation scores
* Show results inside **Langbuilder UI**
* All evaluations should also reflect in **Langfuse**

Langbuilder is the **main UI & backend**
Langfuse runs separately and acts as **evaluation + observability engine**

---

# 🧠 HIGH LEVEL ARCHITECTURE

```
User (Langbuilder UI)
   ↓
Langbuilder Frontend (React TSX)
   ↓
Langbuilder Backend (Python 3.12 FastAPI)
   ↓
Evaluation Service Layer
   ↓
Langfuse SDK
   ↓
Langfuse Server (existing)
   ↓
LLM Judge + Evaluation Engine
```

Langbuilder = primary user interface
Langfuse = evaluation engine + storage + scoring

---

# 📦 CORE FEATURES TO IMPLEMENT

### 1. Dataset Management

* Create dataset
* Add dataset items
* Update/delete dataset items
* Sync dataset to Langfuse

### 2. Experiment Runner

* Select dataset
* Select model/prompt
* Run experiment
* Generate outputs
* Send to Langfuse

### 3. LLM-as-Judge Evaluation

Evaluate generated output vs expected output

Metrics:

* correctness
* helpfulness
* relevance
* conciseness
* hallucination
* toxicity
* faithfulness
* context precision
* context recall
* answer correctness
* goal accuracy
* custom metrics

### 4. Results UI

* Dataset run history
* Score per item
* Average score
* Trace view (Langfuse)
* Comparison runs

---

# 🗄️ DATABASE DESIGN (Langbuilder DB)

Create internal DB tables to map Langfuse resources.

## Table: datasets

```
id (uuid)
name
description
created_by
created_at
langfuse_dataset_id
```

## Table: dataset_items

```
id (uuid)
dataset_id (fk)
input_text
expected_output
metadata_json (nullable)
langfuse_dataset_item_id
created_at
```

## Table: experiments

```
id (uuid)
dataset_id
name
model_name
status (pending/running/completed)
langfuse_experiment_id
created_at
```

## Table: experiment_runs

```
id
experiment_id
dataset_item_id
input
generated_output
expected_output
trace_id (langfuse)
run_status
created_at
```

## Table: evaluation_scores

```
id
experiment_run_id
metric_name
score
reason
created_at
```

---

# 🔌 LANGFUSE SDK INTEGRATION

Install:

```
pip install langfuse
```

Initialize:

```python
from langfuse import Langfuse

langfuse = Langfuse(
    public_key=ENV.PUBLIC_KEY,
    secret_key=ENV.SECRET_KEY,
    host=ENV.LANGFUSE_HOST
)
```

---

# 📚 DATASET CREATION FLOW

## Step 1: Create dataset in Langbuilder UI

User enters:

* dataset name
* description

Backend:

```python
dataset = langfuse.create_dataset(
    name="Support QA dataset",
    description="Evaluation dataset"
)
```

Store returned:

```
langfuse_dataset_id
```

Save in local DB.

---

# 📥 DATASET ITEM CREATION FLOW

Each dataset item:

```
input
expected_output
metadata (optional)
```

Backend:

```python
langfuse.create_dataset_item(
    dataset_name=dataset_name,
    input={"text": input_text},
    expected_output={"text": expected_output},
    metadata=metadata
)
```

Store:

```
langfuse_dataset_item_id
```

---

# 🧪 EXPERIMENT RUN FLOW

## User Flow

User selects:

* dataset
* model
* prompt template
* evaluators (checkbox list)

Then clicks:

```
Run Experiment
```

---

# ⚙️ BACKEND EXPERIMENT PIPELINE

## Step 1: Create experiment record

Create in DB + Langfuse

```python
experiment = langfuse.create_experiment(
    name="gpt4_eval_run",
    dataset_name="support_dataset"
)
```

Store:

```
langfuse_experiment_id
```

---

## Step 2: For each dataset item

Loop through dataset items:

### Generate output

```python
response = llm.generate(input_text)
```

### Create trace in Langfuse

```python
trace = langfuse.trace(
    name="dataset-run",
    input=input_text,
    output=response
)
```

Store trace_id.

---

# 🤖 LLM-AS-JUDGE EVALUATION FLOW

Use Langfuse managed evaluators (from image reference):

Metrics:

* correctness
* helpfulness
* relevance
* conciseness
* hallucination
* toxicity
* context correctness
* faithfulness
* etc.

---

## Step 3: Run evaluator

Example:

```python
langfuse.score(
    trace_id=trace.id,
    name="correctness",
    value=0.9,
    comment="Output matches expected"
)
```

OR use evaluator pipeline:

```python
langfuse.run_evaluator(
    trace_id=trace.id,
    evaluator="correctness",
    expected_output=expected_output
)
```

Repeat for all metrics selected.

---

# 📊 SCORING LOGIC

Each dataset item:

```
input
expected_output
generated_output
```

LLM judge compares:

```
expected_output vs generated_output
```

Produces:

```
score (0-1)
reason
```

Store in:

```
evaluation_scores table
```

---

# 📈 AGGREGATED METRICS

After experiment completes:

Calculate:

```
avg_correctness
avg_helpfulness
avg_relevance
avg_hallucination
overall_score
```

Store in experiment table.

---

# 🧑‍💻 FRONTEND (REACT TSX)

## Pages to Build

### 1. Dataset Page

```
/datasets
```

Features:

* create dataset
* upload JSON/CSV
* add dataset items
* view dataset items

### 2. Experiment Page

```
/experiments
```

Features:

* select dataset
* select model
* select evaluators
* run experiment

Evaluator list UI:

* correctness
* helpfulness
* hallucination
* relevance
* toxicity
* faithfulness
* context precision
* context recall
* goal accuracy

### 3. Results Page

```
/experiments/{id}
```

Show:

* table of dataset items
* generated output
* expected output
* metric scores
* average score
* trace link

---

# 🔗 BACKEND API ROUTES

## Dataset APIs

```
POST   /api/datasets/create
GET    /api/datasets
POST   /api/datasets/{id}/item
GET    /api/datasets/{id}/items
DELETE /api/datasets/{id}
```

## Experiment APIs

```
POST /api/experiments/run
GET  /api/experiments
GET  /api/experiments/{id}
GET  /api/experiments/{id}/results
```

---

# 🧵 BACKGROUND WORKER (IMPORTANT)

Experiment runs must be async.

Use:

* Celery OR
* FastAPI background tasks OR
* Redis queue

Pipeline:

```
Start experiment
 → queue job
 → process dataset items
 → generate output
 → send to langfuse
 → run evaluators
 → store scores
 → mark complete
```

---

# 📊 UI SCORE DISPLAY

For each dataset item show:

| Input | Expected | Generated | Correctness | Helpfulness | Hallucination |
| ----- | -------- | --------- | ----------- | ----------- | ------------- |

Top summary:

```
Overall score: 0.82
Correctness: 0.91
Helpfulness: 0.88
Hallucination: 0.07
```

---

# 🔐 ENV VARIABLES

```
LANGFUSE_PUBLIC_KEY=
LANGFUSE_SECRET_KEY=
LANGFUSE_HOST=http://localhost:3000
OPENAI_API_KEY=
```

---

# 🧠 AGENT IMPLEMENTATION INSTRUCTIONS

You are an engineering agent.

Your task:
Implement full feature inside Langbuilder.

You must generate:

### Backend

* FastAPI routes
* DB models
* Langfuse service layer
* experiment runner
* evaluator runner
* async worker

### Frontend

* dataset UI
* experiment UI
* evaluator selection UI
* results dashboard
* score charts

### Integration

* connect backend to Langfuse SDK
* sync datasets
* sync traces
* sync scores

### Ensure

* everything visible in Langbuilder UI
* everything also visible in Langfuse UI

---

# 🚀 END GOAL

User workflow inside Langbuilder:

```
Create Dataset → Add Items → Run Experiment → Select Evaluators → View Scores
```

Behind the scenes:

```
Langbuilder → Langfuse SDK → Langfuse → LLM Judge → Scores → Back to Langbuilder UI
```

---

# ⭐ PRIORITY ORDER FOR IMPLEMENTATION

1. Langfuse SDK service layer
2. Dataset APIs
3. Experiment runner
4. Evaluator pipeline
5. Results storage
6. Frontend dataset UI
7. Frontend experiment UI
8. Results dashboard

---

# 🏁 FINAL OUTPUT REQUIREMENT

Agent must generate:

* complete backend code
* complete frontend code
* DB migrations
* services
* hooks
* API routes
* evaluation pipeline
* Langfuse integration

All production ready.

---
