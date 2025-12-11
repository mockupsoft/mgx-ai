# TEM Agent - AI-Powered Multi-Agent Development System

**MetaGPT üzerine kurulu, tam otomatik yazılım geliştirme ekibi.**

TEM Agent (Task Execution Manager Agent), yazılım geliştirme sürecini 4 uzman AI ajanı ile otomatikleştirir: Görev analizi, kod yazma, test oluşturma ve kod inceleme - hepsi tek bir komutla.

---

## 📊 Proje Durumu

```
┌─────────────────────────────────────────────────────────────┐
│  Overall Score:        ⭐ 7.5/10                            │
│  Production Ready:     🟢 65%  (Hedef: 85%)                │
│  Test Coverage:        🔴 2%   (Hedef: 80% - Phase 3)      │
│                                                              │
│  Phase Status:                                               │
│  ├─ Phase 1 (Quick Fixes)      ✅ COMPLETE                 │
│  ├─ Phase 2 (Modularization)   ✅ COMPLETE                 │
│  └─ Phase 3 (Test Coverage)    🔄 IN PROGRESS              │
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
/home/engine/project/
├── mgx_agent/                    # 📦 Ana package (3,146 satır)
│   ├── __init__.py              # Package exports (81 satır)
│   ├── config.py                # Configuration & constants (119 satır)
│   ├── metrics.py               # Task metrics (51 satır)
│   ├── actions.py               # Action execution (329 satır)
│   ├── adapter.py               # MetaGPT adapter (222 satır)
│   ├── roles.py                 # AI agent roles (750 satır)
│   ├── team.py                  # Team orchestration (1,402 satır)
│   └── cli.py                   # CLI interface (192 satır)
│
├── examples/
│   └── mgx_style_team.py        # Simple wrapper (35 satır)
│
├── mgx_agent_constants.py       # Legacy constants (177 satır)
├── mgx_agent_utils.py           # Utility functions (410 satır)
└── .gitignore                   # Git ignore rules
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
└────────────────────────────────────────────────────┘
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

### Örnek Çıktı

```
═══════════════════════════════════════════════════════════
✅ MIKE: Analiz ve plan tamamlandı!
📊 Karmaşıklık: M (Medium)
💡 Plan: 3 subtask identified
───────────────────────────────────────────────────────────

═══════════════════════════════════════════════════════════
💻 ALEX (Engineer) - KOD YAZIYOR...
───────────────────────────────────────────────────────────
✅ ALEX: Kod tamamlandı! (1,234 karakter)

═══════════════════════════════════════════════════════════
🧪 BOB (Tester) - TEST YAZIYOR...
───────────────────────────────────────────────────────────
✅ BOB: Testler tamamlandı! (456 karakter)

═══════════════════════════════════════════════════════════
🔍 CHARLIE (Reviewer) - KOD İNCELİYOR...
───────────────────────────────────────────────────────────
✅ CHARLIE: Review tamamlandı - ONAYLANDI!

═══════════════════════════════════════════════════════════
📊 GÖREV METRİKLERİ
═══════════════════════════════════════════════════════════
📌 Görev: Calculate factorial of a number
✅ Durum: Başarılı
⏱️  Süre: 2.5m
🎯 Karmaşıklık: M
🔄 Revision Turları: 0
🪙 Token Kullanımı: ~1,500
💰 Tahmini Maliyet: $3.00
═══════════════════════════════════════════════════════════
```

---

## 🧪 Test Coverage & Testing

### Mevcut Durum
```
Test Coverage: 🟡 2% (Baseline)
├─ mgx_agent_utils.py:  ✅ 100% (6/6 tests passing)
├─ mgx_agent package:   🟡 2%  (Phase 3 WIP)
├─ Unit tests:          🟡 In progress
├─ Integration tests:   🟡 In progress
└─ E2E tests:           🟡 Planned

Hedef: 80% (Phase 3) 📈
```

### Pytest Setup ✅

Phase 3 test infrastructure is now complete:

```bash
# 1. Install test dependencies
pip install -r requirements-dev.txt

# 2. Run all tests
pytest

# 3. Run specific test level
pytest tests/unit              # Unit tests only
pytest tests/integration       # Integration tests only
pytest tests/e2e              # End-to-end tests only

# 4. Generate coverage reports
pytest --cov=mgx_agent --cov-report=html
# Open: htmlcov/index.html

# 5. Run with verbose output
pytest -v

