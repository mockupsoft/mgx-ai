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

import re
from tenacity import retry, stop_after_attempt, wait_exponential, retry_if_exception_type
from metagpt.actions import Action
from metagpt.logs import logger


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
            rsp = await self._aask(prompt)
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
            rsp = await self._aask(prompt)
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
        strict_mode: bool = False
    ) -> str:
        try:
            # Stack bilgisi
            from .stack_specs import get_stack_spec, infer_stack_from_task
            
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
            rsp = await self._aask(prompt)
            
            # Strict mode ise FILE manifest olarak parse et
            if strict_mode:
                return rsp  # FILE manifest formatında döndür (parse edilecek)
            else:
                # Normal mod: code block parse et (backward compatibility)
                return self._parse_code(rsp, language)
        except Exception as e:
            logger.error(f"❌ WriteCode hatası: {e}")
            raise
    
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
        
        # Hiçbir pattern match etmezse, olduğu gibi döndür
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
            rsp = await self._aask(prompt)
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
