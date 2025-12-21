# -*- coding: utf-8 -*-
"""
MGX Agent Actions Module

LLM çağrıları yapan Action sınıfları:
- AnalyzeTask: Görev karmaşıklık analizi
- DraftPlan: Görev planı taslağı
- WriteCode: Kod yazma
- WriteTest: Test yazma
- ReviewCode: Kod inceleme
"""

import os
import re
from datetime import datetime, timezone
from typing import List, Tuple, Optional

from tenacity import retry, stop_after_attempt, wait_exponential, retry_if_exception_type
from metagpt.actions import Action
from metagpt.logs import logger

from mgx_observability import (
    ObservabilityConfig,
    get_langsmith_logger,
    record_exception,
    set_span_attributes,
    start_span,
)


def llm_retry():
    """LLM çağrıları için retry decorator"""
    return retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=2, max=10),
        retry=retry_if_exception_type((Exception,)),
        before_sleep=lambda retry_state: logger.warning(
            f"⚠️ LLM hatası, yeniden deneniyor... (Deneme {retry_state.attempt_number}/3)"
        )
    )


def print_step_progress(step: int, total: int, description: str, role=None):
    """Adım adım progress göster
    
    Args:
        step: Mevcut adım
        total: Toplam adım
        description: Açıklama
        role: Role instance (team referansı için)
    """
    # Eğer role'un team referansı varsa onu kullan (config kontrolü için)
    if role and hasattr(role, '_team_ref') and hasattr(role._team_ref, '_print_progress'):
        role._team_ref._print_progress(step, total, description)
        return
    
    # Fallback: Global fonksiyon (eski davranış)
    bar_length = 20
    filled = int(bar_length * step / total)
    bar = "█" * filled + "░" * (bar_length - filled)
    percent = int(100 * step / total)
    print(f"\r[{bar}] {percent}% - {description}", end="", flush=True)
    if step == total:
        print()  # Yeni satır


def print_phase_header(phase: str, emoji: str = "🔄"):
    """Faz başlığı yazdır"""
    print(f"\n{'='*60}")
    print(f"{emoji} {phase}")
    print(f"{'='*60}")


def _env_flag(name: str) -> bool:
    return str(os.getenv(name, "")).strip().lower() in {"1", "true", "yes", "on"}


async def aask_with_observability(action: Action, prompt: str) -> str:
    action_name = getattr(action, "name", action.__class__.__name__)

    cfg = ObservabilityConfig(
        langsmith_enabled=_env_flag("LANGSMITH_ENABLED"),
        langsmith_api_key=os.getenv("LANGSMITH_API_KEY") or os.getenv("LANGCHAIN_API_KEY"),
        langsmith_project=os.getenv("LANGSMITH_PROJECT") or "mgx-agent",
        langsmith_endpoint=os.getenv("LANGSMITH_ENDPOINT"),
    )
    langsmith_logger = get_langsmith_logger(cfg)

    started_at = datetime.now(timezone.utc)

    async with start_span(
        "mgx.aask",
        attributes={
            "mgx.action": action_name,
            "prompt.length": len(prompt),
        },
    ) as span:
        try:
            rsp = await action._aask(prompt)
            set_span_attributes(span, {"output.length": len(rsp) if rsp is not None else 0})
        except Exception as e:
            record_exception(span, e)
            if langsmith_logger is not None:
                await langsmith_logger.log_llm_call(
                    name=f"mgx.{action_name}",
                    provider="metagpt",
                    model="unknown",
                    prompt=prompt,
                    output="",
                    error=str(e),
                    start_time=started_at,
                    end_time=datetime.now(timezone.utc),
                    metadata={"action": action_name},
                )
            raise

    if langsmith_logger is not None:
        await langsmith_logger.log_llm_call(
            name=f"mgx.{action_name}",
            provider="metagpt",
            model="unknown",
            prompt=prompt,
            output=rsp or "",
            start_time=started_at,
            end_time=datetime.now(timezone.utc),
            metadata={"action": action_name},
        )

    return rsp


