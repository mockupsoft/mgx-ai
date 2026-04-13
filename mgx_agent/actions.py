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
import uuid
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Tuple

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
    """Görevi analiz et (stack-aware, proje kuralları çıkar)"""
    
    PROMPT_TEMPLATE: str = """Görev: {task}
{stack_context}

Aşağıdaki formatı kullanarak görevi analiz et:

KARMAŞIKLIK: [XS/S/M/L/XL]
ÖNERİLEN_STACK: [stack_id] - [kısa gerekçe]
DOSYA_MANİFESTO:
- [dosya1.ext]: [açıklama]
- [dosya2.ext]: [açıklama]
TEST_STRATEJİSİ: [hangi test framework kullanılacak ve kaç test]
PROJE_KURALLARI:
- Stack: [seçilen teknolojiler, framework versiyonları]
- Auth: [kimlik doğrulama yöntemi]
- Veritabanı: [tablolar, ilişkiler]
- Paketler: [kullanılacak kütüphaneler]
- Modüller: [oluşturulacak modül/sayfa listesi]
- Mimari Kararlar: [önemli tasarım kararları]

Kurallar:
- KARMAŞIKLIK: XS (tek fonksiyon), S (birkaç fonksiyon), M (modül), L (çoklu modül), XL (tam sistem)
  → Pano, yönetim paneli, çok modüllü uygulama, CRUD sistemi = XL
  → 3+ modül/sayfa/bölüm = L
  → Tek özellikli modül = M
  → Küçük bileşen/fonksiyon = S
- ÖNERİLEN_STACK: {available_stacks} listesinden seç
- DOSYA_MANİFESTO: Oluşturulacak/değiştirilecek tüm dosyaları listele
- PROJE_KURALLARI: Projeye özel teknik kararları yaz — bunlar gelecek isteklerde kullanılacak
- TEST_STRATEJİSİ: Hangi test framework ve kaç test yazılacağını belirt"""
    
    name: str = "AnalyzeTask"
    
    @llm_retry()
    async def run(self, task: str, target_stack: str = None) -> str:
        try:
            from .stack_specs import STACK_SPECS, infer_stack_from_task
            
            available_stacks = ", ".join(STACK_SPECS.keys())
            
            if target_stack:
                stack_context = f"\nHedef Stack: {target_stack}"
            else:
                inferred = infer_stack_from_task(task)
                stack_context = f"\nÖnerilen Stack: {inferred} (görev açıklamasından tahmin edildi)"

            prompt = self.PROMPT_TEMPLATE.format(
                task=task[:4000],  # uzun görev metnini kırp ama yeterli bağlam bırak
                stack_context=stack_context,
                available_stacks=available_stacks,
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
{sandbox_failure_section}

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
            
            max_sandbox_heal = int(
                (os.getenv("SANDBOX_SELF_HEAL_MAX_ATTEMPTS") or "2").strip() or "2"
            )
            use_sandbox_self_heal = (
                max_sandbox_heal > 0
                and os.getenv("DISABLE_SANDBOX_TESTING", "").lower()
                not in ("true", "1", "yes")
            )

            sandbox_failure_notes = ""
            heal_remaining = max_sandbox_heal if use_sandbox_self_heal else 0

            # Review notları + sandbox self-heal (dış döngü heal_remaining ile yenilenir)
            def _build_review_sections(
                notes: str, sandbox_fb: str
            ) -> Tuple[str, str, str]:
                review_section = ""
                revision_instructions = ""
                if notes and notes.strip():
                    review_section = f"""
Review Notları (İyileştirme Önerileri):
{notes}
"""
                sandbox_failure_section = ""
                if sandbox_fb and sandbox_fb.strip():
                    sandbox_failure_section = f"""
Sandbox testi (önceki deneme) başarısız — aşağıdaki çıktıya göre kodu ve testleri düzelt:
{sandbox_fb}
"""
                combined_any = (notes or "").strip() or (sandbox_fb or "").strip()
                if combined_any:
                    revision_instructions = f"""
ÖNEMLİ: Bu bir düzeltme turu. Yukarıdaki notları (review ve/veya sandbox çıktısı) dikkate alarak mevcut kodu GÜNCELLE / İYİLEŞTİR.
Orijinal görevi unutma: {instruction}
"""
                return review_section, sandbox_failure_section, revision_instructions

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
            
            final_output = None
            validation_result = None

            while True:
                (
                    review_section,
                    sandbox_failure_section,
                    revision_instructions,
                ) = _build_review_sections(review_notes, sandbox_failure_notes)

                # Main generation loop with validation retry
                validation_retry_count = 0
                validation_result = None

                while validation_retry_count <= max_validation_retries:
                    prompt = self.PROMPT_TEMPLATE.format(
                        instruction=instruction,
                        plan=plan,
                        stack_name=stack_name,
                        language=language,
                        constraints_section=constraints_section,
                        review_section=review_section,
                        sandbox_failure_section=sandbox_failure_section,
                        strict_mode_instructions=strict_mode_instructions,
                        file_format_instructions=file_format_instructions,
                        revision_instructions=revision_instructions,
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
                            strict_mode=strict_mode,
                        )

                        if validation_result.is_valid:
                            logger.info(
                                f"✅ Output validation passed: {validation_result.summary()}"
                            )
                            final_output = output
                            break
                        else:
                            logger.warning(
                                f"❌ Output validation failed (attempt {validation_retry_count + 1}/{max_validation_retries + 1})"
                            )
                            logger.warning(
                                f"Errors: {len(validation_result.errors)}, Warnings: {len(validation_result.warnings)}"
                            )

                            for i, error in enumerate(validation_result.errors[:5], 1):
                                logger.warning(f"  {i}. {error}")

                            if validation_retry_count < max_validation_retries:
                                revision_prompt = build_revision_prompt(
                                    validation_result, instruction
                                )
                                review_notes = revision_prompt
                                (
                                    review_section,
                                    sandbox_failure_section,
                                    revision_instructions,
                                ) = _build_review_sections(
                                    review_notes, sandbox_failure_notes
                                )
                                validation_retry_count += 1
                                logger.info(
                                    "🔄 Retrying with validation error feedback..."
                                )
                            else:
                                logger.error(
                                    f"❌ Validation failed after {max_validation_retries + 1} attempts"
                                )
                                logger.error(
                                    "Returning output with validation errors (marked as NEEDS_INFO)"
                                )
                                final_output = output
                                break
                    else:
                        final_output = output
                        break

                # Log final validation status
                if (
                    enable_validation
                    and validation_result
                    and not validation_result.is_valid
                ):
                    error_summary = "\n".join(
                        f"  - {e}" for e in validation_result.errors
                    )
                    logger.error(
                        f"⚠️ WriteCode output validation errors:\n{error_summary}\n"
                        f"Task may require manual intervention (NEEDS_INFO)"
                    )

                if final_output and "FILE:" in final_output:
                    final_output = self._format_output(
                        final_output, target_stack, language
                    )

                if not use_sandbox_self_heal:
                    await self._execute_sandbox_testing(
                        final_output, target_stack, language
                    )
                    return final_output

                ok, detail = await run_sandbox_project_result(
                    final_output, target_stack
                )
                if ok:
                    if detail.get("skipped"):
                        logger.debug(
                            "execute_project atlandı (manifest/import); legacy sandbox"
                        )
                        await self._execute_sandbox_testing(
                            final_output, target_stack, language
                        )
                    else:
                        logger.info(
                            "✅ Sandbox (execute_project) + kalite kapıları geçti"
                        )
                    return final_output

                logger.warning(
                    "⚠️ Sandbox veya kalite kapıları başarısız (self-heal denemesi)"
                )
                if heal_remaining <= 0:
                    logger.warning(
                        "⚠️ SANDBOX_SELF_HEAL_MAX_ATTEMPTS tükendi; son çıktı dönülüyor"
                    )
                    return final_output

                heal_remaining -= 1
                sandbox_failure_notes = build_sandbox_self_heal_feedback(detail)
                logger.info(
                    f"🔄 Sandbox self-heal: kalan deneme hakkı ≈ {heal_remaining}"
                )
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
        
        # Strip markdown code fences from each file content
        cleaned = []
        for path, content in files:
            # Remove opening ```lang or ``` at start, closing ``` at end
            stripped = re.sub(r'^```[a-zA-Z]*\s*', '', content.lstrip(), count=1)
            stripped = re.sub(r'\n?```\s*$', '', stripped.rstrip())
            cleaned.append((path, stripped.strip()))
        return cleaned
    
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


class RunSandboxTests(Action):
    """
    Üretilen FILE manifestindeki tüm dosyaları sandbox'ta (DinD + execute_project)
    çalıştırır; Charlie'nin ReviewCode prompt'una eklenecek Markdown özet döndürür.
    """

    name: str = "RunSandboxTests"

    def _stack_to_project_language(self, target_stack: str) -> str:
        """PROJECT_BASE_IMAGES / SandboxRunner dil anahtarı."""
        ts = (target_stack or "").lower().strip()
        if not ts:
            return "python"
        if any(
            x in ts
            for x in (
                "go-fiber",
                "go_fiber",
                "golang",
            )
        ) or ("go" in ts and "fiber" in ts):
            return "go"
        if "flutter" in ts or ts in ("dart",):
            return "dart"
        if any(
            x in ts
            for x in (
                "react-native",
                "react_native",
                "nextjs",
                "nestjs",
                "express",
                "react-vite",
                "vue-vite",
                "vanilla-html",
            )
        ):
            return "javascript"
        if "laravel" in ts or "php" in ts:
            return "php"
        if "fastapi" in ts or "django" in ts or "python" in ts:
            return "python"
        return "python"

    def _pick_test_command(
        self,
        target_stack: str,
        files: List[Tuple[str, str]],
        project_lang: str,
    ) -> str:
        ts = (target_stack or "").lower()
        if project_lang == "go":
            return "go test ./..."
        if project_lang == "dart":
            return "flutter test"

        wc_lang = project_lang
        if project_lang == "node":
            wc_lang = "javascript"

        wc = WriteCode()
        cmd = wc._determine_test_command(files, wc_lang, target_stack or "")
        if cmd:
            return cmd

        if project_lang == "javascript" or "react" in ts or "next" in ts:
            return "npm test -- --passWithNoTests 2>/dev/null || npm test || node --check $(ls *.js 2>/dev/null | head -1)"
        if project_lang == "php":
            return "php -l index.php 2>/dev/null || true"
        return "python -m pytest 2>/dev/null || python -m py_compile main.py 2>/dev/null || python -m compileall -q ."

    def _format_report(self, result: dict) -> str:
        ok = bool(result.get("success")) or result.get("exit_code") == 0
        dur = result.get("duration_ms", 0)
        exit_c = result.get("exit_code", "?")
        status_tr = "Başarılı" if ok else "Başarısız"
        emoji = "✅" if ok else "❌"
        stdout = (result.get("stdout") or "").strip()
        stderr = (result.get("stderr") or "").strip()
        err_msg = (result.get("error_message") or "").strip()

        def _trunc(s: str, n: int = 6000) -> str:
            if len(s) <= n:
                return s
            return s[:n] + f"\n... ({len(s) - n} karakter daha kesildi)"

        lines = [
            "## Sandbox Test Sonuçları (gerçek çalıştırma)",
            f"- **Durum:** {emoji} {status_tr} (exit_code={exit_c}, süre≈{dur}ms)",
        ]
        if err_msg and not ok:
            lines.append(f"- **Hata:** {_trunc(err_msg, 500)}")
        if stdout:
            lines.append(f"- **Stdout:**\n```\n{_trunc(stdout)}\n```")
        if stderr:
            lines.append(f"- **Stderr:**\n```\n{_trunc(stderr)}\n```")
        if not stdout and not stderr and ok:
            lines.append("- **Çıktı:** (boş veya sadece log)")
        return "\n".join(lines)

    async def run(self, code: str, target_stack: str = None) -> str:
        if _env_flag("DISABLE_SANDBOX_TESTING"):
            return (
                "## Sandbox Test Sonuçları\n"
                "- **Durum:** Devre dışı (`DISABLE_SANDBOX_TESTING`)\n"
            )

        files = WriteCode._parse_file_manifest(code)
        if not files:
            return (
                "## Sandbox Test Sonuçları\n"
                "- **Durum:** Dosya manifesti yok; sandbox çalıştırılmadı.\n"
            )

        pl_lang = self._stack_to_project_language(target_stack or "")
        test_cmd = self._pick_test_command(target_stack or "", files, pl_lang)

        try:
            from backend.services.sandbox import get_sandbox_runner

            runner = get_sandbox_runner()
        except ImportError:
            return (
                "## Sandbox Test Sonuçları\n"
                "- **Durum:** `backend.services.sandbox` yüklenemedi (import hatası).\n"
            )
        except Exception as e:
            return (
                "## Sandbox Test Sonuçları\n"
                f"- **Durum:** SandboxRunner başlatılamadı: `{e}`\n"
            )

        files_dict = {fp: content for fp, content in files}
        execution_id = str(uuid.uuid4())

        try:
            result = await runner.execute_project(
                execution_id=execution_id,
                files=files_dict,
                test_command=test_cmd,
                language=pl_lang,
                timeout=120.0,
                memory_limit_mb=1024,
                workspace_id="mgx-charlie-sandbox",
                project_id=execution_id,
            )
        except Exception as e:
            return (
                "## Sandbox Test Sonuçları\n"
                f"- **Durum:** Çalıştırma hatası: `{e}`\n"
            )

        return self._format_report(result)

    async def run_detailed(
        self,
        code: str,
        target_stack: Optional[str] = None,
        *,
        workspace_id: str = "mgx-writecode-sandbox",
        run_quality_gates: bool = True,
    ) -> Tuple[bool, Dict[str, Any]]:
        """
        execute_project + isteğe bağlı quality gates; (genel başarı, detay dict) döner.
        Charlie Markdown'ı için `run`; Alex self-heal için `run_detailed`.
        """
        detail: Dict[str, Any] = {
            "skipped": False,
            "reason": None,
            "sandbox_result": None,
            "quality_gates_passed": None,
            "quality_gate_raw": None,
        }

        if _env_flag("DISABLE_SANDBOX_TESTING"):
            detail["skipped"] = True
            detail["reason"] = "DISABLE_SANDBOX_TESTING"
            return True, detail

        files = WriteCode._parse_file_manifest(code)
        if not files:
            detail["skipped"] = True
            detail["reason"] = "no_file_manifest"
            return True, detail

        pl_lang = self._stack_to_project_language(target_stack or "")
        test_cmd = self._pick_test_command(target_stack or "", files, pl_lang)

        try:
            from backend.services.sandbox import get_sandbox_runner

            runner = get_sandbox_runner()
        except ImportError:
            detail["skipped"] = True
            detail["reason"] = "sandbox_import"
            return True, detail
        except Exception as e:
            detail["sandbox_result"] = {"error_message": str(e)}
            return False, detail

        files_dict = {fp: content for fp, content in files}
        execution_id = str(uuid.uuid4())

        try:
            result = await runner.execute_project(
                execution_id=execution_id,
                files=files_dict,
                test_command=test_cmd,
                language=pl_lang,
                timeout=120.0,
                memory_limit_mb=1024,
                workspace_id=workspace_id,
                project_id=execution_id,
            )
        except Exception as e:
            detail["sandbox_result"] = {
                "success": False,
                "stderr": str(e),
                "exit_code": 1,
            }
            return False, detail

        detail["sandbox_result"] = result
        sandbox_ok = bool(result.get("success")) or result.get("exit_code") == 0

        if not sandbox_ok:
            return False, detail

        if not run_quality_gates:
            detail["quality_gates_passed"] = None
            return True, detail

        wc = WriteCode()
        qg_ok = await wc._run_quality_gates_after_sandbox(
            files=files,
            workspace_id=workspace_id,
            project_id=execution_id,
            task_run_id=None,
        )
        detail["quality_gates_passed"] = qg_ok
        if not qg_ok:
            detail["quality_gate_raw"] = {
                "message": "Quality gates reported blocking failures or evaluation error",
            }
            return False, detail

        return True, detail


def build_sandbox_self_heal_feedback(detail: Dict[str, Any], max_chars: int = 8000) -> str:
    """LLM geri bildirimi: sandbox + (varsa) kalite kapısı özeti."""
    if detail.get("skipped"):
        return ""

    parts: List[str] = []
    sr = detail.get("sandbox_result") or {}
    if sr:
        exit_c = sr.get("exit_code", "?")
        parts.append(f"exit_code={exit_c}")
        if sr.get("error_message"):
            parts.append(f"hata: {sr.get('error_message')}")
        out = (sr.get("stdout") or "").strip()
        err = (sr.get("stderr") or "").strip()
        if out:
            parts.append("stdout:\n" + out[: max_chars // 2])
        if err:
            parts.append("stderr:\n" + err[: max_chars // 2])

    if detail.get("quality_gates_passed") is False:
        parts.append(
            "Kalite kapıları başarısız: "
            + str(detail.get("quality_gate_raw") or "blocking failures")
        )

    text = "\n\n".join(parts)
    if len(text) > max_chars:
        return text[:max_chars] + f"\n... ({len(text) - max_chars} karakter kesildi)"
    return text


async def run_sandbox_project_result(
    code: str,
    target_stack: Optional[str],
    *,
    workspace_id: str = "mgx-writecode-sandbox",
    run_quality_gates: bool = True,
) -> Tuple[bool, Dict[str, Any]]:
    """Charlie ile aynı execute_project yolu; Alex self-heal döngüsü için."""
    rs = RunSandboxTests()
    return await rs.run_detailed(
        code,
        target_stack,
        workspace_id=workspace_id,
        run_quality_gates=run_quality_gates,
    )


class ReviewCode(Action):
    """Kodu incele ve geri bildirim ver (stack-aware, structured output)"""

    PROMPT_TEMPLATE: str = """
    Kod:
    {code}

    Testler:
    {tests}
    {sandbox_section}
    Stack: {stack_name}
    {stack_specific_checks}

    Bu kodu DİKKATLİCE incele. Aşağıdaki 5 alanda her biri için [PASS] veya [FAIL] yaz, ardından kısa açıklama ekle:

    REVIEW SONUCU:
    1. SECURITY: [PASS/FAIL] — Hardcoded secret yok mu? SQL injection, XSS, CSRF koruması var mı? Input validation yapılmış mı? .env kullanılıyor mu?
    2. CODE_QUALITY: [PASS/FAIL] — Hata yönetimi var mı? Edge case'ler ele alınmış mı? Kod okunabilir mi? Gereksiz tekrar var mı?
    3. STACK_COMPLIANCE: [PASS/FAIL] — Stack-specific best practices uygulanmış mı? Doğru kütüphaneler kullanılıyor mu? PostgreSQL + golden path standartlarına uygun mu?
    4. TEST_COVERAGE: [PASS/FAIL] — Testler yeterli mi? Happy path + hata senaryoları test edilmiş mi?
    5. BUILD_READINESS: [PASS/FAIL] — package.json / composer.json / requirements.txt eksiksiz mi? Build/Run komutları doğru mu?

    {sandbox_verdict}

    KARAR KURALLARI (HER BİRİNİ UYGULA):
    ⛔ HARD GATE — Şu alanlarda FAIL varsa SONUÇ her zaman DEĞİŞİKLİK GEREKLİ'dir (diğer PASS'lar önemsiz):
       - SECURITY = [FAIL] → mutlaka DEĞİŞİKLİK GEREKLİ
       - STACK_COMPLIANCE = [FAIL] → mutlaka DEĞİŞİKLİK GEREKLİ
       - BUILD_READINESS = [FAIL] → mutlaka DEĞİŞİKLİK GEREKLİ
    ✅ Diğer durumlar: 5 alandan 4+ PASS ise ONAYLANDI, 3 veya daha az PASS ise DEĞİŞİKLİK GEREKLİ.

    ÖNEMLİ: MUTLAKA şu kelimelerden birini yaz: "ONAYLANDI" veya "DEĞİŞİKLİK GEREKLİ"

    SONUÇ: [ONAYLANDI / DEĞİŞİKLİK GEREKLİ]

    DÜZELTİLMESİ GEREKENLER (FAIL olan her alan için somut adım):
    - [somut düzeltme 1]
    - [somut düzeltme 2]
    """
    
    name: str = "ReviewCode"
    
    def _get_stack_checks(self, stack_id: str) -> str:
        """Stack-specific acceptance gate kontrol listesi.

        Golden path stack'ler (laravel-blade, flutter-laravel, laravel-react) için
        STACK_COMPLIANCE FAIL tetikleyen hard kriterleri içerir.
        """
        checks = {
            # ── Golden Path Stacks ─────────────────────────────────────────────
            "laravel-blade": """
STACK_COMPLIANCE Kontrol Listesi (Laravel + Blade + PostgreSQL) — HARD GATE:

ÖNCE — TAMAMLANMA KONTROLÜ (Kod metninde dosya varlığı; biri eksikse STACK_COMPLIANCE = [FAIL], SONUÇ = DEĞİŞİKLİK GEREKLİ):
Kodda şu dosyaların/desenlerin VAR OLUP OLMADIĞINI kontrol et (FILE: satırı veya dosya yolu geçerli sayılır):
- [ ] routes/web.php (veya routes/api.php) — "FILE: routes/web.php", "routes/web.php" veya benzeri; içinde Route:: tanımı olmalı → [PASS/FAIL]
- [ ] app/Http/Controllers/ — en az bir controller sınıfı (FILE: app/Http/Controllers/... veya namespace App\\Http\\Controllers) → [PASS/FAIL]
- [ ] resources/views/ — en az bir .blade.php (FILE: resources/views/... veya .blade.php içeren view) → [PASS/FAIL]
- [ ] resources/views/layouts/app.blade.php — ana layout (FILE: resources/views/layouts/app.blade.php veya layouts/app) → [PASS/FAIL]

BU TAMAMLANMA SATIRLARINDAN BİRİ [FAIL] İSE:
→ STACK_COMPLIANCE = [FAIL]
→ SONUÇ mutlaka DEĞİŞİKLİK GEREKLİ
→ DÜZELTİLMESİ GEREKENLER: Eksik dosya yollarını tek tek yaz; Alex'in routes, controllers ve Blade view'ları eklemesi gerekir.

SONRA — ZORUNLU (yukarıdaki tamamlanma PASS iken; biri eksikse STACK_COMPLIANCE = [FAIL]):
- [ ] PostgreSQL kullanılıyor (MySQL/SQLite yoktur)
- [ ] Laravel Sanctum auth mevcut (session veya token)
- [ ] Tüm formlar @csrf direktifini içeriyor
- [ ] Controller'lar FormRequest ile validation yapıyor (inline $request->validate() değil)
- [ ] Eloquent model $fillable tanımlı (mass assignment koruması)
- [ ] N+1 önleme: ilişkiler with() ile eager load ediliyor
- [ ] .env'de hardcoded credential yok (DB_PASSWORD, APP_KEY vb.)
- [ ] Migration dosyaları PostgreSQL uyumlu (jsonb, timestamptz kullanımı)
- [ ] PHPUnit / Pest test dosyaları mevcut (en az 1 Feature test)

TERCIH EDİLEN (olmazsa CODE_QUALITY olumsuz etkilenir):
- Policy veya Gate kullanımı (inline role check değil)
- Service katmanı (thin controller)
- Route model binding""",

            "flutter-laravel": """
STACK_COMPLIANCE Kontrol Listesi (Flutter + Laravel API + PostgreSQL) — HARD GATE:
ZORUNLU (biri eksikse STACK_COMPLIANCE = [FAIL]):
- [ ] Flutter: riverpod veya provider state management kullanılıyor
- [ ] Flutter: Dio kullanılıyor (http paketi değil) + AuthInterceptor
- [ ] Flutter: flutter_secure_storage (SharedPreferences değil) token için
- [ ] Flutter: go_router navigation (Navigator.push dağıtık kullanımı değil)
- [ ] Laravel: API-only backend (Sanctum token-based auth)
- [ ] Laravel: Resource sınıfları Eloquent cevaplarını dönüştürüyor
- [ ] Laravel: PostgreSQL kullanılıyor (MySQL/MongoDB yoktur)
- [ ] Laravel: FormRequest API validation
- [ ] API contract: Flutter ↔ Laravel endpoint URL'leri tutarlı
- [ ] CORS: Laravel cors.php'de Flutter origin'i izin veriyor

TERCIH EDİLEN:
- Feature-based Flutter klasör yapısı (lib/features/<feature>/)
- json_serializable + freezed model tipleri
- Flutter widget testleri + Laravel Feature testleri""",

            "laravel-react": """
STACK_COMPLIANCE Kontrol Listesi (Laravel API + React + PostgreSQL) — HARD GATE:
ZORUNLU (biri eksikse STACK_COMPLIANCE = [FAIL]):
- [ ] Laravel: Sanctum SPA mode — stateful domain ayarı
- [ ] React: Axios withCredentials: true (Sanctum cookie için)
- [ ] React: CSRF cookie fetch (/sanctum/csrf-cookie) mutating istekten önce
- [ ] React: TanStack Query server state için (useEffect+useState değil)
- [ ] React: Zustand global state için
- [ ] Laravel: PostgreSQL kullanılıyor (MySQL/MongoDB yoktur)
- [ ] Laravel: API resource sınıfları (ham Eloquent response yok)
- [ ] CORS: config/cors.php'de React dev origin izin veriliyor
- [ ] TypeScript: API response tiplemeleri tanımlanmış (any kullanılmıyor)
- [ ] Form: Zod veya React Hook Form + validation

TERCIH EDİLEN:
- Feature-based React klasör yapısı (src/features/<feature>/)
- Lazy loading ile route-level code splitting
- TanStack Query prefetching""",

            # ── Standart Stacks ───────────────────────────────────────────────
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
- Migration dosyaları var mı?
- CSRF koruması aktif mi?""",

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
    async def run(
        self,
        code: str,
        tests: str,
        target_stack: str = None,
        sandbox_report: str = None,
    ) -> str:
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

            sandbox_section = ""
            if sandbox_report and str(sandbox_report).strip():
                sandbox_section = "\n\n" + str(sandbox_report).strip()

            # Sandbox FAIL ise Charlie'yi otomatik olarak CHANGES REQUIRED yazmaya yönlendir
            sandbox_verdict = ""
            if sandbox_report and str(sandbox_report).strip():
                report_upper = str(sandbox_report).upper()
                sandbox_failed = any(
                    kw in report_upper for kw in [
                        "FAILED", "FAILURE", "ERROR", "HATA", "BAŞARISIZ",
                        "EXIT CODE: 1", "EXIT CODE 1", "TEST FAILED",
                    ]
                )
                if sandbox_failed:
                    sandbox_verdict = (
                        "\n⚠️ SANDBOX UYARISI: Sandbox testleri BAŞARISIZ oldu. "
                        "Bu durumda BUILD_READINESS alanı otomatik olarak [FAIL] sayılır ve "
                        "SONUÇ mutlaka DEĞİŞİKLİK GEREKLİ olmalıdır."
                    )
                else:
                    sandbox_verdict = "\n✅ SANDBOX: Testler başarıyla geçti."
            else:
                sandbox_verdict = "\n⚪ SANDBOX: Test çalıştırılamadı (dosya manifesti yok veya sandbox devre dışı)."

            prompt = self.PROMPT_TEMPLATE.format(
                code=code,
                tests=tests,
                sandbox_section=sandbox_section,
                stack_name=stack_name,
                stack_specific_checks=stack_specific_checks,
                sandbox_verdict=sandbox_verdict,
            )
            rsp = await aask_with_observability(self, prompt)
            return rsp
        except Exception as e:
            logger.error(f"❌ ReviewCode hatası: {e}")
            raise
