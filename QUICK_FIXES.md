# TEM Agent - Hızlı Düzeltme Rehberi

Bu doküman, kod review'da bulunmuş sorunlara yönelik kısa vadede yapılabilecek düzeltmeleri içerir.

---

## 🔧 FIX #1: .gitignore Ekle

**Sorun:** Hiçbir .gitignore dosyası yok

**Çözüm:**
```bash
# .gitignore
# Byte-compiled / optimized / DLL files
__pycache__/
*.py[cod]
*$py.class

# Distribution / packaging
.Python
build/
develop-eggs/
dist/
downloads/
eggs/
.eggs/
lib/
lib64/
parts/
sdist/
var/
wheels/
*.egg-info/
.installed.cfg
*.egg

# Virtual environments
venv/
ENV/
env/
.venv

# IDE
.vscode/
.idea/
*.swp
*.swo
*~

# Testing
.pytest_cache/
.coverage
htmlcov/

# Logging
*.log

# Output files
output/
results/

# Temporary files
*.tmp
*.bak
*.bak_*

# OS
.DS_Store
.DS_Store?
._*
.Spotlight-V100
.Trashes
ehthumbs.db

# Config secrets
config_*.yaml
*.key
*.pem
```

**Zaman:** 2 dakika

---

## 🔧 FIX #2: Magic Numbers için Constants Dosyası

**Sorun:** 3600, 20, 3, 5 gibi sabitler kod içine saçılmış

**Çözüm:** mgx_agent/constants.py oluştur:

