Here is a comprehensive architecture and implementation specification document designed to act as a prompt for an AI agent (or a senior developer) to build the "LLM-as-a-Judge" evaluation feature within Langbuilder.

---

# Feature Specification: Automated Dataset Evaluation & LLM-as-a-Judge

**Target Application:** Langbuilder (Python 3.12 Backend / React TSX Frontend)
**Integration:** Langfuse SDK (Self-Hosted/Cloud)
**Goal:** Implement a full-stack feature to create datasets, define expected outputs, and run batch experiments using "LLM-as-a-judge" evaluators (Correctness, Helpfulness, etc.) to score application performance.

---

## 1. High-Level Architecture

### Concept

The user will interact solely with the **Langbuilder UI** to manage datasets and trigger evaluations. The **Langbuilder Backend** will act as the orchestrator. It will push data to **Langfuse** (for observability and persistence) and execute the evaluation logic locally (or trigger it) to provide immediate feedback in the Langbuilder UI.

### Data Flow

1. **Dataset Creation:** User inputs data (Input/Expected Output) in Langbuilder UI  Backend saves to Local DB & Syncs to Langfuse via `langfuse.create_dataset()`.
2. **Experiment Execution:** User selects a Dataset and a set of Evaluators (e.g., "Correctness")  Backend iterates through dataset items.
3. **Inference:** Backend runs the specific Langbuilder chain/agent logic for each item.
4. **Judging:** Backend passes the `(Input, Generated Output, Expected Output)` tuple to a `JudgeService`.
5. **Scoring:** The `JudgeService` uses an LLM (e.g., GPT-4o/Gemini) to generate a score and reasoning based on the selected metric.
6. **Telemetry:** Backend pushes the trace and the generated score to Langfuse using the SDK.
7. **Reporting:** Frontend polls/receives the aggregated results and displays a comparison table with scores.

---

## 2. Backend Specification (Python 3.12)

### 2.1. Database Schema (SQLAlchemy / Pydantic Models)

*Although Langfuse holds the data, we need local references to manage the UI state efficiently.*

```python
# Conceptual Models

class DatasetMetadata(Base):
    __tablename__ = "dataset_metadata"
    id = Column(String, primary_key=True) # Matches Langfuse Dataset Name
    description = Column(String)
    created_at = Column(DateTime)

class EvaluationConfig(Base):
    """Stores the user's preference for a specific run"""
    id = Column(Integer, primary_key=True)
    dataset_name = Column(String, ForeignKey("dataset_metadata.id"))
    selected_metrics = Column(JSON) # e.g., ["correctness", "conciseness"]
    model_params = Column(JSON) # Parameters used for the generation

```

### 2.2. Langfuse Service Integration (`services/langfuse_service.py`)

This service wraps the SDK to ensure consistency.

* **Create Dataset:**
```python
def create_dataset_sync(name: str, items: List[Dict]):
    # 1. Create in Langfuse
    langfuse.create_dataset(name=name)
    # 2. Add Items
    for item in items:
        langfuse.create_dataset_item(
            dataset_name=name,
            input=item['input'],
            expected_output=item['expected_output'],
            metadata=item.get('metadata')
        )

```



### 2.3. The Judge Logic (`services/evaluators.py`)

Implement the "LLM-as-a-judge" logic locally to ensure Langbuilder controls the scoring process.

* **Evaluator Interface:**
Each metric (Correctness, Helpfulness) must implement a standard `evaluate` method.
* **Prompt Template (Example for Correctness):**
```text
You are an expert evaluator.
Input: {input}
Expected Output: {expected_output}
Actual Output: {actual_output}

Analyze the Actual Output against the Expected Output.
Return a JSON with:
1. score: (0 to 1)
2. reason: (Short explanation)

```


* **Factory Pattern:**
Create a factory to instantiate evaluators based on the UI selection (similar to the reference image).

### 2.4. API Endpoints (`routes/evaluation.py`)