class AnalyzeTask(Action):
    """Görevi analiz et (stack-aware)"""
    
    PROMPT_TEMPLATE: str = """Görev: {task}
{stack_context}

Aşağıdaki formatı kullanarak görevi analiz et:

KARMAŞIKLIK: [XS/S/M/L/XL]
ÖNERİLEN_STACK: [stack_id] - [kısa gerekçe]
DOSYA_MANİFESTO:
- [dosya1.ext]: [açıklama]
- [dosya2.ext]: [açıklama]
TEST_STRATEJİSİ: [hangi test framework kullanılacak ve kaç test]

Kurallar:
- KARMAŞIKLIK: XS (tek fonksiyon), S (birkaç fonksiyon), M (modül), L (çoklu modül), XL (sistem)
- ÖNERİLEN_STACK: {available_stacks} listesinden seç
- DOSYA_MANİFESTO: Oluşturulacak/değiştirilecek dosyaları listele
- TEST_STRATEJİSİ: Hangi test framework ve kaç test yazılacağını belirt"""
    
    name: str = "AnalyzeTask"
    
    @llm_retry()
    async def run(self, task: str, target_stack: str = None) -> str:
        try:
            # Stack context oluştur
            from .stack_specs import STACK_SPECS, infer_stack_from_task
            
            available_stacks = ", ".join(STACK_SPECS.keys())
            
            if target_stack:
                stack_context = f"\nHedef Stack: {target_stack}"
            else:
                inferred = infer_stack_from_task(task)
                stack_context = f"\nÖnerilen Stack: {inferred} (görev açıklamasından tahmin edildi)"
            
            prompt = self.PROMPT_TEMPLATE.format(
                task=task,
                stack_context=stack_context,
                available_stacks=available_stacks
            )
            rsp = await aask_with_observability(self, prompt)
            return rsp
        except Exception as e:
            logger.error(f"❌ AnalyzeTask hatası: {e}")
            raise


class DraftPlan(Action):
    """Plan taslağı oluştur (stack-aware)"""
    
    PROMPT_TEMPLATE: str = """Görev: {task}

Analiz: {analysis}
{stack_info}

Kısa ve öz plan yaz. SADECE şu formatı kullan:

1. Kod yaz ({stack_name}) - Alex (Engineer)
2. Test yaz ({test_framework}) - Bob (Tester)  
3. Review yap - Charlie (Reviewer)

Açıklama veya detay YAZMA. SADECE numaralı listeyi yaz."""
    
    name: str = "DraftPlan"
    
    @llm_retry()
    async def run(self, task: str, analysis: str, target_stack: str = None) -> str:
        try:
            # Stack bilgisi ekle
            from .stack_specs import get_stack_spec, infer_stack_from_task
            
            if not target_stack:
                target_stack = infer_stack_from_task(task)
            
            spec = get_stack_spec(target_stack)
            if spec:
                stack_info = f"\nStack: {spec.name}"
                stack_name = spec.language.upper()
                test_framework = spec.test_framework
            else:
                stack_info = ""
                stack_name = "Python"
                test_framework = "pytest"
            
            prompt = self.PROMPT_TEMPLATE.format(
                task=task,
                analysis=analysis,
                stack_info=stack_info,
                stack_name=stack_name,
                test_framework=test_framework
            )
            rsp = await aask_with_observability(self, prompt)
            return rsp
        except Exception as e:
            logger.error(f"❌ DraftPlan hatası: {e}")
            raise