```python
# mgx_agent/constants.py
"""
Proje sabitleri - Magic numbers burada merkezleştirilmiş.

Kullanım:
    from mgx_agent.constants import DEFAULT_MAX_ROUNDS, PROGRESS_BAR_LENGTH
"""

# ============================================
# Task Complexity Levels
# ============================================
COMPLEXITY_XS = "XS"  # Çok basit - tek dosya, tek fonksiyon
COMPLEXITY_S = "S"    # Basit - birkaç fonksiyon
COMPLEXITY_M = "M"    # Orta - birden fazla dosya
COMPLEXITY_L = "L"    # Büyük - mimari gerektirir
COMPLEXITY_XL = "XL"  # Çok büyük - tam takım gerektirir

COMPLEXITY_LEVELS = [COMPLEXITY_XS, COMPLEXITY_S, COMPLEXITY_M, COMPLEXITY_L, COMPLEXITY_XL]

# ============================================
# Default Configuration
# ============================================
DEFAULT_MAX_ROUNDS = 5
DEFAULT_MAX_REVISION_ROUNDS = 2
DEFAULT_MAX_MEMORY_SIZE = 50
DEFAULT_ENABLE_CACHING = True
DEFAULT_ENABLE_STREAMING = True
DEFAULT_ENABLE_PROGRESS_BAR = True
DEFAULT_ENABLE_METRICS = True
DEFAULT_ENABLE_MEMORY_CLEANUP = True
DEFAULT_HUMAN_REVIEWER = False
DEFAULT_AUTO_APPROVE_PLAN = False
DEFAULT_INVESTMENT = 3.0
DEFAULT_BUDGET_MULTIPLIER = 1.0
DEFAULT_USE_MULTI_LLM = False
DEFAULT_VERBOSE = False

# ============================================
# Cache Settings
# ============================================
DEFAULT_CACHE_TTL_SECONDS = 3600  # 1 hour
MIN_CACHE_TTL_SECONDS = 60        # Minimum 1 minute
MAX_CACHE_TTL_SECONDS = 86400     # Maximum 1 day

# ============================================
# UI/UX Constants
# ============================================
PROGRESS_BAR_LENGTH = 20           # Progress bar character length
PROGRESS_BAR_FILLED = "█"
PROGRESS_BAR_EMPTY = "░"
SECTION_SEPARATOR = "=" * 60
SUBSECTION_SEPARATOR = "-" * 50

# ============================================
# Memory & Token Management
# ============================================
RELEVANT_MEMORY_LIMIT = 5          # Keep top N relevant memories
DEFAULT_TEST_COUNT = 3             # Default number of tests to generate
MAX_TEST_COUNT = 10                # Maximum test functions per generation
REVIEW_NOTES_MAX_LENGTH = 500      # Truncate review notes to this length
MEMORY_CLEANUP_INTERVAL = 10       # Clean memory every N operations

# ============================================
# Retry Settings (Tenacity)
# ============================================
RETRY_MAX_ATTEMPTS = 3
RETRY_MIN_WAIT_SECONDS = 2
RETRY_MAX_WAIT_SECONDS = 10
RETRY_EXPONENTIAL_MULTIPLIER = 1

# ============================================
# File I/O
# ============================================
OUTPUT_DIRECTORY = "output"
OUTPUT_DIRNAME_PREFIX = "mgx_team"
OUTPUT_BACKUP_SUFFIX = ".bak"
MAX_FILE_SIZE_BYTES = 10 * 1024 * 1024  # 10 MB

# ============================================
# JSON Parsing Markers
# ============================================
JSON_START_MARKER = "---JSON_START---"
JSON_END_MARKER = "---JSON_END---"

# ============================================
# Pattern Matching
# ============================================
COMPLEXITY_PATTERN = r"KARMAŞIKLIK:\s*(XS|S|M|L|XL)"
CODE_BLOCK_PATTERN = r"```(?:python)?\s*(.*?)\s*```"
TASK_KEYWORD_PATTERN = r"GÖREV:|TASK:"
PLAN_KEYWORD_PATTERN = r"PLAN:|PLAN STEPS:"

# ============================================
# Review Keywords
# ============================================
REVIEW_APPROVED_KEYWORD = "ONAYLANDI"
REVIEW_CHANGES_NEEDED_KEYWORD = "DEĞİŞİKLİK GEREKLİ"
REVIEW_RESULT_PATTERN = r"SONUÇ:\s*(ONAYLANDI|DEĞİŞİKLİK GEREKLİ)"

# ============================================
# Model Pricing (örnek - gerçek fiyatlar ile update et)
# ============================================
MODEL_PRICING = {
    "gpt-4": {
        "prompt": 0.03 / 1000,      # $ per token
        "completion": 0.06 / 1000,
    },
    "gpt-3.5-turbo": {
        "prompt": 0.0005 / 1000,
        "completion": 0.0015 / 1000,
    },
    "default": {
        "prompt": 0.001 / 1000,
        "completion": 0.002 / 1000,
    }
}

# ============================================
# CLI Arguments Defaults
# ============================================
DEFAULT_TASK = "Listedeki sayıların çarpımını hesaplayan bir Python fonksiyonu yaz"

# ============================================
# Logging Configuration
# ============================================
LOG_FORMAT = "%(asctime)s - %(name)s - %(levelname)s - %(message)s"
LOG_DATE_FORMAT = "%Y-%m-%d %H:%M:%S"

# ============================================
# Revision Loop Control
# ============================================
REVISION_MAX_ATTEMPTS = 5           # Safety limit (also in config)
INFINITE_LOOP_HASH_CHECK = True     # Enable duplicate review detection
REVISION_PROMPT_TEMPLATE = "Charlie'nin review notlarına göre kodu iyileştir"
```

**Kullanım:**
```python
# Mevcut:
cache_ttl = 3600

# Düzeltilmiş:
from mgx_agent.constants import DEFAULT_CACHE_TTL_SECONDS
cache_ttl = DEFAULT_CACHE_TTL_SECONDS
```

**Zaman:** 30 dakika

---

## 🔧 FIX #3: Tekrar Eden Code Parsing'i DRY Yap

**Sorun:** Code block parsing 2-3 yerde tekrarlanıyor

