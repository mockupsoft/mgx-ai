# Multi-Provider LLM System

## Overview

The Multi-Provider LLM system provides a unified interface to multiple Large Language Model providers with intelligent routing, automatic fallback, and cost optimization.

## Features

- **Multiple Providers**: OpenAI, Anthropic (Claude), Mistral, Ollama (local), Together AI
- **Intelligent Routing**: Cost, latency, quality, and capability-based provider selection
- **Automatic Fallback**: Seamless failover to alternative providers on error
- **Cost Tracking**: Integrated with cost tracking system for budget management
- **Local Models**: Support for offline, privacy-focused local models via Ollama
- **Streaming**: Stream generation support for real-time responses

## Supported Providers

### OpenAI
- **Models**: GPT-4, GPT-4 Turbo, GPT-3.5 Turbo
- **Capabilities**: Code generation, reasoning, analysis, function calling
- **Cost**: $0.0005-$0.06 per 1K tokens
- **Latency**: 500-1500ms
- **Setup**: Requires `OPENAI_API_KEY`

### Anthropic (Claude)
- **Models**: Claude 3 Opus, Claude 3 Sonnet, Claude 3 Haiku
- **Capabilities**: Code, reasoning, analysis, long context (200K tokens)
- **Cost**: $0.00025-$0.075 per 1K tokens
- **Latency**: 500-1500ms
- **Setup**: Requires `ANTHROPIC_API_KEY`

### Mistral AI
- **Models**: Mistral Large, Medium, Small, Tiny
- **Capabilities**: Code generation, analysis, multilingual
- **Cost**: $0.00025-$0.024 per 1K tokens
- **Latency**: 600-1200ms
- **Setup**: Requires `MISTRAL_API_KEY`

### Ollama (Local)
- **Models**: Llama 2, Mistral, CodeLlama
- **Capabilities**: Code generation, analysis, offline operation
- **Cost**: Free (local execution)
- **Latency**: 4000-15000ms (depends on hardware)
- **Setup**: Requires Ollama server running on `http://localhost:11434`

### Together AI
- **Models**: Mistral, Llama 2, CodeLlama
- **Capabilities**: Code generation, analysis
- **Cost**: $0.0002-$0.0009 per 1K tokens
- **Latency**: 1500-2500ms
- **Setup**: Requires `TOGETHER_API_KEY`

## Configuration

### Environment Variables

```bash
# LLM Provider Settings
LLM_DEFAULT_PROVIDER=openai
LLM_ROUTING_STRATEGY=balanced
LLM_ENABLE_FALLBACK=true
LLM_PREFER_LOCAL=false
LLM_MAX_LATENCY_MS=10000

# Provider API Keys
OPENAI_API_KEY=sk-...
OPENAI_ORGANIZATION=org-...
ANTHROPIC_API_KEY=sk-ant-...
MISTRAL_API_KEY=...
TOGETHER_API_KEY=...
OLLAMA_BASE_URL=http://localhost:11434
```

### Routing Strategies

- **`balanced`**: Balance cost, quality, and latency (default)
- **`cost_optimized`**: Select cheapest available model
- **`latency_optimized`**: Select fastest available model
- **`quality_optimized`**: Select highest quality model
- **`local_first`**: Prefer local models when available
- **`capability_match`**: Match models by required capability

## Usage

### Basic Generation

```python
from backend.services.llm.llm_service import get_llm_service

# Get service instance
llm_service = get_llm_service(db_session)

# Generate text
response = await llm_service.generate(
    prompt="Write a Python function to calculate fibonacci numbers",
    workspace_id="workspace-123",
    execution_id="exec-456",
    temperature=0.7,
    max_tokens=1000,
)

print(response.content)
print(f"Cost: ${response.cost_usd:.4f}")
print(f"Latency: {response.latency_ms}ms")
```

### Specific Provider/Model

```python
# Use specific provider and model
response = await llm_service.generate(
    prompt="Explain quantum computing",
    provider="anthropic",
    model="claude-3-opus",
    temperature=0.7,
)
```

### Task-Specific Generation

```python
# Code generation (optimized for code capability)
response = await llm_service.generate(
    prompt="Write a REST API endpoint",
    task_type="code_generation",
    required_capability="code",
    temperature=0.5,
)

# Analysis (optimized for reasoning)
response = await llm_service.generate(
    prompt="Analyze this architecture",
    task_type="analysis",
    required_capability="reasoning",
)
```

### Budget-Constrained Generation

```python
# Stay within budget
response = await llm_service.generate(
    prompt="Summarize this document",
    budget_remaining=0.50,  # $0.50 remaining
    task_type="analysis",
)
```

### Streaming Generation

```python
# Stream responses in real-time
async for chunk in llm_service.stream_generate(
    prompt="Write a long story",
    provider="openai",
    model="gpt-3.5-turbo",
):
    print(chunk, end="", flush=True)
```

### Fallback Chain

