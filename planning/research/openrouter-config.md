# Research: OpenRouter for Eval Framework

## LiteLLM Integration

OpenRouter works natively with LiteLLM. Configuration:
```python
import litellm
response = litellm.completion(
    model="openrouter/anthropic/claude-opus-4-5",
    messages=[...],
    api_key=os.environ["OPENROUTER_API_KEY"],
)
```

LiteLLM prefix: `openrouter/<provider>/<model>`

## Key Models for Evaluation

### Frontier (high-quality, expensive)
| Model | Input/1M tokens | Output/1M tokens | Context |
|-------|----------------|-------------------|---------|
| Claude Opus 4.5 | $5.00 | $25.00 | 200K |
| GPT-5.2 Pro | $21.00 | $168.00 | 400K |
| Gemini 3 Pro | $2.00 | $12.00 | 1M |

### Mid-tier (good balance)
| Model | Input/1M tokens | Output/1M tokens | Context |
|-------|----------------|-------------------|---------|
| GPT-5.1 | $1.25 | $10.00 | 400K |
| GPT-5.2 | $1.75 | $14.00 | 400K |
| Mistral Large 3 | $0.50 | $1.50 | 262K |
| DeepSeek V3.2 | $0.25 | $0.38 | 163K |

### Small/Cheap (fast iteration)
| Model | Input/1M tokens | Output/1M tokens | Context |
|-------|----------------|-------------------|---------|
| Ministral 3 8B | $0.15 | $0.15 | 262K |
| Ministral 3 3B | $0.10 | $0.10 | 131K |
| Devstral 2 | $0.05 | $0.22 | 262K |

### Free models
- openrouter/free (auto-selects)
- Multiple community models with free tiers

## Provider Routing for Evals

Critical for reproducibility:
```python
# Pin to a specific provider
extra_body = {
    "provider": {
        "order": ["anthropic"],
        "allow_fallbacks": False,
        "require_parameters": True
    }
}
```

- `order` + `allow_fallbacks: false` = guaranteed single-provider routing
- `require_parameters: true` = ensures all params (temperature, seed) are supported
- `:nitro` suffix = optimized for throughput
- `:floor` suffix = optimized for cost

## Generation Metadata

GET `/generation` endpoint returns:
- Provider name, model used, total latency (ms)
- Token counts (prompt, completion, cached, reasoning)
- Cost in USD
- Finish reason
- Provider response chain (for fallback tracking)

This is excellent for our eval framework: we can track actual provider, latency, and cost per call.

## Privacy

Zero logging by default. Opt-in logging gives 1% discount.
Can filter providers by data collection policy: `data_collection: "deny"`

## Recommendations for Our Framework

1. Use OpenRouter as PRIMARY provider via LiteLLM (one API key, all models)
2. Pin providers with `order` + `allow_fallbacks: false` for reproducibility
3. Use generation metadata to track actual provider/model/cost per eval call
4. Test across tiers: 1 frontier + 1 mid-tier + 1 small per axis minimum
5. Use `data_collection: "deny"` for eval workloads
6. Cost estimation: calculate based on token counts, not API calls