**Çözüm:** Utility fonksiyona çıkar (utils.py'ye ekle):

```python
# mgx_agent/utils.py

import re
from typing import List, Optional
from mgx_agent import constants

def extract_code_blocks(text: str) -> List[str]:
    """
    Metinden Python kod bloklarını çıkar.
    
    Args:
        text: İçinde kod bloğu olabilecek metin
        
    Returns:
        Bulunan kod bloklarının listesi (boş olabilir)
        
    Example:
        >>> text = "```python\\nprint('hello')\\n```"
        >>> blocks = extract_code_blocks(text)
        >>> assert blocks[0] == "print('hello')"
    """
    if not text:
        return []
    
    matches = re.findall(constants.CODE_BLOCK_PATTERN, text, re.DOTALL)
    return [match.strip() for match in matches if match.strip()]

def extract_first_code_block(text: str) -> Optional[str]:
    """
    Metinden ilk kod bloğunu çıkar.
    
    Useful for single-output parsing (WriteCode, WriteTest)
    """
    blocks = extract_code_blocks(text)
    return blocks[0] if blocks else None

# ESKI (hatalı - tekrarlı):
# WriteCode sınıfında:
@staticmethod
def _parse_code(rsp: str) -> str:
    pattern = r"```python(.*)```"
    match = re.search(pattern, rsp, re.DOTALL)
    return match.group(1).strip() if match else rsp

# WriteTest sınıfında:
@staticmethod
def _parse_code(rsp: str) -> str:
    pattern = r"```python(.*)```"
    match = re.search(pattern, rsp, re.DOTALL)
    return match.group(1).strip() if match else rsp.strip()

# YENİ (DRY):
from mgx_agent.utils import extract_first_code_block

# Her iki Action'da:
async def run(self, ...):
    rsp = await self._aask(prompt)
    code = extract_first_code_block(rsp) or rsp
    return code
```

**Zaman:** 20 dakika

---

## 🔧 FIX #4: Güvenli JSON Parsing

**Sorun:** JSON parsing başarısız olursa hiçbir log yok (silent failure)

**Çözüm:** utils.py'ye ekle ve log ekle:

```python
# mgx_agent/utils.py

import json
from typing import Optional
from metagpt.logs import logger
from mgx_agent import constants

def parse_json_block(text: str, 
                     start_marker: str = None,
                     end_marker: str = None) -> Optional[dict]:
    """
    Gömülü JSON'u parse et.
    
    Args:
        text: İçinde JSON olabilecek metin
        start_marker: JSON başlangıç markeri (default: ---JSON_START---)
        end_marker: JSON bitiş markeri (default: ---JSON_END---)
        
    Returns:
        Parse edilen dict, başarısızsa None
        
    Example:
        >>> text = "---JSON_START---\\n{'key': 'value'}\\n---JSON_END---"
        >>> data = parse_json_block(text)
    """
    if start_marker is None:
        start_marker = constants.JSON_START_MARKER
    if end_marker is None:
        end_marker = constants.JSON_END_MARKER
    
    # Marker kontrolü
    if start_marker not in text or end_marker not in text:
        logger.debug(f"JSON markers not found in text (length: {len(text)})")
        return None
    
    try:
        # JSON'u çıkar
        json_str = text.split(start_marker)[1].split(end_marker)[0].strip()
        
        if not json_str:
            logger.warning("JSON block is empty")
            return None
        
        # Parse et
        data = json.loads(json_str)
        logger.debug(f"Successfully parsed JSON (keys: {list(data.keys())})")
        return data
        
    except IndexError as e:
        logger.warning(f"Failed to extract JSON block: marker mismatch - {e}")
        return None
    except json.JSONDecodeError as e:
        logger.warning(f"Invalid JSON in block: {e}")
        logger.debug(f"JSON string: {json_str[:100]}...")
        return None
    except Exception as e:
        logger.error(f"Unexpected error parsing JSON: {e}")
        return None

# KULLANIM (Alex._act() içinde):
from mgx_agent.utils import parse_json_block

for m in all_messages:
    data = parse_json_block(m.content)
    if data and "task" in data and "plan" in data:
        instruction = data["task"]
        plan = data["plan"]
        logger.info(f"Extracted task from message: {instruction[:50]}...")
        break
else:
    logger.warning("No valid JSON task spec found in messages")
```

**Zaman:** 20 dakika

---

## 🔧 FIX #5: Input Sanitization

**Sorun:** output_dir'e datetime kullanılıyor ama başka validation yok

**Çözüm:** utils.py'ye güvenlik fonksiyonu ekle:

```python
# mgx_agent/utils.py

import re
from pathlib import Path
from typing import Optional

def sanitize_filename(filename: str, max_length: int = 255) -> str:
    """
    Dosya adını güvenli hale getir.
    
    Args:
        filename: Sanitize edilecek dosya adı
        max_length: Maksimum uzunluk
        
    Returns:
        Sanitize edilmiş dosya adı
    """
    # Sadece alphanumeric, underscore, hyphen, dot izin ver
    sanitized = re.sub(r'[^a-zA-Z0-9._-]', '_', filename)
    
    # Uzunluk sınırla
    if len(sanitized) > max_length:
        sanitized = sanitized[:max_length]
    
    # Boşsa default
    if not sanitized or sanitized.startswith('.'):
        sanitized = "output"
    
    return sanitized

def validate_task_description(task: str, max_length: int = 10000) -> str:
    """
    Görev açıklamasını validate et - injection attacks'tan korunma.
    
    Args:
        task: Validate edilecek görev
        max_length: Maksimum uzunluk
        
    Returns:
        Validate edilen görev
        
    Raises:
        ValueError: Geçersiz görev
    """
    # Null/type check
    if not task or not isinstance(task, str):
        raise ValueError("Task must be a non-empty string")
    
    # Uzunluk check
    if len(task) > max_length:
        raise ValueError(f"Task exceeds max length of {max_length} chars")
    
    # Tehlikeli pattern'ler
    dangerous_patterns = [
        (r"exec\(", "exec() call detected"),
        (r"eval\(", "eval() call detected"),
        (r"__import__", "__import__ detected"),
        (r"system\(", "system() call detected"),
        (r"popen\(", "popen() call detected"),
        (r"subprocess\.", "subprocess import detected"),
        (r"os\.system", "os.system call detected"),
    ]
    
    task_lower = task.lower()
    for pattern, reason in dangerous_patterns:
        if re.search(pattern, task_lower):
            logger.warning(f"Suspicious pattern in task: {reason}")
            raise ValueError(f"Dangerous pattern detected: {reason}")
    
    logger.debug(f"Task validation passed (length: {len(task)})")
    return task

# KULLANIM (main fonksiyonunda):
from mgx_agent.utils import validate_task_description

async def main(custom_task: str = None):
    task = custom_task or "Varsayılan görev"
    
    try:
        task = validate_task_description(task)
    except ValueError as e:
        print(f"❌ Geçersiz görev: {e}")
        return
    
    mgx_team = MGXStyleTeam()
    await mgx_team.analyze_and_plan(task)
```

**Zaman:** 20 dakika

---

## 🔧 FIX #6: README.md Oluştur (Minimum)

**Sorun:** README.md yok, nasıl kurulacağı belli değil

**Çözüm:** Proje kökünde README.md oluştur:

```markdown
# MGX Style Multi-Agent Team (TEM Agent)

MetaGPT temelli, dört rol içeren bir multi-agent kod geliştirme sistemi.

## 🚀 Özellikler

- **4 Uzman Rol:** Mike (Planner), Alex (Engineer), Bob (Tester), Charlie (Reviewer)
- **Otomatik Karmaşıklık Değerlendirmesi:** XS/S/M/L/XL seviyeleri
- **Akıllı Revision Döngüleri:** AI tarafından yönlendirilen kod iyileştirmeleri
- **Metrik Takibi:** Token kullanımı ve tahmini maliyetler
- **Esnek Konfigürasyon:** Pydantic V2 tabanlı validation
- **İnsan Müdahalesi:** Opsiyonel human reviewer entegrasyonu

## 📦 Kurulum

```bash
# Repository klonla
git clone <repo>
cd project

# Bağımlılıkları yükle
pip install -r requirements.txt

# MetaGPT setup (ilk kez)
python -m metagpt.config
```

## 🎯 Hızlı Başlangıç

```bash
# Normal mod
python examples/mgx_style_team.py

# İnsan reviewer modu
python examples/mgx_style_team.py --human

# Özel görev
python examples/mgx_style_team.py --task "Fibonacci hesaplayan fonksiyon yaz"
```

## 📖 Dokümantasyon

- [CODE_REVIEW_REPORT.md](CODE_REVIEW_REPORT.md) - Detaylı kod incelemesi
- [IMPROVEMENT_GUIDE.md](IMPROVEMENT_GUIDE.md) - Refactoring rehberi
- [QUICK_FIXES.md](QUICK_FIXES.md) - Hızlı düzeltmeler

## 🔗 Mimarı

```
CLI Input
    ↓
Mike (Analiz & Plan)
    ↓
Alex (Kod Yazma)
    ↓
Bob (Test Yazma)
    ↓
Charlie (Review)
    ↓
Revision Loop (eğer gerekli)
    ↓
Output (main.py, test_main.py, review.md)
```

## 📝 Lisans

MIT
```

**Zaman:** 10 dakika

---

## 🔧 FIX #7: Human-In-The-Loop TODO'su Kaldır

**Sorun:** Line 1138 - TODO flag var ancak feature çalışıyor

**Çözüm:**

```python
# Mevcut (YANLIŞ):
if is_human:
    self.is_human = True
    logger.info(f"👤 {self.name}: HUMAN FLAG SET - Şu an LLM kullanıyor...")
    # (ileride terminal input eklenecek)

# Düzeltilmiş:
if is_human:
    self.is_human = True
    logger.info(f"👤 {self.name}: İNSAN REVIEWER MODU AKTİF")
    logger.info(f"   Sıra size gelince terminal'den input beklenir.")

# Ve Charlie._act() içinde (line 1166-1200) input() zaten varsa,
# sadece TODO comment'i kaldır
```

**Zaman:** 5 dakika

---

## 🔧 FIX #8: MetaGPTAdapter Uyarısı Daha Açık Yapma

**Sorun:** Line 678 - Warning yeterince açık değil

**Çözüm:**

```python
# Mevcut:
logger.warning("⚠️ _memory private attribute kullanıldı - MetaGPT güncellemesinde kırılabilir!")

# Düzeltilmiş:
logger.warning(
    "⚠️ UYARI: MetaGPT private attribute (_memory) kullanılıyor! "
    "   MetaGPT versiyon güncellemesinde bu kod KIRILAB"
    "   GitHub issue açarak bu problemi raporla."
)

# Veya kod açıklaması ekle:
# FALLBACK STRATEGY 3: Private attribute (last resort - risky!)
# TODO: MetaGPT public API isteme
# GitHub issue: https://github.com/geekan/MetaGPT/issues/XXX
if hasattr(mem_store, "_memory"):
    mem_store._memory = messages_to_keep
    logger.warning(
        "⚠️ Using private _memory attribute. "
        "This may break with MetaGPT updates. "
        "Consider submitting public API request to MetaGPT."
    )
    return True
```

**Zaman:** 10 dakika

---

## 📋 QUICK FIX CHECKLIST

| # | FIX | Zaman | Etki | Durumu |
|---|-----|-------|------|--------|
| 1 | .gitignore ekle | 2 min | High | [ ] |
| 2 | constants.py | 30 min | High | [ ] |
| 3 | DRY code parsing | 20 min | Medium | [ ] |
| 4 | JSON parsing logs | 20 min | Medium | [ ] |
| 5 | Input sanitization | 20 min | High | [ ] |
| 6 | README.md (min) | 10 min | High | [ ] |
| 7 | Remove TODO flags | 5 min | Low | [ ] |
| 8 | Clearer warnings | 10 min | Low | [ ] |
| **TOTAL** | | **127 min** | | |

---

## 🎯 Sırada Ne Var?

Bu quick fixes'i yaptıktan sonra:

1. **Test Altyapısını Kur** (40-50 saat)
   - pytest + pytest-asyncio
   - Mock LLM setup
   - 50+ unit test

2. **Modularize Et** (6-8 saat)
   - Dosyaları böl
   - Package structure
   - Import düzelt

3. **Uzun Fonksiyonları Refactor Et** (4-5 saat)
   - execute() -> 5 fonksiyon
   - Alex._act() -> helpers
   - _collect_results() -> optimized

---

**Toplam Hızlı Düzeltme Süresi:** ~2 saat ✅  
**Etki:** Medium-High 📈  
**Zor Derecesi:** Düşük 🟢

Bunları yap → Daha sonra test ve modularization'a geç!
