# -*- coding: utf-8 -*-
"""Main LLM service integrating providers, routing, and cost tracking."""

import logging
from datetime import datetime, timezone
from typing import AsyncIterator, Dict, List, Optional

from sqlalchemy.ext.asyncio import AsyncSession

from backend.config import settings
from backend.services.cost.llm_tracker import LLMCostTracker

from mgx_observability import (
    ObservabilityConfig,
    get_langsmith_logger,
    observability_context,
    record_exception,
    set_span_attributes,
    start_span,
)

from .provider import LLMProvider, LLMResponse, AllProvidersFailedError, ProviderError
from .router import LLMRouter, RoutingStrategy
from .providers import (
    OpenAIProvider,
    AnthropicProvider,
    MistralProvider,
    OllamaProvider,
    TogetherAIProvider,
)

logger = logging.getLogger(__name__)


class LLMService:
    """
    Main LLM service facade.
    
    Provides:
    - Unified interface to all LLM providers
    - Automatic provider selection and routing
    - Fallback chain management
    - Cost tracking integration
    - Usage analytics
    """
    
    def __init__(
        self,
        db_session: Optional[AsyncSession] = None,
        router: Optional[LLMRouter] = None,
    ):
        """
        Initialize the LLM service.
        
        Args:
            db_session: Database session for cost tracking
            router: Custom router (creates default if not provided)
        """
        self.db_session = db_session
        self.cost_tracker = LLMCostTracker(db_session) if db_session else None
        
        # Initialize providers
        self.providers = self._initialize_providers()
        
        # Initialize router
        self.router = router or LLMRouter(
            providers=self.providers,
            default_strategy=RoutingStrategy(settings.llm_routing_strategy),
        )
        
        logger.info(
            f"LLM Service initialized with {len(self.providers)} providers: "
            f"{', '.join(self.providers.keys())}"
        )
    
    def _initialize_providers(self) -> Dict[str, LLMProvider]:
        """Initialize available LLM providers."""
        providers = {}
        
        # OpenAI
        if settings.openai_api_key:
            providers["openai"] = OpenAIProvider(
                api_key=settings.openai_api_key,
                organization=settings.openai_organization,
            )
            logger.info("OpenAI provider initialized")
        
        # Anthropic
        if settings.anthropic_api_key:
            providers["anthropic"] = AnthropicProvider(
                api_key=settings.anthropic_api_key,
            )
            logger.info("Anthropic provider initialized")
        
        # Mistral
        if settings.mistral_api_key:
            providers["mistral"] = MistralProvider(
                api_key=settings.mistral_api_key,
            )
            logger.info("Mistral provider initialized")
        
        # Together AI
        if settings.together_api_key:
            providers["together"] = TogetherAIProvider(
                api_key=settings.together_api_key,
            )
            logger.info("Together AI provider initialized")
        
        # Ollama (local)
        if settings.llm_prefer_local or not providers:
            providers["ollama"] = OllamaProvider(
                base_url=settings.ollama_base_url,
            )
            logger.info(f"Ollama provider initialized at {settings.ollama_base_url}")
        
        return providers
    
    async def generate(
        self,
        prompt: str,
        workspace_id: Optional[str] = None,
        project_id: Optional[str] = None,
        agent_id: Optional[str] = None,
        execution_id: Optional[str] = None,
        provider: Optional[str] = None,
        model: Optional[str] = None,
        temperature: float = 0.7,
        max_tokens: int = 2000,
        task_type: Optional[str] = None,
        budget_remaining: Optional[float] = None,
        required_capability: Optional[str] = None,
        enable_fallback: Optional[bool] = None,
        **kwargs
    ) -> LLMResponse:
        """
        Generate text completion with automatic provider selection and fallback.
        
        Args:
            prompt: Input prompt
            workspace_id: Workspace identifier for cost tracking
            execution_id: Execution identifier for cost tracking
            provider: Specific provider to use (overrides routing)
            model: Specific model to use (overrides routing)
            temperature: Sampling temperature
            max_tokens: Maximum tokens to generate
            task_type: Task type for routing optimization
            budget_remaining: Remaining budget for cost-aware routing
            required_capability: Required model capability
            enable_fallback: Enable fallback (uses config default if not specified)
            **kwargs: Additional provider-specific parameters
        
        Returns:
            LLMResponse with generated text and metadata
        
        Raises:
            AllProvidersFailedError: If all providers in fallback chain fail
        """
        enable_fallback = (
            enable_fallback
            if enable_fallback is not None
            else settings.llm_enable_fallback
        )
        
        # If provider/model specified, use it directly
        if provider and model:
            return await self._generate_with_provider(
                provider=provider,
                model=model,
                prompt=prompt,
                temperature=temperature,
                max_tokens=max_tokens,
                workspace_id=workspace_id,
                project_id=project_id,
                agent_id=agent_id,
                execution_id=execution_id,
                **kwargs,
            )
        
        # Otherwise, use router to select provider
        provider, model = await self.router.select_provider(
            task=task_type,
            budget_remaining=budget_remaining,
            required_capability=required_capability,
            prefer_local=settings.llm_prefer_local,
        )
        
        # Try primary provider
        try:
            return await self._generate_with_provider(
                provider=provider,
                model=model,
                prompt=prompt,
                temperature=temperature,
                max_tokens=max_tokens,
                workspace_id=workspace_id,
                project_id=project_id,
                agent_id=agent_id,
                execution_id=execution_id,
                **kwargs,
            )
        except ProviderError as e:
            logger.warning(f"Primary provider {provider}/{model} failed: {e}")
            
            if not enable_fallback:
                raise
            
            # Try fallback chain
            fallback_chain = await self.router.get_fallback_chain(
                primary_provider=provider,
                primary_model=model,
                required_capability=required_capability,
            )
            
            # Skip first (already tried)
            for fallback_provider, fallback_model in fallback_chain[1:]:
                try:
                    logger.info(
                        f"Trying fallback provider: {fallback_provider}/{fallback_model}"
                    )
                    
                    return await self._generate_with_provider(
                        provider=fallback_provider,
                        model=fallback_model,
                        prompt=prompt,
                        temperature=temperature,
                        max_tokens=max_tokens,
                        workspace_id=workspace_id,
                        project_id=project_id,
                        agent_id=agent_id,
                        execution_id=execution_id,
                        **kwargs,
                    )
                except ProviderError as fallback_error:
                    logger.warning(
                        f"Fallback provider {fallback_provider}/{fallback_model} failed: "
                        f"{fallback_error}"
                    )
                    continue
            
            raise AllProvidersFailedError(
                "All providers in fallback chain failed. "
                f"Tried: {', '.join([f'{p}/{m}' for p, m in fallback_chain])}"
            )
    
    async def _generate_with_provider(
        self,
        provider: str,
        model: str,
        prompt: str,
        temperature: float,
        max_tokens: int,
        workspace_id: Optional[str],
        project_id: Optional[str],
        agent_id: Optional[str],
        execution_id: Optional[str],
        **kwargs,
    ) -> LLMResponse:
        """Generate with a specific provider and track metrics."""
        provider_instance = self.providers.get(provider)
        
        if not provider_instance:
            raise ProviderError(f"Provider not available: {provider}")
        
        obs_cfg = ObservabilityConfig(
            langsmith_enabled=settings.langsmith_enabled,
            langsmith_api_key=settings.langsmith_api_key,
            langsmith_project=settings.langsmith_project,
            langsmith_endpoint=settings.langsmith_endpoint,
        )
        langsmith_logger = get_langsmith_logger(obs_cfg)

        with observability_context(
            workspace_id=workspace_id,
            project_id=project_id,
            agent_id=agent_id,
            execution_id=execution_id,
        ):
            async with start_span(
                "llm.generate",
                attributes={
                    "llm.provider": provider,
                    "llm.model": model,
                    "llm.temperature": temperature,
                    "llm.max_tokens": max_tokens,
                },
            ) as span:
                started_at = datetime.now(timezone.utc)

                try:
                    response = await provider_instance.generate(
                        prompt=prompt,
                        model=model,
                        temperature=temperature,
                        max_tokens=max_tokens,
                        **kwargs,
                    )
                except Exception as e:
                    # Track failure
                    self.router.track_usage(
                        provider=provider,
                        model=model,
                        success=False,
                        latency_ms=0,
                        cost_usd=0.0,
                    )

                    record_exception(span, e)
                    set_span_attributes(span, {"llm.success": False})

                    if langsmith_logger is not None:
                        await langsmith_logger.log_llm_call(
                            name="llm.generate",
                            provider=provider,
                            model=model,
                            prompt=prompt,
                            output="",
                            error=str(e),
                            metadata={
                                "workspace_id": workspace_id,
                                "project_id": project_id,
                                "agent_id": agent_id,
                                "execution_id": execution_id,
                            },
                            start_time=started_at,
                            end_time=datetime.now(timezone.utc),
                        )

                    raise

                completed_at = datetime.now(timezone.utc)

                # Track usage
                self.router.track_usage(
                    provider=provider,
                    model=model,
                    success=True,
                    latency_ms=response.latency_ms,
                    cost_usd=response.cost_usd,
                )

                set_span_attributes(
                    span,
                    {
                        "llm.success": True,
                        "llm.tokens.prompt": response.tokens_prompt,
                        "llm.tokens.completion": response.tokens_completion,
                        "llm.tokens.total": response.tokens_total,
                        "llm.cost.usd": response.cost_usd,
                        "llm.latency.ms": response.latency_ms,
                    },
                )

                # Log cost to database
                if self.cost_tracker and workspace_id and execution_id:
                    await self.cost_tracker.log_llm_call(
                        workspace_id=workspace_id,
                        execution_id=execution_id,
                        provider=provider,
                        model=model,
                        tokens_prompt=response.tokens_prompt,
                        tokens_completion=response.tokens_completion,
                        latency_ms=response.latency_ms,
                        project_id=project_id,
                        agent_id=agent_id,
                        metadata={
                            "temperature": temperature,
                            "max_tokens": max_tokens,
                            **response.metadata,
                        },
                    )

                if langsmith_logger is not None:
                    await langsmith_logger.log_llm_call(
                        name="llm.generate",
                        provider=provider,
                        model=model,
                        prompt=prompt,
                        output=response.content,
                        metadata={
                            "workspace_id": workspace_id,
                            "project_id": project_id,
                            "agent_id": agent_id,
                            "execution_id": execution_id,
                            "tokens_prompt": response.tokens_prompt,
                            "tokens_completion": response.tokens_completion,
                            "tokens_total": response.tokens_total,
                            "cost_usd": response.cost_usd,
                            "latency_ms": response.latency_ms,
                        },
                        start_time=started_at,
                        end_time=completed_at,
                    )

                logger.info(
                    f"LLM generation successful - {provider}/{model}: "
                    f"{response.tokens_total} tokens, ${response.cost_usd:.4f}, "
                    f"{response.latency_ms}ms"
                )

                return response
    
    async def stream_generate(
        self,
        prompt: str,
        provider: Optional[str] = None,
        model: Optional[str] = None,
        temperature: float = 0.7,
        max_tokens: int = 2000,
        task_type: Optional[str] = None,
        required_capability: Optional[str] = None,
        **kwargs
    ) -> AsyncIterator[str]:
        """
        Stream text completion.
        
        Args:
            prompt: Input prompt
            provider: Specific provider to use
            model: Specific model to use
            temperature: Sampling temperature
            max_tokens: Maximum tokens to generate
            task_type: Task type for routing
            required_capability: Required capability
            **kwargs: Additional parameters
        
        Yields:
            Text chunks as they are generated
        """
        # Select provider if not specified
        if not provider or not model:
            provider, model = await self.router.select_provider(
                task=task_type,
                required_capability=required_capability,
                prefer_local=settings.llm_prefer_local,
            )
        
        provider_instance = self.providers.get(provider)
        
        if not provider_instance:
            raise ProviderError(f"Provider not available: {provider}")
        
        async for chunk in provider_instance.stream_generate(
            prompt=prompt,
            model=model,
            temperature=temperature,
            max_tokens=max_tokens,
            **kwargs
        ):
            yield chunk
    
    def get_available_providers(self) -> List[str]:
        """Get list of available provider names."""
        return list(self.providers.keys())
    
    def get_provider(self, name: str) -> Optional[LLMProvider]:
        """Get a specific provider instance."""
        return self.providers.get(name)
    
    def get_usage_stats(self, provider: Optional[str] = None) -> Dict:
        """Get usage statistics."""
        return self.router.get_usage_stats(provider)
    
    async def health_check(self) -> Dict[str, bool]:
        """
        Check health of all providers.
        
        Returns:
            Dictionary of provider name -> health status
        """
        health = {}
        
        for name, provider in self.providers.items():
            try:
                is_healthy = provider.is_available()
                
                # Additional check for Ollama
                if name == "ollama" and is_healthy:
                    is_healthy = await provider.check_connection()
                
                health[name] = is_healthy
            except Exception as e:
                logger.warning(f"Health check failed for {name}: {e}")
                health[name] = False
        
        return health


# Global service instance (initialized on first use)
_llm_service: Optional[LLMService] = None


def get_llm_service(db_session: Optional[AsyncSession] = None) -> LLMService:
    """
    Get LLM service instance.
    
    Args:
        db_session: Database session for cost tracking
    
    Returns:
        LLMService instance
    """
    global _llm_service
    
    if _llm_service is None:
        _llm_service = LLMService(db_session=db_session)
    
    return _llm_service