```python
# Enable automatic fallback
response = await llm_service.generate(
    prompt="Generate code",
    enable_fallback=True,  # Automatically try alternatives on failure
)
```

## Fallback Chains

### Predefined Chains

```python
from backend.services.llm.router import FallbackChain

# High Quality
FallbackChain.HIGH_QUALITY = [
    ("openai", "gpt-4"),
    ("anthropic", "claude-3-opus"),
    ("mistral", "mistral-large"),
]

# Cost Optimized
FallbackChain.COST_OPTIMIZED = [
    ("openai", "gpt-3.5-turbo"),
    ("anthropic", "claude-3-haiku"),
    ("mistral", "mistral-tiny"),
    ("ollama", "mistral"),
]

# Fast Latency
FallbackChain.FAST_LATENCY = [
    ("openai", "gpt-3.5-turbo"),
    ("anthropic", "claude-3-haiku"),
    ("ollama", "mistral"),
]

# Local Only
FallbackChain.LOCAL_ONLY = [
    ("ollama", "mistral"),
    ("ollama", "llama2"),
    ("ollama", "codellama"),
]

# Code Generation
FallbackChain.CODE_GENERATION = [
    ("openai", "gpt-4"),
    ("anthropic", "claude-3-sonnet"),
    ("together", "codellama/CodeLlama-34b-Instruct-hf"),
    ("ollama", "codellama"),
]
```

### Custom Fallback Chain

```python
# Get fallback chain for specific requirements
chain = await llm_service.router.get_fallback_chain(
    primary_provider="openai",
    primary_model="gpt-4",
    strategy=RoutingStrategy.COST_OPTIMIZED,
    required_capability="code",
)

# Returns: [("openai", "gpt-4"), ("anthropic", "claude-3-haiku"), ...]
```

## Model Registry

### Query Models

```python
from backend.services.llm.registry import ModelRegistry

# Get model configuration
config = ModelRegistry.get_model_config("openai", "gpt-4")
print(config.cost_per_1k_prompt)  # 0.03
print(config.max_tokens)  # 8192

# List all models
models = ModelRegistry.list_models()
# ["openai/gpt-4", "anthropic/claude-3-opus", ...]

# List models by provider
openai_models = ModelRegistry.list_models("openai")
# ["openai/gpt-4", "openai/gpt-3.5-turbo", ...]

# Find models by capability
code_models = ModelRegistry.find_models_by_capability("code")

# Find cheap models
cheap_models = ModelRegistry.find_models_by_capability(
    "code",
    max_cost_per_1k=0.01
)

# Get cheapest model
cheapest = ModelRegistry.get_cheapest_model(capability="code")

# Get fastest model
fastest = ModelRegistry.get_fastest_model(
    capability="code",
    max_cost_per_1k=0.05
)
```

## Monitoring & Metrics

### Usage Statistics

```python
# Track usage automatically
llm_service.router.track_usage(
    provider="openai",
    model="gpt-4",
    success=True,
    latency_ms=1200,
    cost_usd=0.05,
)

# Get usage stats
stats = llm_service.get_usage_stats()
# {
#   "openai/gpt-4": {
#     "total_calls": 150,
#     "successful_calls": 148,
#     "failed_calls": 2,
#     "total_latency_ms": 180000,
#     "total_cost_usd": 7.50
#   }
# }

# Get stats for specific provider
openai_stats = llm_service.get_usage_stats("openai")
```

### Health Check

```python
# Check provider health
health = await llm_service.health_check()
# {
#   "openai": True,
#   "anthropic": True,
#   "mistral": False,
#   "ollama": True
# }
```

### Cost Tracking

```python
from backend.services.cost.llm_tracker import get_llm_tracker

tracker = get_llm_tracker(db_session)

# Get workspace costs
costs = await tracker.get_workspace_costs("workspace-123", period="month")
# {
#   "total_cost": 45.67,
#   "total_tokens": 1500000,
#   "call_count": 450,
#   "by_model": [...]
# }

# Get daily costs
daily = await tracker.get_daily_costs("workspace-123", days=30)
```

## Setup Instructions

### 1. Install Dependencies

```bash
# Core dependencies (always install)
pip install httpx

# Provider-specific (install as needed)
pip install openai
pip install anthropic
pip install mistralai
```

### 2. Configure API Keys

```bash
# Add to .env file
OPENAI_API_KEY=sk-...
ANTHROPIC_API_KEY=sk-ant-...
MISTRAL_API_KEY=...
```

### 3. Set Up Ollama (Optional)

```bash
# Install Ollama
curl https://ollama.ai/install.sh | sh

# Pull models
ollama pull mistral
ollama pull llama2
ollama pull codellama

# Start server (default: http://localhost:11434)
ollama serve
```

### 4. Test Configuration

```python
from backend.services.llm.llm_service import get_llm_service

llm_service = get_llm_service()

# Check available providers
print(llm_service.get_available_providers())

# Health check
health = await llm_service.health_check()
print(health)
```

