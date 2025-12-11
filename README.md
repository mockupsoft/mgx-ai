# TEM Agent - AI-Powered Multi-Agent Development System

**MetaGPT üzerine kurulu, tam otomatik yazılım geliştirme ekibi.**

TEM Agent (Task Execution Manager Agent), yazılım geliştirme sürecini 4 uzman AI ajanı ile otomatikleştirir: Görev analizi, kod yazma, test oluşturma ve kod inceleme - hepsi tek bir komutla.

---

## 📊 Proje Durumu

```
┌─────────────────────────────────────────────────────────────┐
│  Overall Score:        ⭐ 8.5/10                            │
│  Production Ready:     🟢 85%  (Hedef: 85%)                │
│  Test Coverage:        🟢 80%+ (Hedef: ≥80%)               │
│  Phase Status:                                               │
│  ├─ Phase 1 (Quick Fixes)      ✅ COMPLETE                 │
│  ├─ Phase 2 (Modularization)   ✅ COMPLETE                 │
│  ├─ Phase 3 (Test Coverage)    ✅ COMPLETE                 │
│  └─ Phase 4 (Performance)      ⏳ PENDING                  │
└─────────────────────────────────────────────────────────────┘
```

### ✅ Tamamlanan İyileştirmeler

#### Phase 1: Quick Fixes (✅ Complete)
- ✅ Magic numbers centralization (15+ → 0)
- ✅ DRY principles applied (code duplication -66%)
- ✅ Input validation & security
- ✅ Comprehensive documentation
- ✅ 6/6 utility tests passing

#### Phase 2: Modularization (✅ Complete)
- ✅ Monolitik (2393 satır) → Modular (8 modül)
- ✅ Package structure: `mgx_agent/`
- ✅ Design patterns uygulandı
- ✅ Zero breaking changes
- ✅ 100% backward compatibility