class WriteCode(Action):
    """Kod yaz (stack-aware, multi-language, FILE manifest)"""
    
    PROMPT_TEMPLATE: str = """
Görev: {instruction}
Plan: {plan}
Stack: {stack_name}
Dil: {language}
{constraints_section}

{review_section}

{strict_mode_instructions}

ADIM 1 - DÜŞÜN (YALNIZCA METİN):

- Bu görevi nasıl çözeceğini 3–7 madde halinde kısaca açıkla.
- Hangi fonksiyonları/component'leri yazacağını ve hangi kütüphaneleri kullanacağını belirt.
- Edge case (uç durum) olarak neleri dikkate alacağını yaz.
- Hangi dosyaları oluşturacağını/değiştireceğini listele.
- Bu düşünce kısmında HİÇBİR KOD yazma.

ADIM 2 - KODLA (FILE MANİFEST FORMATINI KULLAN):

{file_format_instructions}

{revision_instructions}
"""
    
    FILE_FORMAT_STRICT: str = """
Aşağıdaki FILE manifest formatını KULLAN (açıklama yasak, sadece dosyalar):

FILE: path/to/file1.{ext}
[dosya1 içeriği]

FILE: path/to/file2.{ext}
[dosya2 içeriği]

ÖNEMLİ: 
- HER DOSYA "FILE: " ile başlamalı
- Dosya yolları stack yapısına uygun olmalı: {expected_structure}
- Açıklama veya yorum YAZMA, sadece FILE blokları
"""
    
    FILE_FORMAT_NORMAL: str = """
Aşağıdaki FILE manifest formatını veya code block formatını kullan:

SEÇENEK 1 - FILE Manifest (çoklu dosya için):
FILE: path/to/file1.{ext}
[dosya1 içeriği]

FILE: path/to/file2.{ext}
[dosya2 içeriği]

SEÇENEK 2 - Code Block (tek dosya için):
```{language}
# kod buraya
```

Önerilen dosya yapısı: {expected_structure}
"""
    
    name: str = "WriteCode"
    
    @llm_retry()
    async def run(
        self, 
        instruction: str, 
        plan: str = "", 
        review_notes: str = "",
        target_stack: str = None,
        constraints: list = None,
        strict_mode: bool = False,
        enable_validation: bool = True,
        max_validation_retries: int = 2
    ) -> str:
        try:
            # Stack bilgisi
            from .stack_specs import get_stack_spec, infer_stack_from_task
            from .guardrails import validate_output_constraints, build_revision_prompt
            
            if not target_stack:
                target_stack = infer_stack_from_task(instruction)
            
            spec = get_stack_spec(target_stack)
            if spec:
                stack_name = spec.name
                language = spec.language
                ext = spec.file_extensions[0] if spec.file_extensions else "txt"
                expected_structure = ", ".join(list(spec.project_layout.keys())[:5])
            else:
                stack_name = "Python"
                language = "python"
                ext = ".py"
                expected_structure = "src/, tests/"
            
            # Constraints
            constraints_section = ""
            if constraints:
                constraints_section = f"\nKısıtlamalar:\n" + "\n".join(f"- {c}" for c in constraints)
            
            # Review notları
            review_section = ""
            revision_instructions = ""
            if review_notes and review_notes.strip():
                review_section = f"""
Review Notları (İyileştirme Önerileri):
{review_notes}
"""
                revision_instructions = f"""
ÖNEMLİ: Bu bir düzeltme turu. Yukarıdaki review notlarını dikkate alarak mevcut kodu GÜNCELLE / İYİLEŞTİR.
Orijinal görevi unutma: {instruction}
"""
            
            # Strict mode
            strict_mode_instructions = ""
            if strict_mode:
                file_format_instructions = self.FILE_FORMAT_STRICT.format(
                    ext=ext,
                    expected_structure=expected_structure
                )
                strict_mode_instructions = "⚠️ STRICT MODE: Sadece FILE blokları yaz, hiçbir açıklama ekleme!"
            else:
                file_format_instructions = self.FILE_FORMAT_NORMAL.format(
                    ext=ext,
                    language=language,
                    expected_structure=expected_structure
                )
            
            # Main generation loop with validation retry
            validation_retry_count = 0
            final_output = None
            validation_result = None
            
            while validation_retry_count <= max_validation_retries:
                prompt = self.PROMPT_TEMPLATE.format(
                    instruction=instruction,
                    plan=plan,
                    stack_name=stack_name,
                    language=language,
                    constraints_section=constraints_section,
                    review_section=review_section,
                    strict_mode_instructions=strict_mode_instructions,
                    file_format_instructions=file_format_instructions,
                    revision_instructions=revision_instructions
                )
                rsp = await aask_with_observability(self, prompt)
                
                # Parse output based on mode
                if strict_mode:
                    output = rsp  # FILE manifest formatında
                else:
                    output = self._parse_code(rsp, language)
                
                # Run validation if enabled
                if enable_validation:
                    validation_result = validate_output_constraints(
                        generated_output=output,
                        stack_spec=spec,
                        constraints=constraints,
                        strict_mode=strict_mode
                    )
                    
                    if validation_result.is_valid:
                        logger.info(f"✅ Output validation passed: {validation_result.summary()}")
                        final_output = output
                        break
                    else:
                        # Validation failed
                        logger.warning(f"❌ Output validation failed (attempt {validation_retry_count + 1}/{max_validation_retries + 1})")
                        logger.warning(f"Errors: {len(validation_result.errors)}, Warnings: {len(validation_result.warnings)}")
                        
                        for i, error in enumerate(validation_result.errors[:5], 1):
                            logger.warning(f"  {i}. {error}")
                        
                        if validation_retry_count < max_validation_retries:
                            # Build revision prompt with validation errors
                            revision_prompt = build_revision_prompt(validation_result, instruction)
                            review_notes = revision_prompt
                            validation_retry_count += 1
                            logger.info(f"🔄 Retrying with validation error feedback...")
                        else:
                            # Max retries reached
                            logger.error(f"❌ Validation failed after {max_validation_retries + 1} attempts")
                            logger.error("Returning output with validation errors (marked as NEEDS_INFO)")
                            final_output = output
                            break
                else:
                    # Validation disabled
                    final_output = output
                    break
            
            # Log final validation status
            if enable_validation and validation_result and not validation_result.is_valid:
                error_summary = "\n".join(f"  - {e}" for e in validation_result.errors)
                logger.error(
                    f"⚠️ WriteCode returning output with validation errors:\n{error_summary}\n"
                    f"Task may require manual intervention (NEEDS_INFO)"
                )
            
            # Auto-format output if in FILE manifest mode
            if final_output and "FILE:" in final_output:
                final_output = self._format_output(final_output, target_stack, language)
            
            # Phase 11: Sandbox execution integration
            await self._execute_sandbox_testing(final_output, target_stack, language)
            
            return final_output
        except Exception as e:
            logger.error(f"❌ WriteCode hatası: {e}")
            raise
    
    def _format_output(self, output: str, stack: str, language: str) -> str:
        """Format the output (placeholder for future implementation)."""
        return output

    async def _execute_sandbox_testing(
        self, 
        generated_code: str, 
        target_stack: str, 
        language: str
    ) -> bool:
        """
        Execute generated code in sandbox for testing and validation.
        
        This is part of Phase 11: Sandboxed Code Runner integration.
        Automatically runs tests after code generation to validate functionality.
        
        Args:
            generated_code: The generated code content
            target_stack: Technology stack identifier
            language: Programming language
            
        Returns:
            True if testing passed, False otherwise
        """
        try:
            # Only run sandbox testing in development/testing environments
            import os
            if os.getenv("DISABLE_SANDBOX_TESTING", "").lower() in ("true", "1", "yes"):
                logger.debug("🔍 Sandbox testing disabled via environment variable")
                return True
            
            logger.debug("🔍 Running sandbox testing for generated code")
            
            # Extract files from FILE manifest if present
            files = WriteCode._parse_file_manifest(generated_code)
            if not files:
                logger.debug("🔍 No files to test - single code block")
                return True
            
            # Map stack to sandbox language
            language_map = {
                'python': 'python',
                'nodejs': 'javascript',
                'javascript': 'javascript', 
                'typescript': 'javascript',
                'php': 'php',
                'react': 'javascript',
                'vue': 'javascript',
                'express': 'javascript',
            }
            
            sandbox_language = language_map.get(target_stack.lower(), language.lower())
            
            # Determine test command based on language and files
            test_command = self._determine_test_command(files, sandbox_language, target_stack)
            
            if not test_command:
                logger.debug("🔍 No test command determined for this stack/language")
                return True
            
            # Get the main code file content for execution
            main_code = self._extract_main_code(files, sandbox_language)
            if not main_code:
                logger.debug("🔍 No main code file found to test")
                return True
            
            # Execute in sandbox
            success = await self._run_sandbox_execution(
                code=main_code,
                command=test_command,
                language=sandbox_language,
                timeout=60  # 60 second timeout for testing
            )
            
            if success:
                logger.info("✅ Sandbox testing passed")
            else:
                logger.warning("⚠️ Sandbox testing failed - check logs for details")
                return False
            
            # Phase 12: Run Quality Gates after successful sandbox execution
            quality_gate_success = await self._run_quality_gates_after_sandbox(
                files=files,
                workspace_id="test-workspace",  # TODO: Get from context
                project_id="test-project",  # TODO: Get from context
                task_run_id=None  # TODO: Get from context
            )
            
            if not quality_gate_success:
                logger.warning("⚠️ Quality gates failed - code needs revision")
                return False
            
            logger.info("✅ Quality gates passed")
            return True
            
        except Exception as e:
            logger.warning(f"⚠️ Sandbox testing error (non-blocking): {e}")
            return True  # Don't fail the main task if testing fails
    
    def _determine_test_command(
        self, 
        files: List[Tuple[str, str]], 
        language: str, 
        stack: str
    ) -> Optional[str]:
        """
        Determine appropriate test command for the generated code.
        
        Args:
            files: List of (filepath, content) tuples
            language: Programming language
            stack: Technology stack
            
        Returns:
            Test command string or None
        """
        # Check for existing test files in FILE manifest
        test_files = [f[0] for f in files if any(test_indicator in f[0].lower() 
                       for test_indicator in ['test_', '_test.', 'spec.', '.test.', '.spec.'])]
        
        if test_files:
            # Test files exist, use them
            if language == 'python':
                # Check for pytest
                if any('pytest' in f.lower() or 'test_' in f.lower() for f in test_files):
                    return "python -m pytest"
                return "python -m unittest discover"
            elif language == 'javascript':
                # Check for package.json
                package_json_files = [f for f in files if 'package.json' in f[0]]
                if package_json_files:
                    return "npm test"
                return "node test.js"
            elif language == 'php':
                return "vendor/bin/phpunit"
        
        # No test files found - run basic syntax validation
        if language == 'python':
            # Try to compile the code for syntax validation
            try:
                import ast
                for file_path, content in files:
                    if file_path.endswith('.py'):
                        ast.parse(content)
                return None  # Syntax is valid, no additional testing needed
            except SyntaxError:
                return "python -m py_compile"
        
        elif language == 'javascript':
            # Basic Node.js syntax check
            return "node --check"
        
        elif language == 'php':
            # PHP syntax check
            return "php -l"
        
        return None
    
    def _extract_main_code(self, files: List[Tuple[str, str]], language: str) -> Optional[str]:
        """
        Extract main code file content for sandbox execution.
        
        Args:
            files: List of (filepath, content) tuples
            language: Programming language
            
        Returns:
            Main code content or None
        """
        # Language-specific main file patterns
        main_patterns = {
            'python': ['main.py', 'app.py', 'index.py', 'server.py', '__main__.py'],
            'javascript': ['main.js', 'app.js', 'index.js', 'server.js', 'app.js'],
            'php': ['index.php', 'main.php', 'app.php', 'server.php'],
        }
        
        # Look for main files
        main_files = []
        for file_path, content in files:
            file_name = file_path.split('/')[-1]
            if file_name in main_patterns.get(language, []):
                main_files.append((file_path, content))
        
        # If no main files found, take the first non-test file
        if not main_files:
            for file_path, content in files:
                if not any(test_indicator in file_path.lower() 
                          for test_indicator in ['test_', '_test.', 'spec.', '.test.', '.spec.']):
                    main_files.append((file_path, content))
                    break
        
        # Return the content of the first main file
        if main_files:
            return main_files[0][1]
        
        return None
    
    async def _run_sandbox_execution(
        self, 
        code: str, 
        command: str, 
        language: str, 
        timeout: int = 30
    ) -> bool:
        """
        Execute code in sandbox environment.
        
        Args:
            code: Source code to execute
            command: Command to run
            language: Programming language
            timeout: Execution timeout in seconds
            
        Returns:
            True if execution was successful
        """
        try:
            # Import sandbox runner only when needed
            try:
                from backend.services.sandbox import get_sandbox_runner
                runner = get_sandbox_runner()
            except ImportError:
                logger.debug("🔍 Sandbox runner not available - skipping execution")
                return True
            
            # Create execution ID
            import uuid
            execution_id = str(uuid.uuid4())
            
            # Execute in sandbox
            result = await runner.execute_code(
                execution_id=execution_id,
                code=code,
                command=command,
                language=language,
                timeout=timeout,
                memory_limit_mb=512,
                workspace_id="test-workspace",  # TODO: Get from context
                project_id="test-project",  # TODO: Get from context
            )
            
            # Log results
            if result.get('success'):
                logger.info(f"✅ Sandbox execution successful: {command}")
                if result.get('stdout'):
                    logger.debug(f"Output: {result['stdout'][:200]}")
                return True
            else:
                logger.warning(f"⚠️ Sandbox execution failed: {command}")
                if result.get('stderr'):
                    logger.warning(f"Error: {result['stderr'][:200]}")
                return False
                
        except Exception as e:
            logger.warning(f"⚠️ Sandbox execution error: {e}")
            return False
    
    async def _run_quality_gates_after_sandbox(
        self,
        files: List[Tuple[str, str]],
        workspace_id: str,
        project_id: str,
        task_run_id: Optional[str] = None
    ) -> bool:
        """
        Run quality gates after successful sandbox execution.
        
        Args:
            files: List of (filepath, content) tuples
            workspace_id: Workspace ID
            project_id: Project ID  
            task_run_id: Task run ID
            
        Returns:
            True if all quality gates pass
        """
        try:
            # Import quality gate manager
            try:
                from backend.services.quality_gates import get_gate_manager
                gate_manager = await get_gate_manager()
            except ImportError:
                logger.debug("🔍 Quality gate manager not available - skipping")
                return True
            
            # Determine which gates to run based on file types
            gate_types = self._determine_quality_gates_for_files(files)
            
            if not gate_types:
                logger.debug("🔍 No applicable quality gates found for these files")
                return True
            
            logger.info(f"🏗️ Running quality gates: {gate_types}")
            
            # Run quality gates
            result = await gate_manager.evaluate_gates(
                workspace_id=workspace_id,
                project_id=project_id,
                gate_types=gate_types,
                task_run_id=task_run_id,
                working_directory="/tmp/test",  # Use temp directory for testing
            )
            
            if not result.get("success", False):
                logger.warning(f"⚠️ Quality gate evaluation failed: {result.get('error', 'Unknown error')}")
                return False
            
            # Check if evaluation passed
            if result.get("passed", False):
                blocking_failures = result.get("blocking_failures", [])
                if blocking_failures:
                    logger.warning(f"⚠️ Quality gates failed with blocking failures: {blocking_failures}")
                    return False
                else:
                    logger.info("✅ All quality gates passed")
                    return True
            else:
                blocking_failures = result.get("blocking_failures", [])
                logger.warning(f"⚠️ Quality gates failed: {blocking_failures}")
                
                # Log detailed results for debugging
                for gate_type, gate_result in result.get("results", {}).items():
                    if not gate_result.get("passed", True):
                        logger.warning(f"  - {gate_type}: {gate_result.get('status', 'unknown')} - {gate_result.get('error_message', 'No details')}")
                
                return False
                
        except Exception as e:
            logger.warning(f"⚠️ Quality gate execution error: {e}")
            return False  # Fail closed - if quality gates can't run, assume failure
    
    def _determine_quality_gates_for_files(self, files: List[Tuple[str, str]]) -> List[str]:
        """
        Determine which quality gates to run based on file types.
        
        Args:
            files: List of (filepath, content) tuples
            
        Returns:
            List of gate types to run
        """
        gate_types = []
        file_extensions = set()
        
        # Collect file extensions
        for filepath, _ in files:
            if filepath:
                ext = filepath.split('.')[-1].lower() if '.' in filepath else ''
                if ext:
                    file_extensions.add(ext)
        
        # Determine gates based on file types
        if any(ext in file_extensions for ext in ['js', 'jsx', 'ts', 'tsx']):
            gate_types.extend(["lint", "security"])  # JavaScript/TypeScript files
        
        if any(ext in file_extensions for ext in ['py']):
            gate_types.extend(["lint", "coverage", "security", "complexity", "type_check"])  # Python files
        
        if any(ext in file_extensions for ext in ['php']):
            gate_types.extend(["lint", "coverage", "security", "complexity"])  # PHP files
        
        # Always include performance gate if there are any executable files
        if file_extensions:
            gate_types.append("performance")
        
        # Always include contract gate for any web/API projects
        if any(ext in file_extensions for ext in ['js', 'jsx', 'ts', 'tsx', 'py', 'php', 'go', 'java']):
            gate_types.append("contract")
        
        # Remove duplicates while preserving order
        return list(dict.fromkeys(gate_types))
    
    @staticmethod
    def _parse_file_manifest(manifest: str) -> List[Tuple[str, str]]:
        """
        Parse FILE manifest format into list of (filepath, content) tuples.
        
        Format:
        FILE: path/to/file1.ext
        [content line 1]
        [content line 2]
        
        FILE: path/to/file2.ext
        [content]
        
        Returns:
            List of (file_path, content) tuples
        """
        files = []
        current_file = None
        current_content = []
        
        for line in manifest.split('\n'):
            if line.startswith('FILE: '):
                # Save previous file if exists
                if current_file and current_content:
                    content = '\n'.join(current_content)
                    files.append((current_file, content))
                
                # Start new file
                current_file = line[6:].strip()  # Remove 'FILE: ' prefix
                current_content = []
            elif current_file:
                # Add line to current file
                current_content.append(line)
        
        # Save last file
        if current_file and current_content:
            content = '\n'.join(current_content).rstrip()
            files.append((current_file, content))
        
        return files
    
    @staticmethod
    def _parse_code(rsp: str, language: str = "python") -> str:
        """Code block'tan kodu çıkar (backward compatibility)"""
        # Önce FILE manifest formatını kontrol et
        if "FILE:" in rsp:
            return rsp  # FILE manifest formatında, olduğu gibi döndür
        
        # Dile özel pattern'ler
        patterns = [
            rf"```{language}(.*?)```",
            r"```(.*)```",
        ]
        
        for pattern in patterns:
            match = re.search(pattern, rsp, re.DOTALL)
            if match:
                return match.group(1).strip()
        
        # Hiçbir pattern match etmezse, olduğu gibe döndür
        return rsp


