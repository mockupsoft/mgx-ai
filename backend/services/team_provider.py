# -*- coding: utf-8 -*-
"""
MGX Team Provider Service

Wraps MGXStyleTeam for FastAPI dependency injection without modifying
the public API of the original team class.
"""

import asyncio
import logging
import os
import yaml
from pathlib import Path
from typing import Optional, Dict, Any, TYPE_CHECKING, Callable
from contextlib import asynccontextmanager

if TYPE_CHECKING:
    from mgx_agent import MGXStyleTeam, TeamConfig

logger = logging.getLogger(__name__)

# Lazy import to avoid Pydantic validation errors during module import
# Do NOT import mgx_agent at module level - import only when needed


class MGXTeamProvider:
    """
    Service provider for MGXStyleTeam instances.
    
    Manages team lifecycle and provides dependency injection for routers.
    Wraps MGXStyleTeam without modifying its public API.
    """
    
    def __init__(self, config: Optional['TeamConfig'] = None):
        """
        Initialize the team provider.
        
        Args:
            config: TeamConfig instance. If None, uses DEFAULT_CONFIG.
        """
        # Store config as-is - lazy import will happen in get_team()
        self.config = config
        self._team: Optional['MGXStyleTeam'] = None
        self._lock = asyncio.Lock()
        logger.info(f"MGXTeamProvider initialized (config will be resolved lazily)")
    
    async def get_team(self) -> 'MGXStyleTeam':
        """
        Get or create the team instance.
        
        Thread-safe lazy initialization with async lock.
        
        Returns:
            MGXStyleTeam instance
        """
        # Lazy import to avoid Pydantic validation errors - only import when actually needed
        if self._team is None:
            async with self._lock:
                if self._team is None:
                    try:
                        from backend.config import settings
                        
                        # CRITICAL: Set environment variables BEFORE importing mgx_agent
                        # MetaGPT Config validates during import, so we must set env vars first
                        logger.info("Setting MetaGPT LLM config environment variables...")
                        
                        # Set default LLM provider first
                        default_provider = settings.llm_default_provider or "ollama"
                        
                        # Set all LLM environment variables (MetaGPT reads these during Config import)
                        # CRITICAL: MetaGPT Config validates during import, so these must be set BEFORE import
                        os.environ["OPENAI_API_KEY"] = settings.openai_api_key or ""
                        os.environ["ANTHROPIC_API_KEY"] = settings.anthropic_api_key or ""
                        os.environ["MISTRAL_API_KEY"] = settings.mistral_api_key or ""
                        os.environ["TOGETHER_API_KEY"] = settings.together_api_key or ""
                        os.environ["OPENROUTER_API_KEY"] = settings.openrouter_api_key or ""
                        os.environ["GOOGLE_API_KEY"] = getattr(settings, 'google_api_key', None) or ""
                        os.environ["OLLAMA_BASE_URL"] = settings.ollama_base_url or "http://localhost:11434"
                        os.environ["LLM_DEFAULT_PROVIDER"] = default_provider
                        
                        # For Gemini, set Google API key
                        if default_provider == "gemini":
                            os.environ["LLM_API_KEY"] = getattr(settings, 'google_api_key', None) or ""
                            os.environ["GEMINI_API_KEY"] = getattr(settings, 'google_api_key', None) or ""
                            logger.info(f"Setting MetaGPT LLM config for Gemini with model: {getattr(settings, 'gemini_model', 'gemini-2.0-flash')}")
                        # For Ollama, set specific environment variables that MetaGPT might check
                        elif default_provider == "ollama":
                            os.environ["OLLAMA_HOST"] = "localhost"
                            os.environ["OLLAMA_PORT"] = "11434"
                            # MetaGPT might also check these
                            os.environ.setdefault("LLM_API_KEY", "")
                            os.environ.setdefault("LLM_BASE_URL", settings.ollama_base_url or "http://localhost:11434")
                        elif default_provider == "openrouter":
                            # OpenRouter uses OpenAI-compatible API
                            os.environ["LLM_API_KEY"] = settings.openrouter_api_key or ""
                            os.environ["LLM_BASE_URL"] = settings.openrouter_base_url or "https://openrouter.ai/api/v1"
                            # Set OpenAI API key to OpenRouter key for compatibility
                            os.environ["OPENAI_API_KEY"] = settings.openrouter_api_key or ""
                            os.environ["OPENAI_BASE_URL"] = settings.openrouter_base_url or "https://openrouter.ai/api/v1"
                        else:
                            # For other providers, set LLM_API_KEY to the appropriate key
                            if default_provider == "openai":
                                os.environ["LLM_API_KEY"] = settings.openai_api_key or ""
                            elif default_provider == "anthropic":
                                os.environ["LLM_API_KEY"] = settings.anthropic_api_key or ""
                            elif default_provider == "mistral":
                                os.environ["LLM_API_KEY"] = settings.mistral_api_key or ""
                            elif default_provider == "together":
                                os.environ["LLM_API_KEY"] = settings.together_api_key or ""
                        
                        # Create MetaGPT config directory and config.yaml file if it doesn't exist
                        # MetaGPT Config.from_home() reads from ~/.metagpt/config.yaml
                        home_dir = Path.home()
                        metagpt_dir = home_dir / ".metagpt"
                        metagpt_config_file = metagpt_dir / "config.yaml"
                        
                        # Set additional MetaGPT-specific environment variables AFTER metagpt_dir is defined
                        os.environ["METAGPT_CONFIG_PATH"] = str(metagpt_config_file)
                        # Set METAGPT_LLM_API_KEY based on default provider
                        if default_provider == "gemini":
                            os.environ["METAGPT_LLM_API_KEY"] = getattr(settings, 'google_api_key', None) or ""
                        elif default_provider == "openrouter":
                            os.environ["METAGPT_LLM_API_KEY"] = settings.openrouter_api_key or ""
                            os.environ["METAGPT_LLM_BASE_URL"] = settings.openrouter_base_url or "https://openrouter.ai/api/v1"
                        else:
                            os.environ["METAGPT_LLM_API_KEY"] = settings.openai_api_key or settings.anthropic_api_key or settings.mistral_api_key or settings.together_api_key or ""
                            os.environ["METAGPT_LLM_BASE_URL"] = settings.ollama_base_url or "http://localhost:11434"
                        
                        # Create MetaGPT config directory and config.yaml file if it doesn't exist
                        # MetaGPT Config.from_home() reads from ~/.metagpt/config.yaml
                        home_dir = Path.home()
                        metagpt_dir = home_dir / ".metagpt"
                        metagpt_config_file = metagpt_dir / "config.yaml"
                        
                        try:
                            metagpt_dir.mkdir(parents=True, exist_ok=True)
                            
                            # Always create/update config.yaml to ensure correct provider settings
                            logger.info(f"Creating/updating MetaGPT config file at {metagpt_config_file}")
                            
                            # Determine LLM config based on provider
                            if default_provider == "gemini":
                                llm_config = {
                                    "api_type": "gemini",
                                    "api_key": os.environ.get("GOOGLE_API_KEY", ""),
                                    "model": os.environ.get("GEMINI_MODEL", "gemini-2.0-flash"),
                                }
                            elif default_provider == "ollama":
                                llm_config = {
                                    "api_type": "ollama",
                                    "api_key": "",
                                    "base_url": os.environ.get("OLLAMA_BASE_URL", "http://localhost:11434"),
                                    "model": "llama3.2",
                                }
                            elif default_provider == "openai":
                                llm_config = {
                                    "api_type": "openai",
                                    "api_key": os.environ.get("OPENAI_API_KEY", ""),
                                    "base_url": "",
                                    "model": "gpt-4",
                                }
                            elif default_provider == "anthropic":
                                llm_config = {
                                    "api_type": "anthropic",
                                    "api_key": os.environ.get("ANTHROPIC_API_KEY", ""),
                                    "base_url": "",
                                    "model": "claude-3-opus-20240229",
                                }
                            elif default_provider == "openrouter":
                                # OpenRouter uses OpenAI-compatible API
                                llm_config = {
                                    "api_type": "openai",
                                    "api_key": os.environ.get("OPENROUTER_API_KEY", ""),
                                    "base_url": os.environ.get("OPENROUTER_BASE_URL", "https://openrouter.ai/api/v1"),
                                    "model": "nex-agi/deepseek-v3.1-nex-n1:free",
                                }
                            else:
                                # Default to ollama
                                llm_config = {
                                    "api_type": "ollama",
                                    "api_key": "",
                                    "base_url": os.environ.get("OLLAMA_BASE_URL", "http://localhost:11434"),
                                    "model": "llama3.2",
                                }
                            
                            config_data = {
                                "llm": llm_config
                            }
                            
                            with open(metagpt_config_file, 'w', encoding='utf-8') as f:
                                yaml.dump(config_data, f, default_flow_style=False, allow_unicode=True)
                            
                            logger.info(f"MetaGPT config file updated with {default_provider} provider: {llm_config}")
                        except Exception as config_error:
                            logger.warning(f"Failed to create MetaGPT config file: {config_error}")
                            # Continue anyway - environment variables might be enough
                        
                        logger.info(f"MetaGPT LLM env vars set - provider: {default_provider}, ollama_url: {os.environ.get('OLLAMA_BASE_URL')}")
                        
                        # NOW import mgx_agent after environment variables and config file are set
                        # MetaGPT Config will read from environment variables and config file during import
                        import_attempts = 0
                        max_import_attempts = 3
                        import_success = False
                        last_import_error = None
                        
                        # Try to monkey-patch MetaGPT Config before import to avoid validation errors
                        # This is a workaround for MetaGPT Config's strict validation during import
                        try:
                            import sys
                            # Check if metagpt.config is already imported
                            if 'metagpt.config' not in sys.modules:
                                # Try to create a minimal Config mock before actual import
                                # This prevents Pydantic validation errors during import
                                logger.debug("Attempting to pre-configure MetaGPT Config...")
                        except Exception as prep_error:
                            logger.debug(f"Pre-configuration attempt failed (non-critical): {prep_error}")
                        
                        while import_attempts < max_import_attempts and not import_success:
                            import_attempts += 1
                            try:
                                # CRITICAL: Import mgx_agent which will trigger MetaGPT Config import
                                # MetaGPT Config validates during import, so all env vars must be set
                                from mgx_agent import MGXStyleTeam, DEFAULT_CONFIG
                                logger.info("Successfully imported MGXStyleTeam")
                                import_success = True
                            except Exception as import_error:
                                last_import_error = import_error
                                error_str = str(import_error)
                                
                                if import_attempts < max_import_attempts:
                                    if "validation error for Config" in error_str and "llm" in error_str:
                                        logger.warning(f"MetaGPT Config validation failed (attempt {import_attempts}/{max_import_attempts}): {import_error}")
                                        
                                        # Try to ensure config file exists and is valid
                                        try:
                                            if metagpt_config_file.exists():
                                                # Verify config file content
                                                with open(metagpt_config_file, 'r', encoding='utf-8') as f:
                                                    existing_config = yaml.safe_load(f)
                                                    if not existing_config or 'llm' not in existing_config:
                                                        logger.warning("Config file exists but missing 'llm' field, recreating...")
                                                        metagpt_config_file.unlink()  # Delete invalid config
                                                        raise FileNotFoundError("Invalid config, will recreate")
                                        except Exception as config_check_error:
                                            logger.debug(f"Config file check failed: {config_check_error}")
                                        
                                        # Set additional environment variables that MetaGPT might check
                                        # MetaGPT might use different env var names - try common variations
                                        os.environ["METAGPT_CONFIG_PATH"] = str(metagpt_config_file)
                                        os.environ["METAGPT_LLM_API_KEY"] = os.environ.get("OPENAI_API_KEY") or os.environ.get("LLM_API_KEY") or ""
                                        os.environ["METAGPT_LLM_BASE_URL"] = os.environ.get("OLLAMA_BASE_URL") or os.environ.get("LLM_BASE_URL") or ""
                                        
                                        # Try setting LLM config as JSON string (some Config classes expect this)
                                        try:
                                            import json
                                            llm_config_dict = {
                                                "api_type": default_provider,
                                                "api_key": os.environ.get("LLM_API_KEY", ""),
                                                "base_url": os.environ.get("LLM_BASE_URL", ""),
                                                "model": "gpt-4" if default_provider == "openai" else "llama3.2"
                                            }
                                            os.environ["METAGPT_LLM_CONFIG"] = json.dumps(llm_config_dict)
                                        except Exception:
                                            pass
                                        
                                        # Wait a bit before retry (in case of file system sync issues)
                                        if import_attempts < max_import_attempts:
                                            await asyncio.sleep(0.2)
                                    else:
                                        # Non-Config validation error - don't retry
                                        logger.error(f"Import failed with non-Config error: {import_error}")
                                        raise
                                else:
                                    # Final attempt failed - provide detailed error message
                                    logger.error(f"Failed to import MGXStyleTeam after {max_import_attempts} attempts")
                                    logger.error(f"Last error: {last_import_error}")
                                    logger.error("MetaGPT Config requires 'llm' field but cannot find it in environment variables or config file")
                                    logger.error(f"Config file path: {metagpt_config_file}")
                                    logger.error(f"Config file exists: {metagpt_config_file.exists() if 'metagpt_config_file' in locals() else 'N/A'}")
                                    logger.error(f"LLM_API_KEY set: {bool(os.environ.get('LLM_API_KEY'))}")
                                    logger.error(f"OPENAI_API_KEY set: {bool(os.environ.get('OPENAI_API_KEY'))}")
                                    logger.error(f"METAGPT_CONFIG_PATH: {os.environ.get('METAGPT_CONFIG_PATH')}")
                                    logger.error(f"Current env vars with 'LLM' or 'OPENAI': {[k for k in os.environ.keys() if 'LLM' in k or 'OPENAI' in k]}")
                                    raise RuntimeError(f"mgx_agent not available: {last_import_error}")
                        
                        if not import_success:
                            raise RuntimeError(f"mgx_agent not available: {last_import_error}")
                        
                        # Resolve config if None
                        if self.config is None:
                            from mgx_agent import TeamConfig
                            # Create config with auto_approve_plan=True to skip manual approval
                            self.config = TeamConfig(auto_approve_plan=True)
                            logger.info("Created TeamConfig with auto_approve_plan=True")
                        elif hasattr(self.config, 'auto_approve_plan'):
                            # Enable auto-approve on existing config
                            self.config.auto_approve_plan = True
                            logger.info("Set auto_approve_plan=True on existing config")
                        
                        logger.info("Creating new MGXStyleTeam instance")
                        self._team = MGXStyleTeam(config=self.config)
                    except Exception as e:
                        logger.error(f"Failed to import or create MGXStyleTeam: {e}", exc_info=True)
                        raise RuntimeError(f"mgx_agent not available: {e}")
        
        return self._team
    
    async def run_task(
        self, 
        task: str, 
        max_attempts: int = 3
    ) -> Dict[str, Any]:
        """
        Run a task through the team.
        
        Args:
            task: Task description
            max_attempts: Maximum retry attempts
        
        Returns:
            Task execution result
        """
        team = await self.get_team()
        logger.info(f"Running task: {task[:50]}...")
        
        try:
            # First analyze and plan the task
            logger.info("Analyzing and planning task...")
            plan = await team.analyze_and_plan(task)
            logger.info(f"Plan generated: {plan[:100] if plan else 'No plan'}...")
            
            # Auto-approve the plan (since we set auto_approve_plan=True)
            if hasattr(team, 'approve_plan'):
                team.approve_plan()
            
            # Execute the plan
            logger.info("Executing plan...")
            result = await team.execute()
            logger.info(f"Task completed successfully")
            return {
                "status": "success",
                "result": result,
                "plan": plan,
            }
        except Exception as e:
            logger.error(f"Task failed: {str(e)}", exc_info=True)
            return {
                "status": "error",
                "error": str(e),
            }
    
    async def simple_chat(self, message: str) -> Dict[str, Any]:
        """
        Simple chat mode - directly call LLM for basic questions.
        No code generation, no agents - just a direct LLM response.
        
        Args:
            message: User's message/question
            
        Returns:
            Dict with status and response
        """
        try:
            from metagpt.config2 import config as global_config
            from metagpt.llm import LLM
            
            logger.info(f"Simple chat: {message[:50]}...")
            
            # Create LLM instance with global config
            llm = LLM(global_config.llm)
            
            # Get current model name for context
            current_model = getattr(global_config.llm, 'model', 'unknown')
            model_info = f"Şu anda {current_model} modelini kullanıyorsun."
            
            # Natural, conversational system prompt for chat
            system_prompt = f"""Sen samimi, doğal ve yardımsever bir AI asistanısın. {model_info}

KRİTİK KURALLAR - MUTLAKA UY:
1. ASLA "Ben Google tarafından eğitilmiş büyük bir dil modeliyim" veya benzeri generic tanıtım cümleleri kullanma
2. "Sen kimsin" sorusuna ÖRNEK CEVAP: "Ben bir AI asistanım, sana yardımcı olmak için buradayım. Sorularını cevaplayabilirim, kod yazabilirim, projeler geliştirebilirim."
3. "Hangi model" veya "hangi modeli kullanıyorsun" sorusuna ÖRNEK CEVAP: "{current_model} kullanıyorum" veya sadece model adını söyle
4. Doğal ve samimi konuş, robot gibi değil, arkadaş gibi
5. Kısa ve öz cevaplar ver (1-2 cümle yeterli), gereksiz detay verme
6. Türkçe sorulara Türkçe, İngilizce sorulara İngilizce cevap ver
7. Kod yazmak veya proje geliştirmek istenmediği sürece, sadece sohbet formatında yanıt ver
8. Generic tanıtım cümleleri, uzun açıklamalar veya eğitim bilgileri verme - sadece soruya direkt cevap ver

ÖRNEK İYİ CEVAPLAR:
- "Sen kimsin" → "Ben bir AI asistanım, sana yardımcı olmak için buradayım."
- "Hangi model" → "{current_model} kullanıyorum"
- "Nasılsın" → "İyiyim, teşekkürler! Sen nasılsın?"

ÖRNEK KÖTÜ CEVAPLAR (ASLA KULLANMA):
- "Ben Google tarafından eğitilmiş büyük bir dil modeliyim" ❌
- "Ben bir yapay zeka asistanıyım ve..." (uzun açıklama) ❌
- Generic tanıtım cümleleri ❌"""
            
            # Temporarily increase temperature in LLM config for more natural responses
            original_temperature = getattr(global_config.llm, 'temperature', None)
            try:
                # Set higher temperature for more natural, varied responses
                if hasattr(global_config.llm, 'temperature'):
                    global_config.llm.temperature = 0.8
                elif hasattr(llm, 'temperature'):
                    llm.temperature = 0.8
                
                # Call LLM directly
                response = await llm.aask(message, system_msgs=[system_prompt])
            finally:
                # Restore original temperature
                if original_temperature is not None and hasattr(global_config.llm, 'temperature'):
                    global_config.llm.temperature = original_temperature
            
            logger.info(f"Simple chat response: {response[:100]}...")
            
            # Post-process response to remove generic phrases
            cleaned_response = response
            generic_phrases = [
                "Ben Google tarafından eğitilmiş",
                "I am a large language model trained by Google",
                "I'm a large language model",
                "Ben bir büyük dil modeliyim",
                "I am an AI assistant trained by",
                "I'm an AI language model",
            ]
            
            for phrase in generic_phrases:
                if phrase.lower() in cleaned_response.lower():
                    # Remove the generic phrase and clean up
                    cleaned_response = cleaned_response.replace(phrase, "")
                    cleaned_response = cleaned_response.replace(phrase.lower(), "")
                    # Clean up extra spaces
                    cleaned_response = " ".join(cleaned_response.split())
                    # If response is too short after cleaning, use a fallback
                    if len(cleaned_response.strip()) < 10:
                        if "sen kimsin" in message.lower() or "who are you" in message.lower():
                            cleaned_response = "Ben bir AI asistanım, sana yardımcı olmak için buradayım."
                        elif "hangi model" in message.lower() or "which model" in message.lower():
                            cleaned_response = f"{current_model} kullanıyorum."
                        else:
                            cleaned_response = response  # Fallback to original if cleaning removed too much
            
            return {
                "status": "success",
                "response": cleaned_response.strip() if cleaned_response.strip() else response,
                "mode": "simple_chat",
            }
        except Exception as e:
            logger.error(f"Simple chat failed: {str(e)}", exc_info=True)
            return {
                "status": "error",
                "error": str(e),
            }
    
    def is_simple_question(self, task: str) -> bool:
        """
        Determine if a task is a simple question (chat) or complex task (code generation).
        
        Simple questions:
        - Greetings (merhaba, selam, hi)
        - Direct questions (ne, kim, nedir, kaç)
        - Explanations (açıkla, anlat)
        
        Complex tasks:
        - Code requests (kod yaz, uygulama, API)
        - File operations (dosya, create, implement)
        - Project requests (proje, sistem)
        """
        task_lower = task.lower().strip()
        
        # Simple greeting patterns
        simple_patterns = [
            'merhaba', 'selam', 'hi', 'hello', 'hey', 'nasılsın', 'naber',
            'sen kimsin', 'who are you', 'adın ne', 'what is your name',
            'ne yapabilirsin', 'what can you do', 'ne yapıyorsun', 'what are you doing',
            'kaç eder', 'kaç yapar', 'hesapla',  # Math questions
            'ne demek', 'nedir', 'açıkla', 'anlat',  # Explanations
            'teşekkür', 'thanks', 'sağol',
            # Question words - direct questions (check these first before complex patterns)
            'hangi', 'which', 'what', 'ne', 'kim', 'who', 'where', 'nerede',
            'when', 'ne zaman', 'why', 'neden', 'how', 'nasıl',
            # Model/LLM related questions
            'hangi model', 'which model', 'what model', 'model nedir',
            'hangi llm', 'which llm', 'what llm',
        ]
        
        # Complex task patterns (require code generation)
        complex_patterns = [
            'kod yaz', 'code', 'uygulama yaz', 'program yaz',
            'api', 'endpoint', 'database', 'veritabanı',
            'dosya oluştur', 'create file', 'implement',
            'proje', 'project', 'sistem', 'system',
            'web', 'frontend', 'backend', 'full-stack',
            # Action words that indicate creation/building
            ' yap', 'yapın', 'yapar mısın', 'yapar misin',
            'oluştur', 'kur', 'hazırla',
            'geliştir', 'develop', 'build', 'make',
            # UI/App related
            'arayüz', 'dashboard', 'interface', 'ui',
            'sayfa', 'page', 'form', 'tablo', 'table',
            'hesap makinesi', 'calculator',
            # File types
            'html', 'css', 'javascript', '.py', '.php',
        ]
        
        # IMPORTANT: Check simple patterns FIRST before complex patterns
        # This ensures questions like "ne yapabilirsin" are detected as simple
        # even if they contain words that might match complex patterns
        
        # Check if it matches simple patterns
        for pattern in simple_patterns:
            if pattern in task_lower:
                return True  # Simple question
        
        # Check if it matches complex patterns
        for pattern in complex_patterns:
            if pattern in task_lower:
                return False  # Complex task
        
        # Default: if short (< 50 chars) and no code keywords, treat as simple
        # Be more aggressive in detecting simple questions
        if len(task) < 50:
            # Check if it contains question words
            question_words = ['hangi', 'which', 'what', 'ne', 'kim', 'who', 'where', 'nerede', 
                            'when', 'ne zaman', 'why', 'neden', 'how', 'nasıl', 'nedir', 'kaç']
            has_question_word = any(qw in task_lower for qw in question_words)
            
            # Check if it doesn't have action words
            action_words = ['yaz', 'oluştur', 'create', 'build', 'yap', 'make', 'kur', 'hazırla', 
                          'geliştir', 'develop', 'implement', 'kod', 'code']
            has_action_word = any(aw in task_lower for aw in action_words)
            
            # If it has question words and no action words, it's a simple question
            if has_question_word and not has_action_word:
                return True
            
            # If it's very short and has no action words, treat as simple
            if len(task) < 30 and not has_action_word:
                return True
            
        return False  # Default to complex for longer tasks or uncertain cases
    
    async def shutdown(self):
        """Shutdown the team and cleanup resources."""
        if self._team is not None:
            logger.info("Shutting down MGXStyleTeam")
            # Add any cleanup logic if needed
            self._team = None
    
    @asynccontextmanager
    async def get_team_context(self):
        """
        Context manager for team operations.
        
        Usage:
            async with team_provider.get_team_context() as team:
                result = await team.run(task)
        """
        team = await self.get_team()
        try:
            yield team
        except Exception as e:
            logger.error(f"Team operation failed: {str(e)}")
            raise
    
    def __str__(self) -> str:
        """String representation."""
        return f"MGXTeamProvider(config={self.config})"


# Global provider instance (lazy-initialized)
_provider: Optional[MGXTeamProvider] = None


def get_team_provider() -> MGXTeamProvider:
    """
    Get the global team provider instance.
    
    Usage in FastAPI routers:
        from backend.services import get_team_provider
        
        @router.post("/tasks")
        async def create_task(task: str):
            provider = get_team_provider()
            result = await provider.run_task(task)
            return result
    """
    global _provider
    if _provider is None:
        _provider = MGXTeamProvider()
    return _provider


def set_team_provider(provider: MGXTeamProvider):
    """Set the global team provider instance (for testing)."""
    global _provider
    _provider = provider


__all__ = ['MGXTeamProvider', 'get_team_provider', 'set_team_provider']