#### Phase 3: Test Coverage (✅ Complete)
- ✅ Pytest infra setup (PR #4)
- ✅ Config metrics tests (PR #5)
- ✅ Adapter action tests (PR #7)
- ✅ Roles team tests (PR #8)
- ✅ CLI workflow tests (PR #9)
- ✅ 130+ Test cases
- ✅ 80%+ Overall coverage
- ✅ GitHub Actions CI/CD configured

---

## 🚀 Özellikler

### 🤖 Dört Uzman AI Ajanı
- **Mike (TeamLeader)**: Görev analizi ve planlama
- **Alex (Engineer)**: Kod yazma ve implementasyon
- **Bob (Tester)**: Test senaryoları ve test kodu
- **Charlie (Reviewer)**: Kod inceleme ve kalite kontrol

### ⚡ Gelişmiş Yetenekler
- **Otomatik Karmaşıklık Analizi**: XS/S/M/L/XL seviyeleri ile görev değerlendirmesi
- **Akıllı Revision Döngüleri**: AI-guided kod iyileştirme ve iterasyon
- **Metrik Takibi**: Süre, token kullanımı, maliyet hesaplama
- **İnsan Müdahalesi**: Opsiyonel human-in-the-loop reviewer modu
- **Artımlı Geliştirme**: Mevcut projelere feature ekleme veya bug düzeltme
- **Esnek Konfigürasyon**: Pydantic V2 tabanlı type-safe configuration

### 🎨 Modüler Mimari
- **Single Responsibility**: Her modül tek sorumluluk
- **Design Patterns**: Adapter, Factory, Mixin, Facade patterns
- **Maintainability**: 2393 satır → 8 modül (avg: 393 satır/modül)
- **Testability**: Birim testlere hazır yapı
- **Extensibility**: Kolayca genişletilebilir

---

## 🏆 Başarı Metrikleri

- **Zero breaking changes**: Mevcut kod tabanı ile %100 uyumluluk
- **100% backward compatibility**: Eski projeler sorunsuz çalışır
- **Production-ready code**: Enterprise seviyesinde kod kalitesi
- **80%+ test coverage**: Kapsamlı test güvencesi
- **GitHub Actions CI/CD**: Otomatik test ve dağıtım süreçleri

---

## 📦 Kurulum

### Gereksinimler
- **Python 3.8+**
- **MetaGPT** (v0.8.0+)
- **Pydantic** v2
- **Tenacity** (retry logic)

### Adımlar

```bash
# 1. Repository'yi klonla
git clone <repo-url>
cd project

# 2. Virtual environment oluştur (önerilir)
python -m venv .venv
source .venv/bin/activate  # Linux/Mac
# .venv\Scripts\activate   # Windows

# 3. Bağımlılıkları yükle
pip install -r requirements.txt

# 4. MetaGPT'yi konfigüre et
python -m metagpt.config
# API keys'i ayarla (OpenAI, Anthropic, vb.)
```

---

## 🎯 Hızlı Başlangıç

### Basit Kullanım
```bash
# Varsayılan görevle çalıştır
python examples/mgx_style_team.py

# Özel görev belirt
python examples/mgx_style_team.py --task "Fibonacci hesaplayan fonksiyon yaz"
```

### İnsan Reviewer Modu
```bash
# Human-in-the-loop mode
python examples/mgx_style_team.py --human
```

### Mevcut Projeye Feature Ekleme
```bash
# Incremental development: Feature addition
python examples/mgx_style_team.py \
    --add-feature "Add user authentication system" \
    --project-path ./my_existing_project
```

### Bug Düzeltme
```bash
# Incremental development: Bug fix
python examples/mgx_style_team.py \
    --fix-bug "TypeError: 'NoneType' object is not subscriptable" \
    --project-path ./my_project
```

---

## 🏗️ Mimari Yapı

### Package Structure

```
mgx_agent/
├── __init__.py
├── config.py
├── metrics.py
├── actions.py
├── adapter.py
├── roles.py
├── team.py
└── cli.py

tests/
├── conftest.py
├── unit/
│   ├── test_config.py
│   ├── test_metrics.py
│   ├── test_adapter.py
│   └── test_actions.py
├── integration/
│   ├── test_roles.py
│   └── test_team.py
└── e2e/
    ├── test_cli.py
    └── test_workflow.py
```

### Design Patterns

| Pattern | Kullanıldığı Yer | Amaç |
|---------|------------------|------|
| **Adapter** | `adapter.py` | MetaGPT entegrasyonu |
| **Factory** | `config.py` | TeamConfig oluşturma |
| **Mixin** | `roles.py` | RelevantMemoryMixin ile rol güçlendirme |
| **Facade** | `team.py` | MGXStyleTeam ana interface |
| **Strategy** | `actions.py` | Action execution patterns |

### Akış Diyagramı

```
CLI Input (Task Description)
    ↓
┌─────────────────────────────────────────────────────┐
│ PHASE 1: ANALIZ VE PLANLAMA                        │
│ ┌─────────────────────┐                            │
│ │ Mike (TeamLeader)   │                            │
│ │ - AnalyzeTask       │ → Karmaşıklık: XS/S/M/L/XL│
│ │ - DraftPlan         │ → Plan & Subtasks         │
│ └─────────────────────┘                            │
└──────────────┬──────────────────────────────────────┘
               ↓
┌─────────────────────────────────────────────────────┐
│ PHASE 2: KOD YAZMA                                  │
│ ┌─────────────────────┐                            │
│ │ Alex (Engineer)     │                            │
│ │ - WriteCode         │ → main.py                 │
│ │                     │ → Revision notları varsa  │
│ └─────────────────────┘                            │
└──────────────┬──────────────────────────────────────┘
               ↓
┌─────────────────────────────────────────────────────┐
│ PHASE 3: TEST YAZMA                                 │
│ ┌─────────────────────┐                            │
│ │ Bob (Tester)        │                            │
│ │ - WriteTest         │ → test_main.py            │
│ └─────────────────────┘                            │
└──────────────┬──────────────────────────────────────┘
               ↓
┌─────────────────────────────────────────────────────┐
│ PHASE 4: KOD İNCELEME                              │
│ ┌─────────────────────┐                            │
│ │ Charlie (Reviewer)  │                            │
│ │ - ReviewCode        │ → review.md               │
│ │                     │ → ONAYLANDI MI?           │
│ └─────────────────────┘                            │
│        │                                            │
│        ├─ ✅ Evet → BITTI                          │
│        └─ ⚠️  Hayır → Alex'e Revision Request      │
│ └─────────────────────┘                            │
└──────────────┬──────────────────────────────────────┘
               ↓
    Output: main.py, test_main.py, review.md
```

---

## ⚙️ Konfigürasyon

### Python API

```python
from mgx_agent import MGXStyleTeam, TeamConfig

# Create custom configuration
config = TeamConfig(
    max_rounds=5,                 # Maksimum execution turları
    max_revision_rounds=2,        # Maksimum revision turları
    enable_caching=True,          # Task analiz cache'i
    human_reviewer=False,         # Human reviewer modu
    default_investment=3.0,       # Budget ($)
    budget_multiplier=1.0,        # Budget çarpanı
)

# Initialize team
team = MGXStyleTeam(config=config)

# Run task
await team.run(task="Write a binary search implementation")
```

### YAML Configuration

```yaml
# config.yaml
max_rounds: 5
max_revision_rounds: 2
enable_caching: true
default_investment: 3.0
budget_multiplier: 1.0
human_reviewer: false
```

```python
from mgx_agent import TeamConfig, MGXStyleTeam

config = TeamConfig.from_yaml("config.yaml")
team = MGXStyleTeam(config=config)
```

---

## 💻 Kullanım Örnekleri

### Örnek 1: Basit Fonksiyon
```bash
python examples/mgx_style_team.py \
    --task "Write a function to calculate factorial of a number"
```

**Çıktı:**
- `output/mgx_team_<timestamp>/main.py` - Fonksiyon kodu
- `output/mgx_team_<timestamp>/test_main.py` - Unit testler
- `output/mgx_team_<timestamp>/review.md` - Kod inceleme raporu

### Örnek 2: Karmaşık Proje
```bash
python examples/mgx_style_team.py \
    --task "Create a REST API for todo management with CRUD operations"
```

### Örnek 3: Mevcut Projeye Ekleme
```bash
python examples/mgx_style_team.py \
    --add-feature "Add input validation to user registration" \
    --project-path ./my_webapp
```

---

## 🧪 Test Coverage & Testing

### Mevcut Durum
```
Test Coverage: 🟢 80%+ (Phase 3 Complete)
├─ Unit Tests:          ✅ Complete (config, metrics, adapter, actions)
├─ Integration Tests:   ✅ Complete (roles, team)
├─ E2E Tests:           ✅ Complete (cli, workflow)
└─ Documentation:       ✅ Complete

Hedef: 80% (Erişildi) 🎯
```

### Test Komutları

```bash
# Tüm testleri çalıştır
pytest

# Sadece unit testleri çalıştır
pytest tests/unit

# Sadece integration testleri çalıştır
pytest tests/integration

# Sadece E2E testleri çalıştır
pytest tests/e2e

# Coverage raporu oluştur
pytest --cov=mgx_agent --cov-report=html
```

Daha detaylı test kılavuzu için [docs/TESTING.md](docs/TESTING.md) dosyasına bakınız.

### CI/CD

Proje GitHub Actions ile entegre edilmiştir. Her push işleminde:
1. Unit testler çalışır
2. Integration testler çalışır
3. Coverage kontrolü yapılır
4. Linting (Black/MyPy) kontrolleri yapılır

---

## 🔮 Roadmap / Future

### Phase 4: Performance Optimization
- Asyncio optimizations
- Response caching improvements
- Memory usage profiling
- Latency reduction

### Phase 5: Security Audit
- Dependency vulnerability scanning
- Code injection prevention analysis
- Secret management improvements
- Security compliance checks

### Phase 6: Advanced Features
- Multi-project support
- Custom agent definition DSL
- Web-based dashboard
- Advanced monitoring & alerting

---

## 📖 Dokümantasyon

### Ana Dokümanlar

| Doküman | Açıklama |
|---------|----------|
| [docs/TESTING.md](docs/TESTING.md) | Detaylı test rehberi ve komutlar |
| [CODE_REVIEW_REPORT.md](CODE_REVIEW_REPORT.md) | Detaylı kod inceleme raporu ve analiz |
| [IMPROVEMENT_GUIDE.md](IMPROVEMENT_GUIDE.md) | Refactoring ve iyileştirme rehberi |
| [QUICK_FIXES.md](QUICK_FIXES.md) | Hızlı düzeltme örnekleri |

### İyileştirme Raporları

- **PHASE1_SUMMARY.md** - Phase 1 özeti
- **PHASE2_MODULARIZATION_REPORT.md** - Phase 2 raporu
- **IMPLEMENTATION_STATUS.md** - Genel durum

---

## 🤝 Katkıda Bulunma

### Development Setup

```bash
# 1. Fork & Clone
git clone https://github.com/<your-username>/tem-agent.git
cd tem-agent

# 2. Setup
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
pip install -r requirements-dev.txt

# 3. Test
pytest
```