* `GET /api/datasets`: List all available datasets.
* `POST /api/datasets`: Create a new dataset or append items.
* `POST /api/experiments/run`:
* **Payload:** `{ dataset_id: str, evaluators: List[str], target_chain_id: str }`
* **Action:** Triggers a background task (Celery/AsyncIO).
* **Logic:**
1. Fetch dataset items from Langfuse SDK (`langfuse.get_dataset(id)`).
2. For each item:
* Run the `target_chain_id` with `item.input`.
* Capture `trace_id` from the run.
* Run the selected `Evaluators` (e.g., Correctness).
* Send Score to Langfuse: `langfuse.score(trace_id=..., name="correctness", value=0.9, comment="...")`.






* `GET /api/experiments/{run_id}/results`: Returns the status and aggregated scores of a run.

---

## 3. Frontend Specification (React / TSX)

### 3.1. UI Components

#### A. Dataset Management Page (`/datasets`)

* **Layout:** Split view. List of datasets on the left, details on the right.
* **Components:**
* `DatasetList`: Sidebar list.
* `ItemEditor`: A form to add/edit `Input` (JSON editor), `Expected Output` (JSON editor), and `Metadata`.
* `ImportButton`: Ability to upload a JSON/CSV to bulk create items.



#### B. Experiment Setup Modal (The "Set up evaluator" view)

* *Reference the uploaded image for styling.*
* **Stepper:**
1. **Select Evaluator:** A checklist of metrics (Conciseness, Correctness, Hallucination). Use the "knot" icon 🪢 for Langfuse managed references.
2. **Configure Config:** Select which "Chain" or "Prompt" version to test.
3. **Run:** A generic "Start Experiment" button.



#### C. Experiment Results View

* **Table Columns:**
1. **Input:** Truncated view of the prompt.
2. **Expected:** What was defined in the dataset.
3. **Generated:** What the model produced.
4. **Scores:** A column for each metric (e.g., Correctness).
* *Visual:* Color-coded badges (Green > 0.8, Red < 0.5).
* *Interaction:* Hovering over a score shows the "Reasoning" generated by the Judge LLM.





### 3.2. State Management (Hooks)

* `useDatasets()`: Fetch list of datasets.
* `useExperimentRunner()`: specialized hook to handle the long-polling of the experiment status.
* States: `idle` | `running` (with progress bar %) | `completed` | `error`.



---

## 4. Implementation Steps (Agent Instructions)

**Phase 1: Foundation**

1. Initialize `langfuse` client in the Python backend using environment variables.
2. Create the `Evaluator` abstract base class and implement two concrete judges: `CorrectnessEvaluator` and `ConcisenessEvaluator` using a standard LLM client (e.g., OpenAI/Gemini) for the judging logic.

**Phase 2: Dataset Management**

1. Build the `POST /api/datasets` endpoint.
2. Create the Frontend "Dataset Manager" page to allow users to create a dataset and add 5 sample items manually.

**Phase 3: Experiment Runner**

1. Implement the `run_experiment` background task. This is the core loop:
```python
# Pseudo-code for the loop
dataset = langfuse.get_dataset(name)
for item in dataset.items:
    # 1. Execute Application Logic
    generation, trace = app.invoke(item.input)

    # 2. Evaluate
    for metric in selected_metrics:
        score, reason = metric.evaluate(item.input, item.expected_output, generation)

        # 3. Log to Langfuse
        trace.score(name=metric.name, value=score, comment=reason)

```



**Phase 4: UI Visualization**

1. Build the "Select Evaluator" component (matching the provided image).
2. Build the Results Table to display the data fetched from the completed experiment.

---

## 5. Development Constraints & Guidelines

* **Langfuse SDK Usage:** Do NOT create custom SQL tables for storing dataset items. Use `langfuse.get_dataset(name)` as the source of truth to ensure the Langfuse UI and Langbuilder UI are always in sync.
* **Asynchronous Processing:** Experiment runs can be slow. Ensure the API endpoint starts a background task and returns a `run_id` immediately. The Frontend should poll for progress.
* **Judge Prompts:** Store the prompts used for "Judging" in the codebase as constants or distinct prompt files so they can be versioned.
* **Type Safety:** Use Pydantic models for all API Request/Response bodies.