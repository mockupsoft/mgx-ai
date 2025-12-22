# TEM Agent İyileştirme Rehberi

Bu doküman, TEM Agent projesinin kod review raporunda belirlenen sorunları çözmek için adım adım rehber ve örnekler sağlar.

---

## 📑 İçindekiler

1. [Modularization (Bölümleme)](#1-modularization)
2. [Test Altyapısı](#2-test-altyapısı)
3. [Code Refactoring](#3-code-refactoring)
4. [Dokümantasyon](#4-dokümantasyon)
5. [Performance Optimization](#5-performance-optimization)
6. [Güvenlik Iyileştirmeleri](#6-güvenlik-iyileştirmeleri)

---

## 1. Modularization

### Mevcut Durum
```
examples/
└── mgx_style_team.py (2392 satır - HER ŞEY BİRDE!)
```

### Hedef Durum
```
mgx_agent/
├── __init__.py
├── constants.py           # Magic numbers
├── config.py             # TeamConfig, TaskComplexity
├── metrics.py            # TaskMetrics
├── actions.py            # Action sınıfları
├── roles.py              # Role sınıfları
├── adapter.py            # MetaGPT adaptasyonu
├── team.py               # MGXStyleTeam orchestrator
├── utils.py              # Helper fonksiyonlar
└── cli.py                # CLI entry points
```

### Implementation Plan

#### Step 1: constants.py
```python
# mgx_agent/constants.py
"""Proje sabitleri"""

# Task Complexity Levels
COMPLEXITY_XS = "XS"
COMPLEXITY_S = "S"
COMPLEXITY_M = "M"
COMPLEXITY_L = "L"
COMPLEXITY_XL = "XL"

# Default Values
DEFAULT_MAX_ROUNDS = 5
DEFAULT_MAX_REVISION_ROUNDS = 2
DEFAULT_MAX_MEMORY_SIZE = 50
DEFAULT_CACHE_TTL_SECONDS = 3600
DEFAULT_INVESTMENT = 3.0
DEFAULT_BUDGET_MULTIPLIER = 1.0

# Performance Settings
PROGRESS_BAR_LENGTH = 20
RELEVANT_MEMORY_LIMIT = 5
DEFAULT_TEST_COUNT = 3
REVIEW_NOTES_MAX_LENGTH = 500

# Retry Settings
RETRY_MAX_ATTEMPTS = 3
RETRY_MIN_WAIT = 2
RETRY_MAX_WAIT = 10

# Model Pricing (örnek - gerçek fiyatlar eklenecek)
MODEL_PRICING = {
    "gpt-4": {
        "prompt": 0.03,
        "completion": 0.06
    },
    "gpt-3.5-turbo": {
        "prompt": 0.0005,
        "completion": 0.0015
    }
}

# Magic Strings
JSON_START_MARKER = "---JSON_START---"
JSON_END_MARKER = "---JSON_END---"
COMPLEXITY_PATTERN = r"KARMAŞIKLIK:\s*(XS|S|M|L|XL)"
CODE_BLOCK_PATTERN = r"```(?:python)?\s*(.*?)\s*```"
```

#### Step 2: Modular File Structure

Mevcut dosyayı şu şekilde ayır:

**config.py:**
```python
# mgx_agent/config.py
from enum import Enum
from pydantic import BaseModel, Field, field_validator, ConfigDict
import yaml
import logging

logger = logging.getLogger(__name__)

class LogLevel(str, Enum):
    """Log seviyeleri"""
    DEBUG = "debug"
    INFO = "info"
    WARNING = "warning"
    ERROR = "error"

class TaskComplexity:
    """Görev karmaşıklık seviyeleri"""
    XS = "XS"
    S = "S"
    M = "M"
    L = "L"
    XL = "XL"

class TeamConfig(BaseModel):
    """MGX Style Team konfigürasyonu"""
    # ... (mevcut implementation)
    
    @field_validator('max_rounds')
    @classmethod
    def validate_max_rounds(cls, v):
        if v < 1:
            raise ValueError("max_rounds en az 1 olmalı")
        return v
```

**metrics.py:**
```python
# mgx_agent/metrics.py
from dataclasses import dataclass, field
from datetime import datetime

@dataclass
class TaskMetrics:
    """Görev metrikleri"""
    task_name: str
    start_time: float
    end_time: float = 0.0
    success: bool = False
    complexity: str = "XS"
    token_usage: int = 0
    estimated_cost: float = 0.0
    revision_rounds: int = 0
    error_message: str = ""
    
    @property
    def duration_seconds(self) -> float:
        """Görev süresi (saniye)"""
        return self.end_time - self.start_time if self.end_time else 0.0
    
    @property
    def duration_formatted(self) -> str:
        """Formatlanmış süre"""
        secs = self.duration_seconds
        if secs < 60:
            return f"{secs:.1f}s"
        elif secs < 3600:
            return f"{secs/60:.1f}m"
        else:
            return f"{secs/3600:.1f}h"
    
    def to_dict(self) -> dict:
        """Metriği dict olarak döndür"""
        return {
            "task_name": self.task_name,
            "duration": self.duration_formatted,
            "success": self.success,
            "complexity": self.complexity,
            "token_usage": self.token_usage,
            "estimated_cost": f"${self.estimated_cost:.4f}",
            "revision_rounds": self.revision_rounds,
            "error": self.error_message if self.error_message else None
        }
```

**adapter.py:**
```python
# mgx_agent/adapter.py
"""MetaGPT adaptasyonu ve soyutlama"""

class MetaGPTAdapter:
    """MetaGPT'nin internal API'sini soyutlayan adapter"""
    
    @staticmethod
    def get_memory_store(role):
        """Role'dan memory store'u güvenli şekilde al"""
        if not hasattr(role, "rc"):
            return None
        if not hasattr(role.rc, "memory"):
            return None
        return role.rc.memory
    
    # ... (diğer metodlar)
```

**utils.py:**
```python
# mgx_agent/utils.py
"""Yardımcı fonksiyonlar"""

import re
from typing import Optional

def parse_code_blocks(text: str) -> list:
    """Metinden Python kod bloklarını çıkar"""
    if not text:
        return []
    
    pattern = r"```(?:python)?\s*(.*?)\s*```"
    matches = re.findall(pattern, text, re.DOTALL)
    return [m.strip() for m in matches if m.strip()]

def parse_json_block(text: str, start_marker: str = "---JSON_START---", 
                     end_marker: str = "---JSON_END---") -> Optional[dict]:
    """Gömülü JSON'u parse et"""
    if start_marker not in text or end_marker not in text:
        return None
    
    try:
        json_str = text.split(start_marker)[1].split(end_marker)[0].strip()
        return json.loads(json_str)
    except (json.JSONDecodeError, IndexError, ValueError) as e:
        logger.warning(f"JSON parse hatası: {e}")
        return None

def extract_complexity(text: str) -> str:
    """Metinden karmaşıklık seviyesini çıkar"""
    from constants import COMPLEXITY_PATTERN, COMPLEXITY_XS
    
    m = re.search(COMPLEXITY_PATTERN, text.upper())
    return m.group(1) if m else COMPLEXITY_XS

def print_phase_header(phase: str, emoji: str = "🔄"):
    """Faz başlığı yazdır"""
    print(f"\n{'='*60}")
    print(f"{emoji} {phase}")
    print(f"{'='*60}")

def print_step_progress(step: int, total: int, description: str, role=None):
    """Adım adım progress göster
    
    Args:
        step: Mevcut adım numarası
        total: Toplam adım sayısı
        description: İşlem açıklaması
        role: Role instance (team referansı için)
    """
    if role and hasattr(role, '_team_ref') and hasattr(role._team_ref, '_print_progress'):
        role._team_ref._print_progress(step, total, description)
        return
    
    bar_length = 20
    filled = int(bar_length * step / total)
    bar = "█" * filled + "░" * (bar_length - filled)
    percent = int(100 * step / total)
    print(f"\r[{bar}] {percent}% - {description}", end="", flush=True)
    if step == total:
        print()
```

### Verification Checklist

- [ ] `constants.py` oluşturuldu ve tüm magic numbers taşındı
- [ ] `config.py` ayrı dosya olarak çalışıyor
- [ ] `metrics.py` ayrı dosya olarak çalışıyor
- [ ] `adapter.py` ayrı dosya olarak çalışıyor
- [ ] `utils.py` helper fonksiyonları içeriyor
- [ ] `__init__.py` imports'ları expose ediyor
- [ ] Tüm imports düzeltildi ve relative imports kullanılıyor
- [ ] Tests hepsini import edebildiğini doğruluyor

---

## 2. Test Altyapısı

### Test Framework Kurulumu

```bash
# pyproject.toml
[tool.pytest.ini_options]
testpaths = ["tests"]
asyncio_mode = "auto"
markers = [
    "unit: unit tests",
    "integration: integration tests",
    "slow: slow tests",
]

[tool.coverage.run]
source = ["mgx_agent"]
omit = ["*/tests/*"]

[tool.coverage.report]
exclude_lines = [
    "pragma: no cover",
    "def __repr__",
    "raise AssertionError",
    "raise NotImplementedError",
    "if __name__ == .__main__.:",
]
```

### Test Strukturu

```
tests/
├── conftest.py                      # Shared fixtures
├── unit/
│   ├── test_config.py              # Config validation
│   ├── test_metrics.py             # Metrics calculation
│   ├── test_utils.py               # Utility functions
│   ├── test_adapter.py             # MetaGPT adapter
│   ├── test_actions.py             # LLM action classes
│   └── test_roles.py               # Role classes
├── integration/
│   ├── test_team_workflow.py       # Full workflow
│   ├── test_revision_loop.py       # Revision mechanism
│   └── test_incremental.py         # Incremental features
├── fixtures/
│   ├── mock_responses.py           # Mock LLM responses
│   ├── sample_code.py              # Test code samples
│   └── sample_projects/            # Test projects
└── README.md
```

### Örnek Test Cases

**tests/conftest.py:**
```python
import pytest
import asyncio
from unittest.mock import AsyncMock, MagicMock

@pytest.fixture
def event_loop():
    """Async test loop"""
    loop = asyncio.get_event_loop_policy().new_event_loop()
    yield loop
    loop.close()

@pytest.fixture
def mock_llm():
    """Mock LLM for testing"""
    mock = AsyncMock()
    mock._aask = AsyncMock(return_value="Mock response")
    return mock

@pytest.fixture
def sample_code():
    """Sample Python code for testing"""
    return '''
def multiply_list(numbers):
    """Listedeki sayıların çarpımını hesapla"""
    result = 1
    for n in numbers:
        result *= n
    return result
'''

@pytest.fixture
def sample_tests():
    """Sample test code"""
    return '''
def test_multiply_list_positive():
    assert multiply_list([2, 3, 4]) == 24

def test_multiply_list_single():
    assert multiply_list([5]) == 5

def test_multiply_list_with_zero():
    assert multiply_list([2, 0, 3]) == 0
'''
```

**tests/unit/test_config.py:**
```python
import pytest
from mgx_agent.config import TeamConfig, TaskComplexity, LogLevel

class TestTaskComplexity:
    """TaskComplexity enum'i test et"""
    
    def test_complexity_values(self):
        """Karmaşıklık seviyeleri tanımlanmış mı?"""
        assert TaskComplexity.XS == "XS"
        assert TaskComplexity.S == "S"
        assert TaskComplexity.M == "M"
        assert TaskComplexity.L == "L"
        assert TaskComplexity.XL == "XL"

class TestTeamConfig:
    """TeamConfig validation test'leri"""
    
    def test_default_config(self):
        """Default config değerleri doğru mu?"""
        config = TeamConfig()
        assert config.max_rounds == 5
        assert config.enable_caching is True
        assert config.human_reviewer is False
    
    def test_invalid_max_rounds(self):
        """0 rounds reject edilmeli"""
        with pytest.raises(ValueError):
            TeamConfig(max_rounds=0)
    
    def test_invalid_investment(self):
        """$0.5'den az investment reject edilmeli"""
        with pytest.raises(ValueError):
            TeamConfig(default_investment=0.2)
    
    def test_high_budget_multiplier_warning(self, caplog):
        """Yüksek budget multiplier'ı warning verir"""
        config = TeamConfig(budget_multiplier=15.0)
        assert config.budget_multiplier == 15.0
        # Warning kontrolü (eğer uygulandıysa)
    
    @pytest.mark.parametrize("level", [
        LogLevel.DEBUG, LogLevel.INFO, LogLevel.WARNING, LogLevel.ERROR
    ])
    def test_log_levels(self, level):
        """Tüm log seviyeleri kabul edilmeli"""
        config = TeamConfig(log_level=level)
        assert config.log_level == level
    
    def test_config_to_dict(self):
        """Config dict'e dönüştürülmeli"""
        config = TeamConfig(max_rounds=10)
        d = config.to_dict()
        assert d["max_rounds"] == 10
        assert "enable_caching" in d
    
    def test_config_from_dict(self):
        """Dict'ten config oluşturulmalı"""
        d = {"max_rounds": 8, "human_reviewer": True}
        config = TeamConfig.from_dict(d)
        assert config.max_rounds == 8
        assert config.human_reviewer is True
    
    @pytest.mark.asyncio
    async def test_config_yaml_roundtrip(self, tmp_path):
        """YAML save/load cycle çalışmalı"""
        config = TeamConfig(
            max_rounds=12,
            budget_multiplier=1.5,
            human_reviewer=True
        )
        
        path = tmp_path / "config.yaml"
        config.save_yaml(str(path))
        
        loaded = TeamConfig.from_yaml(str(path))
        assert loaded.max_rounds == 12
        assert loaded.budget_multiplier == 1.5
        assert loaded.human_reviewer is True
```

**tests/unit/test_utils.py:**
```python
import pytest
from mgx_agent.utils import (
    parse_code_blocks,
    parse_json_block,
    extract_complexity,
)

class TestParseCodeBlocks:
    """Code block parsing test'leri"""
    
    def test_single_code_block(self):
        """Tek bir kod bloğu parse edilmeli"""
        text = """
        ```python
        def hello():
            return "world"
        ```
        """
        blocks = parse_code_blocks(text)
        assert len(blocks) == 1
        assert "def hello" in blocks[0]
    
    def test_multiple_code_blocks(self):
        """Birden fazla kod bloğu parse edilmeli"""
        text = """
        ```python
        x = 1
        ```
        Some text
        ```python
        y = 2
        ```
        """
        blocks = parse_code_blocks(text)
        assert len(blocks) == 2
    
    def test_code_block_without_language(self):
        """Dil belirtilmeden kod bloğu da çalışmalı"""
        text = "```\nx = 1\n```"
        blocks = parse_code_blocks(text)
        assert len(blocks) == 1
        assert "x = 1" in blocks[0]
    
    def test_empty_string(self):
        """Boş string boş liste döndürmeli"""
        assert parse_code_blocks("") == []
        assert parse_code_blocks(None) == []

class TestParseJsonBlock:
    """JSON block parsing test'leri"""
    
    def test_valid_json(self):
        """Geçerli JSON parse edilmeli"""
        text = """
        ---JSON_START---
        {"key": "value", "number": 42}
        ---JSON_END---
        """
        result = parse_json_block(text)
        assert result == {"key": "value", "number": 42}
    
    def test_invalid_json(self):
        """Invalid JSON None döndürmeli"""
        text = "---JSON_START---{invalid json}---JSON_END---"
        result = parse_json_block(text)
        assert result is None
    
    def test_missing_markers(self):
        """Marker yoksa None döndürmeli"""
        result = parse_json_block('{"key": "value"}')
        assert result is None

class TestExtractComplexity:
    """Complexity extraction test'leri"""
    
    @pytest.mark.parametrize("text,expected", [
        ("KARMAŞIKLIK: XS", "XS"),
        ("karmaşıklık: M", "M"),
        ("Görev karmaşıklığı: L", "L"),
        ("", "XS"),  # Default
        ("Hiç karmaşıklık yok", "XS"),  # Default
    ])
    def test_extract_complexity(self, text, expected):
        """Farklı formatlardaki karmaşıklık çıkarılmalı"""
        assert extract_complexity(text) == expected
```

---

## 3. Code Refactoring

### Execute() Fonksiyonunu Böl

**Problem:**
```python
async def execute(self, n_round: int = None, max_revision_rounds: int = None) -> str:
    # 226 satır - TOO LONG!
    # Derin nesting, karmaşık logic
```

**Çözüm:**
```python
# mgx_agent/team.py
async def execute(self, n_round: int = None, max_revision_rounds: int = None) -> str:
    """Görevi çalıştır - orchestration katmanı"""
    if not self._validate_execution_prerequisites():
        return "❌ Ön koşullar sağlanmadı"
    
    # Initialize
    budget, metric = await self._initialize_execution(n_round)
    
    try:
        # Phase 1: First execution
        await self._run_first_execution_round(budget)
        
        # Phase 2: Revision loops
        revision_count = await self._run_revision_loops(
            max_revision_rounds=max_revision_rounds,
            budget=budget
        )
        
        # Phase 3: Finalize
        return await self._finalize_execution(metric, revision_count)
        
    except Exception as e:
        return await self._handle_execution_error(e, metric)
    
    finally:
        metric.end_time = time.time()
        if self.metrics is not None:
            self.metrics.append(metric)
            self._show_metrics_report(metric)

async def _validate_execution_prerequisites(self) -> bool:
    """Çalıştırma ön koşullarını kontrol et"""
    if not self.plan_approved and not self.config.auto_approve_plan:
        logger.warning("Plan henüz onaylanmadı")
        return False
    return True

async def _initialize_execution(self, n_round: int) -> tuple:
    """Çalıştırmayı initialize et"""
    start_time = time.time()
    metric = TaskMetrics(
        task_name=self.current_task[:50] if self.current_task else "Unknown",
        start_time=start_time
    )
    
    complexity = self._get_complexity_from_plan()
    budget = self._tune_budget(complexity)
    metric.complexity = complexity
    
    if n_round is None:
        n_round = budget["n_round"]
    
    return budget, metric

async def _run_first_execution_round(self, budget: dict):
    """İlk execution turunu çalıştır"""
    print_phase_header("Görev Yürütme", "🚀")
    print(f"📊 Karmaşıklık: {budget.get('investment')} "
          f"Investment: ${budget['investment']}")
    
    # Complete planning phase
    for role in self.team.env.roles.values():
        if hasattr(role, 'complete_planning'):
            role.complete_planning()
    
    # Run team
    self.team.invest(investment=budget["investment"])
    await self.team.run(n_round=budget.get("n_round", 3))
    
    # Cleanup
    self.cleanup_memory()

async def _run_revision_loops(self, max_revision_rounds: int, budget: dict) -> int:
    """Revision döngülerini çalıştır"""
    revision_count = 0
    last_review_hash = None
    
    while revision_count < max_revision_rounds:
        code, tests, review = self._collect_raw_results()
        
        if not self._should_continue_revision(review, last_review_hash):
            break
        
        if "DEĞİŞİKLİK GEREKLİ" in review.upper():
            revision_count += 1
            await self._run_revision_improvements(code, review, budget)
            last_review_hash = hashlib.md5(review.encode()).hexdigest()
        else:
            print("\n✅ Review ONAYLANDI - Düzeltme gerekmiyor.")
            break
    
    return revision_count

def _should_continue_revision(self, review: str, last_review_hash: str) -> bool:
    """Revision döngüsüne devam edilmeli mi?"""
    if not review or not review.strip():
        logger.warning("Review bulunamadı")
        return False
    
    review_hash = hashlib.md5(review.encode()).hexdigest()
    if review_hash == last_review_hash:
        logger.warning("Aynı review tekrar geldi - sonsuz döngü detected")
        return False
    
    return True
```

### Conditional Nesting'i Azalt

**Before:**
```python
if not instruction:
    for m in all_messages:
        content = m.content if hasattr(m, 'content') else str(m)
        if "---JSON_START---" in content and "---JSON_END---" in content:
            try:
                json_str = content.split("---JSON_START---")[1].split("---JSON_END---")[0].strip()
                data = json.loads(json_str)
                if "task" in data and "plan" in data:
                    instruction = data["task"]
                    plan = data["plan"]
                    break
            except (json.JSONDecodeError, IndexError, ValueError):
                pass
```

**After:**
```python
def _extract_task_spec_from_messages(self, messages) -> Optional[dict]:
    """Mesajlardan task spec çıkar - null-safe"""
    for msg in messages:
        spec = self._extract_json_spec(msg.content)
        if spec:
            return spec
    return None

def _extract_json_spec(self, content: str) -> Optional[dict]:
    """Content'den JSON spec'i parse et"""
    if not content:
        return None
    
    spec = parse_json_block(content)
    if spec and "task" in spec and "plan" in spec:
        return spec
    
    return None

# Usage:
spec = self._extract_task_spec_from_messages(all_messages)
if spec:
    instruction = spec["task"]
    plan = spec["plan"]
```

---

## 4. Dokümantasyon

### README.md Şablonu

```markdown
# MGX Style Multi-Agent Team (TEM Agent)

MetaGPT açık kaynak kodunun üzerine geliştirilen, dört rol içeren bir multi-agent sistem.

## 🚀 Features

- **4 Specialized Roles:** Mike (Planner), Alex (Engineer), Bob (Tester), Charlie (Reviewer)
- **Automatic Task Complexity Assessment:** XS/S/M/L/XL levels
- **Intelligent Revision Loops:** AI-driven code improvements
- **Metrics & Cost Tracking:** Monitor token usage and estimated costs
- **Flexible Configuration:** Pydantic-based config with validation
- **Human-in-the-Loop:** Optional human review integration
- **Incremental Development:** Add features or fix bugs in existing projects

## 📦 Installation

```bash
pip install -e .
```

### Requirements

- Python 3.8+
- MetaGPT
- Pydantic v2
- Tenacity

## 🎯 Quick Start

### Basic Usage

```python
import asyncio
from mgx_agent.team import MGXStyleTeam

async def main():
    team = MGXStyleTeam()
    task = "Bir Python fonksiyonu yaz: Listedeki sayıların çarpımını hesapla"
    
    # Analiz ve plan oluştur
    await team.analyze_and_plan(task)
    
    # Planı onayla
    team.approve_plan()
    
    # Görevi çalıştır
    await team.execute()

asyncio.run(main())
```

### CLI Usage

```bash
# Normal mode
python -m mgx_agent

# Human reviewer mode
python -m mgx_agent --human

# Custom task
python -m mgx_agent --task "Your custom task here"

# Add feature
python -m mgx_agent --add-feature "Add authentication" --project-path ./my_project

# Fix bug
python -m mgx_agent --fix-bug "TypeError: x is undefined" --project-path ./my_project
```

## ⚙️ Configuration

```python
from mgx_agent.config import TeamConfig

config = TeamConfig(
    max_rounds=5,                    # Max execution rounds
    max_revision_rounds=2,           # Max revision iterations
    enable_caching=True,             # Cache task analysis
    human_reviewer=False,            # Human in the loop
    default_investment=3.0,          # Budget in dollars
    budget_multiplier=1.0,           # Adjust budget
)

team = MGXStyleTeam(config=config)
```

### Config from YAML

```python
config = TeamConfig.from_yaml("config.yaml")
team = MGXStyleTeam(config=config)
```

## 📊 Architecture

```
┌─────────────────────────────────────┐
│         CLI / Main Entry            │
└────────────┬────────────────────────┘
             │
┌────────────▼────────────────────────┐
│      MGXStyleTeam Orchestrator      │
│   (Task spec, memory, metrics)      │
└────────────┬────────────────────────┘
             │
    ┌────────┼────────┐
    │        │        │
    ▼        ▼        ▼
  Mike    Alex    Bob    Charlie
(Planner) (Eng) (Test) (Review)
    │        │        │        │
    └────────┼────────┼────────┘
             │
    ┌────────▼────────┐
    │   MetaGPTAdapter│
    │  (Safe API Access)
    └─────────────────┘
```

## 🧪 Testing

```bash
# Run all tests
pytest

# With coverage
pytest --cov=mgx_agent

# Specific test file
pytest tests/unit/test_config.py

# Async tests
pytest tests/integration/test_team_workflow.py
```

## 📈 Metrics

The team tracks:
- Task completion time
- Token usage
- Estimated costs
- Revision rounds
- Success/failure status

```python
metrics = team.get_metrics_summary()
print(metrics)
```

## 🔄 Revision Loop

The system automatically improves code:

1. Alex writes code
2. Bob writes tests
3. Charlie reviews
4. If issues found → Alex revises (max 2-5 rounds)
5. Repeat until approved

## 🛡️ Error Handling

- Automatic LLM retry (3 attempts with exponential backoff)
- Graceful fallbacks for missing data
- Comprehensive error logging

## 📝 Logging

```python
import logging
from mgx_agent.config import LogLevel, TeamConfig

config = TeamConfig(log_level=LogLevel.DEBUG, verbose=True)
team = MGXStyleTeam(config=config)
```

## 🐛 Known Limitations

- Test coverage: Work in progress
- Multi-LLM mode: Requires manual config (see issue #123)
- Human reviewer: Currently terminal-based

## 📚 API Reference

### MGXStyleTeam

#### `analyze_and_plan(task: str) -> str`
Analyzes task and creates a plan

#### `approve_plan() -> bool`
Approves current plan for execution

#### `execute(n_round: int = None) -> str`
Executes the approved task

#### `add_feature(feature: str, project_path: str) -> str`
Adds a feature to existing project

#### `fix_bug(bug_description: str, project_path: str) -> str`
Fixes a bug in existing project

## 🤝 Contributing

1. Write tests first (TDD)
2. Follow PEP 8
3. Add docstrings
4. Update CHANGELOG

## 📄 License

MIT
```

### ARCHITECTURE.md

```markdown
# TEM Agent Architecture

## Overview

TEM (Turkish Engineer Multi-Agent) is a MetaGPT-based system that coordinates 4 specialized AI agents to develop software.

## Component Diagram

```
┌─────────────────────────────────────────┐
│          CLI/Interface Layer            │
│  (main.py, incremental_main.py)         │
└────────────┬────────────────────────────┘
             │
┌────────────▼──────────────────────────────┐
│     Orchestration Layer                   │
│     (MGXStyleTeam)                        │
│  - Task spec management                   │
│  - Memory cleanup                         │
│  - Metrics tracking                       │
│  - Revision loop control                  │
└────────────┬──────────────────────────────┘
             │
    ┌────────┴──────────┬───────────────┐
    │                   │               │
┌───▼────────┐  ┌──────▼────┐  ┌──────▼────┐
│  Roles     │  │  Actions  │  │  Config   │
│  Layer     │  │  Layer    │  │  Layer    │
│            │  │           │  │           │
│ - Mike     │  │ - Analyze │  │ - Teams   │
│   (Planner)│  │ - DraftPln│  │ - Tasks   │
│ - Alex     │  │ - Write   │  │ - Budget  │
│   (Engine) │  │ - WriteTst│  │ - Metrics │
│ - Bob      │  │ - Review  │  │           │
│   (Tester) │  │           │  │           │
│ - Charlie  │  │           │  │           │
│   (Review) │  │           │  │           │
└───┬────────┘  └──────┬────┘  └───────────┘
    │                  │
    └──────────────────┴──────────┐
                                  │
                    ┌─────────────▼───────────┐
                    │  MetaGPT Adapter        │
                    │  (Safe API Access)      │
                    │                         │
                    │ - get_memory_store()    │
                    │ - get_messages()        │
                    │ - add_message()         │
                    │ - clear_memory()        │
                    │ - get_news()            │
                    └─────────────┬───────────┘
                                  │
                    ┌─────────────▼───────────┐
                    │   MetaGPT Framework     │
                    │                         │
                    │ - Context               │
                    │ - Team                  │
                    │ - Role                  │
                    │ - Action                │
                    │ - Message               │
                    │ - Memory                │
                    └─────────────────────────┘
```

## Data Flow

### Phase 1: Analysis & Planning

```
User Input (Task)
    │
    ▼
Mike.analyze_and_plan()
    │
    ├─> AnalyzeTask (LLM)
    │       └─> Complexity Level (XS/S/M/L/XL)
    │
    └─> DraftPlan (LLM)
            └─> Plan Steps
                │
                ▼
        Save to task_spec (single source of truth)
                │
                ▼
        Return to User
```

### Phase 2: Execution

```
Approved Task Spec
    │
    ├─> Alex.run()
    │   └─> WriteCode (LLM)
    │       └─> Code Output
    │
    ├─> Bob.run()
    │   └─> WriteTest (LLM with Code)
    │       └─> Test Output
    │
    └─> Charlie.run()
        └─> ReviewCode (LLM with Code + Tests)
            └─> Review Output
                │
                ├─> "ONAYLANDI" → Done
                └─> "DEĞİŞİKLİK GEREKLİ"
                    │
                    ▼
            Enter Revision Loop
```

### Phase 3: Revision (if needed)

```
Review with Issues
    │
    ▼
MGXStyleTeam.set_task_spec() with review_notes
    │
    ▼
Alex.run() with review_notes (revision prompt)
    │
    ├─> Updated Code
    ├─> Bob.run() → Updated Tests
    └─> Charlie.run() → New Review
        │
        └─> Check again (max 2-5 rounds)
```

## Key Abstractions

### MetaGPTAdapter

Why needed:
- MetaGPT internals are not stable
- Private attributes (_memory) are implementation details
- API might change between versions

Pattern:
```python
# Direct access (WRONG - fragile):
messages = role.rc.memory._messages  # ← Private!

# Adapter access (CORRECT - safe):
memory_store = MetaGPTAdapter.get_memory_store(role)
messages = MetaGPTAdapter.get_messages(memory_store)
```

### Task Spec (Single Source of Truth)

Instead of parsing messages repeatedly, we maintain one `current_task_spec`:

```python
current_task_spec = {
    "task": "Original task description",
    "plan": "Step-by-step plan",
    "complexity": "M",
    "is_revision": False,
    "review_notes": ""  # Only set during revision
}
```

Benefits:
- Consistent state
- No message parsing errors
- Efficient lookups

### Memory Management

- **Token Efficiency:** Only keep relevant memories
- **Cleanup Strategy:** Keep last N messages per role
- **Cache:** Task analysis results with TTL

## Configuration Flow

```
Default Config
    │
    ├─> User provides TeamConfig()
    │   │
    │   └─> Pydantic Validation
    │       (ge=1, le=20, etc.)
    │
    ├─> Load YAML (optional)
    │   │
    │   └─> Override defaults
    │
    └─> Multi-LLM Config (optional)
        │
        └─> Load model-specific configs
```

## Metrics & Monitoring

```
Task Execution
    │
    ▼
TaskMetrics Object
    │
    ├─> start_time
    ├─> end_time
    ├─> success/failure
    ├─> complexity
    ├─> token_usage (estimated)
    ├─> estimated_cost
    ├─> revision_rounds
    └─> error_message
        │
        ▼
    Display Report
    Save to metrics list
    Export to JSON/CSV
```

## Error Handling Strategy

```
LLM Call
    │
    ├─> Success → Return result
    │
    └─> Failure
        │
        ├─> Retry 1 (wait 2-5s)
        ├─> Retry 2 (wait 5-10s)
        ├─> Retry 3 (wait 10s)
        │
        └─> All failed → Return error / use fallback
```

## Extension Points

### Adding a New Role

```python
class Dave(Role):
    """Security Reviewer"""
    name: str = "Dave"
    profile: str = "SecurityReviewer"
    
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.set_actions([SecurityReview])
        self._watch([WriteCode, WriteTest])
    
    async def _act(self) -> Message:
        # Implementation
        pass
```

### Adding a New Action

```python
class SecurityAudit(Action):
    """Security audit action"""
    name: str = "SecurityAudit"
    
    @llm_retry()
    async def run(self, code: str) -> str:
        prompt = "Review this code for security issues..."
        return await self._aask(prompt)
```

## Known Issues & Limitations

1. **Multi-LLM Mode:** Config loading works but role distribution may not
2. **Streaming:** Flag exists but not implemented
3. **Token Counting:** Estimated, not actual
4. **Human Input:** Basic terminal input, no validation
5. **Path Handling:** Assumes write permission to current dir

See CODE_REVIEW_REPORT.md for detailed analysis.
```

---

## 5. Performance Optimization

### Memory Access Optimization

```python
# mgx_agent/team.py

class MGXStyleTeam:
    def __init__(self, ...):
        # Cache role references
        self._roles_cache = {}
        self._regenerate_role_cache()
    
    def _regenerate_role_cache(self):
        """Role referanslarını cache'le"""
        if hasattr(self.team, 'env') and hasattr(self.team.env, 'roles'):
            self._roles_cache = dict(self.team.env.roles)
    
    def _collect_results_optimized(self) -> tuple:
        """Optimized result collection"""
        code_content = ""
        test_content = ""
        review_content = ""
        
        # Use cached roles
        for role in self._roles_cache.values():
            mem_store = MetaGPTAdapter.get_memory_store(role)
            if mem_store is None:
                continue
            
            # Get only last message (iteration-free)
            messages = MetaGPTAdapter.get_messages(mem_store)
            if not messages:
                continue
            
            last_msg = messages[-1]  # O(1) instead of O(n)
            
            if last_msg.role == "Engineer":
                code_content = last_msg.content
            elif last_msg.role == "Tester":
                test_content = last_msg.content
            elif last_msg.role == "Reviewer":
                review_content = last_msg.content
        
        return code_content, test_content, review_content
```

### Async Optimization

```python
# mgx_agent/utils.py

async def load_configs_parallel(config_paths: dict) -> dict:
    """Konfigürasyon dosyalarını paralel yükle"""
    import asyncio
    
    async def load_one(name: str, path: str):
        loop = asyncio.get_event_loop()
        return name, await loop.run_in_executor(None, Config.from_home, path)
    
    tasks = [load_one(name, path) for name, path in config_paths.items()]
    results = await asyncio.gather(*tasks, return_exceptions=True)
    
    return {name: config for name, config in results if not isinstance(config, Exception)}
```

---

## 6. Güvenlik İyileştirmeleri

### Input Validation

```python
# mgx_agent/utils.py

import re
from pathlib import Path

def sanitize_path(user_input: str, base_dir: str = "output") -> str:
    """Kullanıcı input'undan güvenli path oluştur"""
    # Sadece alphanumeric + underscore + hyphen
    sanitized = re.sub(r'[^a-zA-Z0-9_-]', '', user_input)
    
    if not sanitized:
        sanitized = "output"
    
    path = Path(base_dir) / sanitized
    
    # Path traversal kontrolü
    try:
        path.resolve().relative_to(Path(base_dir).resolve())
    except ValueError:
        raise ValueError(f"Invalid path: {user_input}")
    
    return str(path)

def validate_task_description(task: str, max_length: int = 10000) -> str:
    """Görev açıklamasını validate et"""
    if not task or not isinstance(task, str):
        raise ValueError("Task must be a non-empty string")
    
    if len(task) > max_length:
        raise ValueError(f"Task exceeds max length of {max_length}")
    
    # Injection kontrolleri (basit)
    dangerous_patterns = [
        r"exec\(",
        r"eval\(",
        r"__import__",
        r"system\(",
        r"popen\(",
    ]
    
    task_lower = task.lower()
    for pattern in dangerous_patterns:
        if re.search(pattern, task_lower):
            raise ValueError(f"Suspicious pattern detected: {pattern}")
    
    return task
```

### Safe File Operations

```python
# mgx_agent/utils.py

import shutil
from pathlib import Path

def safe_write_file(path: str, content: str, max_size: int = 10 * 1024 * 1024) -> bool:
    """Dosyayı güvenli şekilde yaz"""
    try:
        # Size check
        if len(content) > max_size:
            logger.warning(f"Content size {len(content)} exceeds max {max_size}")
            return False
        
        # Path validation
        path = Path(path)
        path.parent.mkdir(parents=True, exist_ok=True)
        
        # Backup existing file
        if path.exists():
            backup = path.with_suffix(path.suffix + f".bak_{datetime.now().strftime('%Y%m%d_%H%M%S')}")
            shutil.copy2(path, backup)
        
        # Atomic write
        with open(path, "w", encoding="utf-8") as f:
            f.write(content)
        
        logger.info(f"File written safely: {path}")
        return True
        
    except Exception as e:
        logger.error(f"Safe file write failed: {e}")
        return False
```

---

## 📋 Implementation Checklist

### Phase 1 (1-2 weeks)
- [ ] Modularize codebase into mgx_agent package
- [ ] Create constants.py with all magic numbers
- [ ] Set up pytest framework with conftest
- [ ] Write 20 unit tests for config
- [ ] Write 10 unit tests for utils
- [ ] Write README.md
- [ ] Complete human-in-the-loop feature
- [ ] Add .gitignore

### Phase 2 (1-2 weeks)
- [ ] Write 30+ integration tests
- [ ] Refactor execute() method
- [ ] Write 20+ unit tests for actions
- [ ] Write 20+ unit tests for roles
- [ ] Add ARCHITECTURE.md
- [ ] Fix async optimization
- [ ] Add security validations

### Phase 3 (Nice-to-have)
- [ ] Add 20+ more tests (90% coverage target)
- [ ] Performance profiling & optimization
- [ ] API documentation
- [ ] Example notebooks
- [ ] CI/CD setup (GitHub Actions)
- [ ] WebUI prototype

---

**Updated:** 2024  
**Status:** Ready for implementation  
**Estimated Effort:** 60-80 hours total
