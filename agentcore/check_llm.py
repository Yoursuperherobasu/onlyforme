import httpx

BASE = "http://localhost:8001"
HEADERS = {"x-api-key": "agentcore-llm-svc-key-001"}

# Step 1: List models
models = httpx.get(f"{BASE}/v1/registry/models", headers=HEADERS).json()
llm_id = "c55b73f0-4e77-4801-86b9-3e7a7a5d082a"  # pick your model

# Step 2: Chat
resp = httpx.post(f"{BASE}/v1/chat/completions", headers=HEADERS, json={
    "provider": "groq",
    "model": "llama-3.1-8b-instant",
    "messages": [{"role": "user", "content": "What is Python?"}],
    "provider_config": {"registry_model_id": llm_id},
})
print(resp.json()["choices"][0]["message"]["content"])
