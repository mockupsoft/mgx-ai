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
    """Görevi analiz et"""
    
    PROMPT_TEMPLATE: str = """Görev: {task}

SADECE karmaşıklık seviyesini yaz:
- XS: Tek fonksiyon
- S: Birkaç fonksiyon  
- M: Modül düzeyinde
- L: Çoklu modül
- XL: Sistem düzeyinde

Yanıt formatı (SADECE bu kadar yaz):
KARMAŞIKLIK: [seviye]"""
    
    name: str = "AnalyzeTask"
    
    @llm_retry()
    async def run(self, task: str) -> str:
        try:
            prompt = self.PROMPT_TEMPLATE.format(task=task)
            rsp = await self._aask(prompt)
            return rsp
        except Exception as e:
            logger.error(f"❌ AnalyzeTask hatası: {e}")
            raise


class DraftPlan(Action):
    """Plan taslağı oluştur"""
    
    PROMPT_TEMPLATE: str = """Görev: {task}

Kısa ve öz plan yaz. SADECE şu formatı kullan:

1. Kod yaz - Alex (Engineer)
2. Test yaz - Bob (Tester)  
3. Review yap - Charlie (Reviewer)

Açıklama veya detay YAZMA. SADECE numaralı listeyi yaz."""
    
    name: str = "DraftPlan"
    
    @llm_retry()
    async def run(self, task: str, analysis: str) -> str:
        try:
            prompt = self.PROMPT_TEMPLATE.format(task=task)
            rsp = await self._aask(prompt)
            return rsp
        except Exception as e:
            logger.error(f"❌ DraftPlan hatası: {e}")
            raise


class WriteCode(Action):
    """Kod yaz"""
    
    PROMPT_TEMPLATE: str = """
Görev: {instruction}
Plan: {plan}

{review_section}

ADIM 1 - DÜŞÜN (YALNIZCA METİN):

- Bu görevi nasıl çözeceğini 3–7 madde halinde kısaca açıkla.
- Hangi fonksiyonları yazacağını ve hangi kütüphaneleri kullanacağını belirt.
- Edge case (uç durum) olarak neleri dikkate alacağını yaz.
- Bu düşünce kısmında HİÇBİR KOD yazma.

ADIM 2 - KODLA (SADECE AŞAĞIDAKİ BLOĞA KOD YAZ):

Aşağıdaki ```python``` bloğunda, yukarıdaki plana uygun ve edge case'leri de kapsayan
KESİN Python kodunu yaz.
Kodun temiz, okunabilir ve iyi yorumlanmış olsun.

{revision_instructions}

```python
# kodunuz buraya
```
"""
    
    name: str = "WriteCode"
    
    @llm_retry()
    async def run(self, instruction: str, plan: str = "", review_notes: str = "") -> str:
        try:
            # Review notları varsa ekle
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
            
            prompt = self.PROMPT_TEMPLATE.format(
                instruction=instruction,
                plan=plan,
                review_section=review_section,
                revision_instructions=revision_instructions
            )
            rsp = await self._aask(prompt)
            return self._parse_code(rsp)
        except Exception as e:
            logger.error(f"❌ WriteCode hatası: {e}")
            raise
    
    @staticmethod
    def _parse_code(rsp: str) -> str:
        pattern = r"```python(.*)```"
        match = re.search(pattern, rsp, re.DOTALL)
        return match.group(1).strip() if match else rsp


class WriteTest(Action):
    """Test yaz"""
    
    PROMPT_TEMPLATE: str = """
    Kod:
    {code}
    
    ÖNEMLİ: Bu kod için pytest kullanarak TAM OLARAK {k} ADET unit test yaz.
    DAHA FAZLA YAZMA! Sadece {k} adet test yaz.
    
    Kurallar:
    1. TAM OLARAK {k} adet test yaz (daha fazla değil!)
    2. Her test farklı bir senaryoyu test etmeli:
       - Pozitif senaryo (normal kullanım)
       - Negatif senaryo (hata durumları)
       - Edge case (sınır değerleri)
    3. Aynı testi tekrar yazma - her test benzersiz olmalı
    4. Test isimleri açıklayıcı olsun
    
    Sadece {k} adet test yaz, daha fazla değil!
    
    ```python
    import pytest
    
    # Test 1: [açıklama]
    def test_1():
        # kod
    
    # Test 2: [açıklama]
    def test_2():
        # kod
    
    # Test {k}: [açıklama]
    def test_{k}():
        # kod
    ```
    
    UYARI: Sadece {k} adet test yaz, daha fazla yazma!
    """
    
    name: str = "WriteTest"
    
    @staticmethod
    def _parse_code(rsp: str) -> str:
        pattern = r"```python(.*)```"
        match = re.search(pattern, rsp, re.DOTALL)
        return match.group(1).strip() if match else rsp.strip()
    
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
    
    @llm_retry()
    async def run(self, code: str, k: int = 3) -> str:
        try:
            prompt = self.PROMPT_TEMPLATE.format(code=code, k=k)
            rsp = await self._aask(prompt)
            raw_code = self._parse_code(rsp)
            # Post-process: Test sayısını k ile sınırla (LLM daha fazla yazsa bile)
            limited_code = self._limit_tests(raw_code, k)
            logger.debug(f"📊 WriteTest: {k} adet test sınırı uygulandı")
            return limited_code
        except Exception as e:
            logger.error(f"❌ WriteTest hatası: {e}")
            raise


class ReviewCode(Action):
    """Kodu incele ve geri bildirim ver"""
    
    PROMPT_TEMPLATE: str = """
    Kod:
    {code}
    
    Testler:
    {tests}
    
    Bu kodu ve testleri DİKKATLİCE incele:
    1. Kod kalitesi nasıl? Hata yönetimi var mı? Input validation var mı?
    2. Test coverage yeterli mi? Edge case'ler test edilmiş mi?
    3. Docstring'ler var mı? Kod dokümantasyonu yeterli mi?
    4. İyileştirme gereken noktalar var mı?
    
    ÖNEMLİ: Eğer kodda eksiklikler, hatalar veya iyileştirme gereken noktalar varsa MUTLAKA "DEĞİŞİKLİK GEREKLİ" yaz.
    Sadece kod mükemmel ve hiçbir sorun yoksa "ONAYLANDI" yaz.
    
    SONUÇ: [ONAYLANDI / DEĞİŞİKLİK GEREKLİ]
    
    YORUMLAR:
    - [yorum 1]
    - [yorum 2]
    - [yorum 3]
    """
    
    name: str = "ReviewCode"
    
    @llm_retry()
    async def run(self, code: str, tests: str) -> str:
        try:
            prompt = self.PROMPT_TEMPLATE.format(code=code, tests=tests)
            rsp = await self._aask(prompt)
            return rsp
        except Exception as e:
            logger.error(f"❌ ReviewCode hatası: {e}")
            raise