class WriteTest(Action):
    """Test yaz (stack-aware)"""
    
    PROMPT_TEMPLATE: str = """
    Kod:
    {code}
    
    Stack: {stack_name}
    Test Framework: {test_framework}
    
    ÖNEMLİ: Bu kod için {test_framework} kullanarak TAM OLARAK {k} ADET unit test yaz.
    DAHA FAZLA YAZMA! Sadece {k} adet test yaz.
    
    Kurallar:
    1. TAM OLARAK {k} adet test yaz (daha fazla değil!)
    2. Her test farklı bir senaryoyu test etmeli:
       - Pozitif senaryo (normal kullanım)
       - Negatif senaryo (hata durumları)
       - Edge case (sınır değerleri)
    3. Aynı testi tekrar yazma - her test benzersiz olmalı
    4. Test isimleri açıklayıcı olsun
    5. {test_framework} syntax'ını kullan
    
    Sadece {k} adet test yaz, daha fazla değil!
    
    ```{language}
    {test_template}
    ```
    
    UYARI: Sadece {k} adet test yaz, daha fazla yazma!
    """
    
    name: str = "WriteTest"
    
    @staticmethod
    def _parse_code(rsp: str, language: str = "python") -> str:
        """Code block'tan test kodunu çıkar"""
        patterns = [
            rf"```{language}(.*?)```",
            r"```(.*)```",
        ]
        
        for pattern in patterns:
            match = re.search(pattern, rsp, re.DOTALL)
            if match:
                return match.group(1).strip()
        
        return rsp.strip()
    
    @staticmethod
    def _limit_tests(code: str, k: int) -> str:
        """
        Test kodundan sadece ilk k adet test fonksiyonunu al.
        LLM daha fazla test yazsa bile sadece k adet test döndürür.
        
        Args:
            code: Test kodu
            k: Maksimum test sayısı
            
        Returns:
            Sadece k adet test içeren kod
        """
        lines = code.splitlines()
        result = []
        test_count = 0
        in_test_function = False
        
        for i, line in enumerate(lines):
            # Test fonksiyonu başlangıcını tespit et
            if re.match(r'^\s*def\s+test_', line):
                if test_count >= k:
                    # K adet test bulundu, daha fazlasını alma
                    break
                test_count += 1
                in_test_function = True
                result.append(line)
            elif in_test_function:
                # Test fonksiyonu içindeyiz
                result.append(line)
                # Bir sonraki test fonksiyonu veya dosya sonu gelirse dur
                if i + 1 < len(lines):
                    next_line = lines[i + 1]
                    if re.match(r'^\s*def\s+test_', next_line):
                        # Bir sonraki test başlıyor, eğer k adet test bulunduysa dur
                        if test_count >= k:
                            break
            else:
                # Test fonksiyonu dışındayız (import, class tanımları vs.)
                result.append(line)
        
        # Eğer hiç test bulunamadıysa orijinal kodu döndür
        if test_count == 0:
            return code
        
        return "\n".join(result)
    
    def _get_test_template(self, test_framework: str, language: str, k: int) -> str:
        """Test framework'e göre template döndür"""
        templates = {
            "pytest": """import pytest

# Test 1: [açıklama]
def test_1():
    # kod

# Test 2: [açıklama]
def test_2():
    # kod

# Test {k}: [açıklama]
def test_{k}():
    # kod""",
            
            "jest": """import {{ describe, it, expect }} from '@jest/globals';

describe('TestSuite', () => {{
  it('Test 1: [açıklama]', () => {{
    // kod
  }});
  
  it('Test 2: [açıklama]', () => {{
    // kod
  }});
  
  it('Test {k}: [açıklama]', () => {{
    // kod
  }});
}});""",
            
            "vitest": """import {{ describe, it, expect }} from 'vitest';

describe('TestSuite', () => {{
  it('Test 1: [açıklama]', () => {{
    // kod
  }});
  
  it('Test 2: [açıklama]', () => {{
    // kod
  }});
  
  it('Test {k}: [açıklama]', () => {{
    // kod
  }});
}});""",
            
            "phpunit": """<?php

use PHPUnit\\Framework\\TestCase;

class MyTest extends TestCase
{{
    public function test1(): void
    {{
        // kod
    }}
    
    public function test2(): void
    {{
        // kod
    }}
    
    public function test{k}(): void
    {{
        // kod
    }}
}}""",
        }
        
        template = templates.get(test_framework.lower(), templates["pytest"])
        return template.replace("{k}", str(k))
    
    @llm_retry()
    async def run(self, code: str, k: int = 3, target_stack: str = None) -> str:
        try:
            # Stack bilgisi
            from .stack_specs import get_stack_spec, infer_stack_from_task
            
            if target_stack:
                spec = get_stack_spec(target_stack)
                if spec:
                    test_framework = spec.test_framework
                    language = spec.language
                    stack_name = spec.name
                else:
                    test_framework = "pytest"
                    language = "python"
                    stack_name = "Python"
            else:
                test_framework = "pytest"
                language = "python"
                stack_name = "Python"
            
            test_template = self._get_test_template(test_framework, language, k)
            
            prompt = self.PROMPT_TEMPLATE.format(
                code=code,
                k=k,
                stack_name=stack_name,
                test_framework=test_framework,
                language=language,
                test_template=test_template
            )
            rsp = await aask_with_observability(self, prompt)
            raw_code = self._parse_code(rsp, language)
            # Post-process: Test sayısını k ile sınırla (LLM daha fazla yazsa bile)
            limited_code = self._limit_tests(raw_code, k)
            logger.debug(f"📊 WriteTest: {k} adet test sınırı uygulandı ({test_framework})")
            return limited_code
        except Exception as e:
            logger.error(f"❌ WriteTest hatası: {e}")
            raise