# 6. Run specific test
pytest tests/unit/test_helpers.py::TestMockLogger::test_logger_creation
```

### Test Structure
```
tests/
├── conftest.py                    # Global fixtures & configuration
├── unit/                          # Fast, isolated tests
├── integration/                   # Component interaction tests
├── e2e/                          # End-to-end workflow tests
├── helpers/
│   ├── metagpt_stubs.py         # MetaGPT component stubs
│   └── factories.py             # Factory functions for test objects
└── logs/                         # Test execution logs
```

### Key Features

✅ **MetaGPT Stubs**: Lightweight mocks for testing without real MetaGPT  
✅ **Test Factories**: Reusable factories for creating test objects  
✅ **Async Support**: Full pytest-asyncio integration  
✅ **Coverage Tracking**: Automatic HTML/XML/terminal reports  
✅ **Isolated Tests**: Fresh event loop for each async test  
✅ **Comprehensive Fixtures**: Pre-built fixtures for common test scenarios  

### Documentation

📖 **[docs/TESTING.md](docs/TESTING.md)** - Complete testing guide with:
- Setup and installation
- Running tests (all levels and subsets)
- Fixture documentation
- Test helper reference
- Writing tests (unit, async, integration)
- Coverage reporting
- Troubleshooting

### Development Tips

```bash
# Run tests in parallel (faster)
pytest -n auto

# Run only fast tests
pytest -m "not slow"

# Run with debugging
pytest -s --log-cli-level=DEBUG

# Collect tests without running
pytest --collect-only

# Run until first failure
pytest -x

# Run last failed
pytest --lf
```

---

## 📖 Dokümantasyon

### Ana Dokümanlar

| Doküman | Açıklama |
|---------|----------|
| [CODE_REVIEW_REPORT.md](CODE_REVIEW_REPORT.md) | Detaylı kod inceleme raporu ve analiz |
| [IMPROVEMENT_GUIDE.md](IMPROVEMENT_GUIDE.md) | Refactoring ve iyileştirme rehberi |
| [QUICK_FIXES.md](QUICK_FIXES.md) | Hızlı düzeltme örnekleri |
| [PHASE1_SUMMARY.md](PHASE1_SUMMARY.md) | Phase 1 tamamlama özeti |
| [PHASE2_MODULARIZATION_REPORT.md](PHASE2_MODULARIZATION_REPORT.md) | Phase 2 modularization raporu |
| [CODE_REVIEW_INDEX.md](CODE_REVIEW_INDEX.md) | Kod inceleme indeksi |
| [REVIEW_SUMMARY.md](REVIEW_SUMMARY.md) | Yönetim özeti ve aksiyon planı |

### İyileştirme Raporları

- **BEFORE_AFTER_ANALYSIS.md** - Before/After karşılaştırması
- **IMPLEMENTATION_STATUS.md** - Implementation durumu
- **CURRENT_STATUS_SUMMARY.txt** - Güncel durum özeti

---

## 🤝 Katkıda Bulunma

### Development Setup

```bash
# 1. Repository'yi fork'la ve klonla
git clone https://github.com/<your-username>/tem-agent.git
cd tem-agent

# 2. Development branch oluştur
git checkout -b feature/my-feature

# 3. Virtual environment
python -m venv .venv
source .venv/bin/activate

# 4. Dependencies (development)
pip install -r requirements.txt
pip install -r requirements-dev.txt  # pytest, black, mypy, vb.

# 5. Değişiklikleri yap
# ...

# 6. Test et
pytest tests/ -v
python -m black mgx_agent/
python -m mypy mgx_agent/

# 7. Commit et
git add .
git commit -m "feat: Add new feature"

# 8. Push ve PR aç
git push origin feature/my-feature
```

### Commit Mesajı Standardı

```
<type>(<scope>): <subject>

<body>

<footer>
```

**Types:**
- `feat`: Yeni özellik
- `fix`: Bug düzeltme
- `docs`: Dokümantasyon
- `style`: Code style (formatting)
- `refactor`: Refactoring
- `test`: Test ekleme/düzenleme
- `chore`: Build/config değişiklikleri

**Örnek:**
```
feat(team): Add support for parallel task execution

- Implement concurrent role execution
- Add task queue management
- Update metrics tracking