## Best Practices

### 1. Cost Optimization

```python
# Use cheaper models for simple tasks
response = await llm_service.generate(
    prompt="Summarize this text",
    provider="openai",
    model="gpt-3.5-turbo",  # Cheaper than GPT-4
)

# Enable cost-optimized routing
response = await llm_service.generate(
    prompt="Simple analysis",
    budget_remaining=budget,
    task_type="analysis",
)
```

### 2. Latency Optimization

```python
# Use faster models for real-time applications
response = await llm_service.generate(
    prompt="Quick question",
    provider="openai",
    model="gpt-3.5-turbo",  # Faster than GPT-4
)

# Use streaming for better UX
async for chunk in llm_service.stream_generate(
    prompt="Generate report",
    provider="anthropic",
    model="claude-3-haiku",  # Fast model
):
    send_to_client(chunk)
```

### 3. Quality vs Cost Trade-offs

```python
# High-quality for critical tasks
response = await llm_service.generate(
    prompt="Complex architecture decision",
    provider="openai",
    model="gpt-4",  # Highest quality
    temperature=0.3,  # More deterministic
)

# Cost-effective for bulk operations
for item in bulk_items:
    response = await llm_service.generate(
        prompt=item,
        provider="anthropic",
        model="claude-3-haiku",  # Cheap and fast
    )
```

### 4. Local Models for Privacy

```python
# Use local models for sensitive data
response = await llm_service.generate(
    prompt="Analyze sensitive data",
    provider="ollama",
    model="mistral",  # No data leaves your server
)
```

### 5. Fallback for Reliability

```python
# Always enable fallback for production
response = await llm_service.generate(
    prompt="Critical operation",
    enable_fallback=True,
    task_type="code_generation",
)
```

## Troubleshooting

### Provider Not Available

```python
# Check health
health = await llm_service.health_check()
if not health.get("openai"):
    logger.error("OpenAI provider not available")
    # Use fallback
```

### Rate Limiting

```python
from backend.services.llm.provider import RateLimitError

try:
    response = await llm_service.generate(prompt="...")
except RateLimitError as e:
    logger.warning(f"Rate limited: {e}")
    # Automatic fallback will retry with different provider
```

### Ollama Connection Issues

```bash
# Check if Ollama is running
curl http://localhost:11434/api/tags

# Start Ollama
ollama serve

# Check model is pulled
ollama list
```

### Authentication Errors

```python
from backend.services.llm.provider import AuthenticationError

try:
    response = await llm_service.generate(prompt="...")
except AuthenticationError as e:
    logger.error(f"Authentication failed: {e}")
    # Check API keys in .env file
```

## Performance Tuning

### 1. Model Selection

- **GPT-4**: Best quality, highest cost, slower
- **GPT-3.5 Turbo**: Good balance, fast, cost-effective
- **Claude 3 Opus**: High quality, good for long context
- **Claude 3 Haiku**: Fast, cheap, good for simple tasks
- **Mistral Medium**: Good balance, multilingual
- **Ollama**: Free, private, slower

### 2. Temperature Settings

```python
# Deterministic (factual, consistent)
response = await llm_service.generate(
    prompt="Calculate result",
    temperature=0.0,
)

# Creative (varied, diverse)
response = await llm_service.generate(
    prompt="Write a story",
    temperature=0.9,
)

# Balanced (recommended)
response = await llm_service.generate(
    prompt="General task",
    temperature=0.7,
)
```

### 3. Token Limits

```python
# Short responses (faster, cheaper)
response = await llm_service.generate(
    prompt="One sentence summary",
    max_tokens=50,
)

# Long responses
response = await llm_service.generate(
    prompt="Detailed explanation",
    max_tokens=2000,
)
```

## Architecture

```
┌─────────────────────────────────────────────────────────────┐
│                        LLM Service                           │
│  ┌────────────────────────────────────────────────────────┐ │
│  │                    LLM Router                           │ │
│  │  - Provider Selection                                   │ │
│  │  - Routing Strategies                                   │ │
│  │  - Fallback Chains                                      │ │
│  └────────────────────────────────────────────────────────┘ │
│                              │                               │
│  ┌───────────────────────────┼──────────────────────────┐  │
│  │                           │                           │  │
│  ▼                           ▼                           ▼  │
│  OpenAI Provider      Anthropic Provider      Mistral ...   │
│  - GPT-4              - Claude 3 Opus         - Mistral Lg  │
│  - GPT-3.5            - Claude 3 Sonnet       - Mistral Md  │
│                                                              │
│  ┌────────────────────┐       ┌────────────────────┐       │
│  │  Cost Tracker      │       │  Model Registry     │       │
│  │  - Token Usage     │       │  - Model Configs    │       │
│  │  - Cost Logging    │       │  - Capabilities     │       │
│  └────────────────────┘       └────────────────────┘       │
└─────────────────────────────────────────────────────────────┘
```

## License

MIT License - See LICENSE file for details