class ReviewCode(Action):
    """Kodu incele ve geri bildirim ver (stack-aware)"""
    
    PROMPT_TEMPLATE: str = """
    Kod:
    {code}
    
    Testler:
    {tests}
    
    Stack: {stack_name}
    {stack_specific_checks}
    
    Bu kodu ve testleri DİKKATLİCE incele:
    1. Kod kalitesi nasıl? Hata yönetimi var mı? Input validation var mı?
    2. Test coverage yeterli mi? Edge case'ler test edilmiş mi?
    3. Docstring'ler/Comment'ler var mı? Kod dokümantasyonu yeterli mi?
    4. Stack-specific best practices uygulanmış mı?
    5. Güvenlik: Environment variables, secrets, input sanitization kontrol edilmiş mi?
    6. Build/Test/Run komutları doğru mu? (package.json, composer.json, requirements.txt vs.)
    7. İyileştirme gereken noktalar var mı?
    
    ÖNEMLİ: Eğer kodda eksiklikler, hatalar veya iyileştirme gereken noktalar varsa MUTLAKA "DEĞİŞİKLİK GEREKLİ" yaz.
    Sadece kod mükemmel ve hiçbir sorun yoksa "ONAYLANDI" yaz.
    
    SONUÇ: [ONAYLANDI / DEĞİŞİKLİK GEREKLİ]
    
    YORUMLAR:
    - [yorum 1]
    - [yorum 2]
    - [yorum 3]
    """
    
    name: str = "ReviewCode"
    
    def _get_stack_checks(self, stack_id: str) -> str:
        """Stack-specific kontrol listesi"""
        checks = {
            "express-ts": """
Kontrol listesi (Express-TS):
- Middleware sırası doğru mu? (body-parser, cors, helmet)
- Error handling middleware var mı?
- TypeScript tipleri tam mı?
- .env için dotenv kullanılmış mı?""",
            
            "nestjs": """
Kontrol listesi (NestJS):
- Module/Controller/Service yapısı doğru mu?
- Dependency Injection kullanılmış mı?
- DTO validation var mı?
- Exception filters uygun mu?""",
            
            "laravel": """
Kontrol listesi (Laravel):
- Eloquent relationships doğru mu?
- Request validation kullanılmış mı?
- Route tanımları RESTful mi?
- Migration dosyaları var mı?""",
            
            "fastapi": """
Kontrol listesi (FastAPI):
- Pydantic model'ler kullanılmış mı?
- Async/await doğru kullanılmış mı?
- Dependency Injection var mı?
- Response model'ler tanımlanmış mı?""",
            
            "react-vite": """
Kontrol listesi (React-Vite):
- Component yapısı temiz mi?
- Props type checking (TypeScript) var mı?
- State management doğru mu?
- useEffect dependency array'leri doğru mu?""",
            
            "nextjs": """
Kontrol listesi (Next.js):
- App Router / Pages Router kullanımı doğru mu?
- Server/Client component ayrımı yapılmış mı?
- API routes doğru tanımlanmış mı?
- Metadata/SEO ayarları var mı?""",
            
            "vue-vite": """
Kontrol listesi (Vue-Vite):
- Composition API doğru kullanılmış mı?
- Reactive state management uygun mu?
- Component props/emits tanımlanmış mı?
- Script setup syntax kullanılmış mı?""",
        }
        
        return checks.get(stack_id, "")
    
    @llm_retry()
    async def run(self, code: str, tests: str, target_stack: str = None) -> str:
        try:
            # Stack bilgisi
            from .stack_specs import get_stack_spec
            
            if target_stack:
                spec = get_stack_spec(target_stack)
                if spec:
                    stack_name = spec.name
                    stack_specific_checks = self._get_stack_checks(target_stack)
                else:
                    stack_name = "Python"
                    stack_specific_checks = ""
            else:
                stack_name = "Python"
                stack_specific_checks = ""
            
            prompt = self.PROMPT_TEMPLATE.format(
                code=code,
                tests=tests,
                stack_name=stack_name,
                stack_specific_checks=stack_specific_checks
            )
            rsp = await self._aask(prompt)
            return rsp
        except Exception as e:
            logger.error(f"❌ ReviewCode hatası: {e}")
            raise