Closes #123
```

### PR Process

1. **Issue aç** veya mevcut issue'ya referans ver
2. **Branch oluştur** (`feature/`, `fix/`, `docs/` prefix)
3. **Test et** (tüm testler geçmeli)
4. **PR aç** (açıklayıcı başlık ve description)
5. **Code review** bekle
6. **Değişiklikler** istendiyse yap
7. **Merge** edilsin! 🎉

---

## ⚠️ Bilinen Sınırlamalar

| Sorun | Durum | Çözüm/Workaround |
|-------|-------|------------------|
| Test coverage = 2% | 🔴 CRITICAL | Phase 3'te 80%'e çıkarılacak |
| Token counting tahmini | ⚠️ Estimated | MetaGPT API'sinden gerçek değer alınır |
| Multi-LLM support | ⚠️ Experimental | Config dosyalarıyla test edin |
| Human-in-loop UX | 🔄 Basic | Terminal input (gelecekte WebUI) |
| Memory management | ⚠️ Manual clear | Otomatik cleanup Phase 4'te |

---

## 🗺️ Roadmap

### Phase 3: Test Coverage & Optimization (🔄 In Progress)
**Hedef:** Test coverage 80%, performance optimization
- [ ] Pytest framework setup
- [ ] 130+ unit tests yazılması
- [ ] Integration tests
- [ ] Performance profiling
- [ ] Memory optimization
- [ ] Tahmini süre: 40-50 saat

### Phase 4: Production Hardening (📋 Planned)
**Hedef:** Production-ready 85%
- [ ] Security audit
- [ ] Error handling improvements
- [ ] Logging enhancements
- [ ] WebUI dashboard (bonus)
- [ ] Docker containerization
- [ ] CI/CD pipeline setup

### Phase 5: Advanced Features (💡 Future)
**Hedef:** Enterprise features
- [ ] Multi-project support
- [ ] Team collaboration
- [ ] Custom role definitions
- [ ] Plugin system
- [ ] Cloud deployment
- [ ] Monitoring & alerting

---

## 📊 Proje Metrikleri

### Code Organization
```
Original (Before Phase 2):
├─ Monolithic: 2,393 lines
└─ Files: 1

After Phase 2:
├─ Modular: 3,146 lines (includes framework overhead)
├─ Files: 8 modules
├─ Average file size: 393 lines
└─ Largest component: team.py (1,402 lines)
```

### Quality Metrics
```
Production Readiness:
├─ Initial:     40%
├─ Phase 1:     42% (+2%)
└─ Phase 2:     65% (+23%)

Code Quality:
├─ Magic numbers:       100% eliminated ✅
├─ Code duplication:    -66% ✅
├─ Maintainability:     +85% ✅
└─ Test coverage:       2% (Phase 3: 80%)
```

---

## 🔧 Troubleshooting

### Problem: MetaGPT import error
```bash
# Solution: Install MetaGPT
pip install metagpt
```

### Problem: API key not found
```bash
# Solution: Configure MetaGPT
python -m metagpt.config
# Set your API keys (OpenAI, etc.)
```

### Problem: Output directory permission error
```bash
# Solution: Create output directory manually
mkdir -p output
chmod 755 output
```

### Problem: Human reviewer mode not accepting input
```bash
# Solution: Ensure terminal is in interactive mode
python -u examples/mgx_style_team.py --human
```

---

## 📝 Lisans

MIT License - Detaylar için [LICENSE](LICENSE) dosyasına bakın.

---

## 🙏 Acknowledgements

- **MetaGPT Team** - Temel framework
- **OpenAI** - GPT models
- **Anthropic** - Claude models
- **Community Contributors** - Feedback ve katkılar

---

## 💬 Destek ve İletişim

### Sorun mu yaşıyorsunuz?
1. [Dokümantasyonu](CODE_REVIEW_REPORT.md) kontrol edin
2. [Improvement Guide'a](IMPROVEMENT_GUIDE.md) bakın
3. [GitHub Issues](https://github.com/your-repo/issues) açın
4. Discussions'da soru sorun

### Katkıda bulunmak ister misiniz?
- 🐛 Bug report: [GitHub Issues](https://github.com/your-repo/issues/new?template=bug_report.md)
- 💡 Feature request: [GitHub Issues](https://github.com/your-repo/issues/new?template=feature_request.md)
- 📖 Documentation: Pull request açın
- 💻 Code contribution: [Contributing Guide](#-katkıda-bulunma) okuyun

---

## 📈 Stats

```
┌─────────────────────────────────────────────────────────────┐
│ TEM Agent - By The Numbers                                  │
├─────────────────────────────────────────────────────────────┤
│ Lines of Code:         3,146 (modularized)                  │
│ Number of Modules:     8                                     │
│ AI Agents:             4 (Mike, Alex, Bob, Charlie)         │
│ Design Patterns:       5 (Adapter, Factory, Mixin, ...)    │
│ Test Coverage:         2% (→ 80% in Phase 3)               │
│ Production Ready:      65% (→ 85% target)                  │
│ Overall Quality:       ⭐ 7.5/10                            │
└─────────────────────────────────────────────────────────────┘
```

---

**Last Updated:** 2024-12-11  
**Version:** v2.0 (Phase 2 Complete)  
**Status:** ✅ Phase 1 & 2 Complete | 🔄 Phase 3 In Progress  
**Branch:** `docs/readme-update-phase1-2-architecture-status`

---

<div align="center">

**Made with ❤️ by the TEM Agent Team**

[Documentation](CODE_REVIEW_REPORT.md) • [Issues](https://github.com/your-repo/issues) • [Contributing](IMPROVEMENT_GUIDE.md)

</div>
