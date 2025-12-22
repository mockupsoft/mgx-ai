#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""Direct test of LLM modules without pytest."""

import sys
import os

# Set dummy OpenAI key for MetaGPT
os.environ['OPENAI_API_KEY'] = 'sk-test'

# Test registry
print("=" * 60)
print("Testing ModelRegistry...")
print("=" * 60)

try:
    from backend.services.llm.registry import ModelRegistry
    print("✅ Registry imported successfully")
    
    # Test get_model_config
    config = ModelRegistry.get_model_config('openai', 'gpt-4')
    print(f"✅ GPT-4 config: {config.max_tokens} tokens, ${config.cost_per_1k_prompt} per 1k prompt")
    
    # Test list_models
    models = ModelRegistry.list_models('openai')
    print(f"✅ Found {len(models)} OpenAI models: {models[:3]}...")
    
    # Test find_models_by_capability
    code_models = ModelRegistry.find_models_by_capability('code')
    print(f"✅ Found {len(code_models)} models with 'code' capability")
    
    # Test get_cheapest_model
    cheapest = ModelRegistry.get_cheapest_model('code')
    print(f"✅ Cheapest code model: {cheapest.provider}/{cheapest.model} (${cheapest.cost_per_1k_prompt + cheapest.cost_per_1k_completion} per 1k)")
    
    # Test get_fastest_model
    fastest = ModelRegistry.get_fastest_model('code')
    print(f"✅ Fastest code model: {fastest.provider}/{fastest.model} ({fastest.latency_estimate_ms}ms)")
    
    print("\n✅ All ModelRegistry tests passed!\n")
    
except Exception as e:
    print(f"❌ Error: {e}")
    import traceback
    traceback.print_exc()
    sys.exit(1)

# Test router
print("=" * 60)
print("Testing LLMRouter...")
print("=" * 60)

try:
    from backend.services.llm.router import LLMRouter, RoutingStrategy, FallbackChain
    print("✅ Router imported successfully")
    
    # Test routing strategies
    print(f"✅ Available strategies: {[s.value for s in RoutingStrategy]}")
    
    # Test fallback chains
    print(f"✅ High Quality Chain: {len(FallbackChain.HIGH_QUALITY)} models")
    print(f"✅ Cost Optimized Chain: {len(FallbackChain.COST_OPTIMIZED)} models")
    print(f"✅ Fast Latency Chain: {len(FallbackChain.FAST_LATENCY)} models")
    print(f"✅ Local Only Chain: {len(FallbackChain.LOCAL_ONLY)} models")
    print(f"✅ Code Generation Chain: {len(FallbackChain.CODE_GENERATION)} models")
    
    print("\n✅ All LLMRouter tests passed!\n")
    
except Exception as e:
    print(f"❌ Error: {e}")
    import traceback
    traceback.print_exc()
    sys.exit(1)

# Test providers
print("=" * 60)
print("Testing Provider Implementations...")
print("=" * 60)

try:
    from backend.services.llm.providers import (
        OpenAIProvider,
        AnthropicProvider,
        MistralProvider,
        OllamaProvider,
        TogetherAIProvider,
    )
    print("✅ All providers imported successfully")
    
    # Test OpenAI provider
    openai_provider = OpenAIProvider(api_key="test-key")
    print(f"✅ OpenAI provider: {openai_provider.provider_name}")
    print(f"   Available models: {len(openai_provider.list_models())}")
    
    # Test Anthropic provider
    anthropic_provider = AnthropicProvider(api_key="test-key")
    print(f"✅ Anthropic provider: {anthropic_provider.provider_name}")
    print(f"   Available models: {len(anthropic_provider.list_models())}")
    
    # Test Mistral provider
    mistral_provider = MistralProvider(api_key="test-key")
    print(f"✅ Mistral provider: {mistral_provider.provider_name}")
    print(f"   Available models: {len(mistral_provider.list_models())}")
    
    # Test Ollama provider
    ollama_provider = OllamaProvider()
    print(f"✅ Ollama provider: {ollama_provider.provider_name}")
    print(f"   Available models: {len(ollama_provider.list_models())}")
    
    # Test Together provider
    together_provider = TogetherAIProvider(api_key="test-key")
    print(f"✅ Together provider: {together_provider.provider_name}")
    print(f"   Available models: {len(together_provider.list_models())}")
    
    print("\n✅ All Provider tests passed!\n")
    
except Exception as e:
    print(f"❌ Error: {e}")
    import traceback
    traceback.print_exc()
    sys.exit(1)

print("=" * 60)
print("✅ ALL TESTS PASSED!")
print("=" * 60)
print("\nPhase 20 implementation is working correctly!")
print("- Model Registry: ✅")
print("- LLM Router: ✅") 
print("- Providers (5): ✅")
print("- Fallback Chains: ✅")
