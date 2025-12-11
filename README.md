# MGX Style Multi-Agent Team (TEM Agent)

MetaGPT açık kaynak kodunun üzerine geliştirilen, **dört rol içeren bir multi-agent kod geliştirme sistemi**.

Sistem, yazılım geliştirme sürecini otomatikleştirerek:
- Görev analiz eder ve plan oluşturur (Mike)
- Kod yazar (Alex)
- Test yazır (Bob)  
- Kodu inceler (Charlie)

---

## 🚀 Özellikler

- **4 Uzman Rol**: Mike (TeamLeader), Alex (Engineer), Bob (Tester), Charlie (Reviewer)
- **Otomatik Karmaşıklık Değerlendirmesi**: XS/S/M/L/XL seviyeleri
- **Akıllı Revision Döngüleri**: AI tarafından yönlendirilen kod iyileştirmeleri
- **Metrik Takibi**: Süre, token, maliyet hesaplamaları
- **Esnek Konfigürasyon**: Pydantic V2 tabanlı doğrulama
- **İnsan Müdahalesi**: Opsiyonel human reviewer modu
- **Artımlı Geliştirme**: Mevcut projelere özellik ekleme veya bug düzeltme

---

## 📦 Kurulum

### Gereksinimler
- Python 3.8+
- MetaGPT
- Pydantic v2
- Tenacity

### Adımlar

```bash
# Repository'yi klonla
git clone <repo>
cd project

# Bağımlılıkları yükle
pip install -r requirements.txt

# MetaGPT'yi konfigüre et (ilk kez)
python -m metagpt.config
```

---

## 🎯 Hızlı Başlangıç

### Normal Mod
```bash
python examples/mgx_style_team.py
```

### İnsan Reviewer Modu
```bash
python examples/mgx_style_team.py --human
```

### Özel Görev
```bash
python examples/mgx_style_team.py --task "Fibonacci hesaplayan fonksiyon yaz"
```

### Mevcut Projeye Özellik Ekleme
```bash
python examples/mgx_style_team.py --add-feature "Add login system" --project-path ./my_project
```

### Mevcut Projedeki Bug'ı Düzeltme
```bash
python examples/mgx_style_team.py --fix-bug "TypeError: x is undefined" --project-path ./my_project
```

---

## 📖 Dokümantasyon

| Doküman | Açıklama |
|---------|----------|
| [CODE_REVIEW_INDEX.md](CODE_REVIEW_INDEX.md) | Kod inceleme raporları indeksi |
| [REVIEW_SUMMARY.md](REVIEW_SUMMARY.md) | Yönetim özeti ve aksiyon planı |
| [CODE_REVIEW_REPORT.md](CODE_REVIEW_REPORT.md) | Detaylı kod inceleme analizi |
| [IMPROVEMENT_GUIDE.md](IMPROVEMENT_GUIDE.md) | Refactoring ve iyileştirme rehberi |
| [QUICK_FIXES.md](QUICK_FIXES.md) | Hızlı düzeltme örnekleri |

---

## ⚙️ Konfigürasyon

### Python API ile
```python
from examples.mgx_style_team import MGXStyleTeam, TeamConfig

config = TeamConfig(
    max_rounds=5,                 # Maksimum execution turları
    max_revision_rounds=2,        # Maksimum revision turları
    enable_caching=True,          # Task analiz cache'i
    human_reviewer=False,         # Human reviewer modu
    default_investment=3.0,       # Budget ($)
    budget_multiplier=1.0,        # Budget çarpanı
)

team = MGXStyleTeam(config=config)
```

### YAML ile
```yaml
max_rounds: 5
max_revision_rounds: 2
enable_caching: true
default_investment: 3.0
budget_multiplier: 1.0
```

```python
config = TeamConfig.from_yaml("config.yaml")
team = MGXStyleTeam(config=config)
```

---

## 🏗️ Mimari

```
CLI Input (Task)
    ↓
┌─────────────────────┐
│ Mike (TeamLeader)   │  Analiz & Plan
│ - AnalyzeTask      │  - Karmaşıklık değerlendir
│ - DraftPlan        │  - Plan oluştur
└──────────┬──────────┘
           ↓
┌─────────────────────┐
│ Alex (Engineer)     │  Kod Yazma
│ - WriteCode        │  - Review notları varsa revize
└──────────┬──────────┘
           ↓
┌─────────────────────┐
│ Bob (Tester)        │  Test Yazma
│ - WriteTest        │  - Kod testlerini yaz
└──────────┬──────────┘
           ↓
┌─────────────────────┐
│ Charlie (Reviewer)  │  Kod İnceleme
│ - ReviewCode       │  - Kalite kontrol
└──────────┬──────────┘
           ↓
    ONAYLANDI MI?
    ├─ Evet → Bitti ✅
    └─ Hayır → Alex'e geri (Revision Loop)
           ↓
    Output (main.py, test_main.py, review.md)
```

---

## 📊 Örnek Çıktı

```
═══════════════════════════════════════════════════════
✅ MIKE: Analiz ve plan tamamlandı!
📊 Karmaşıklık: M
───────────────────────────────────────────────────────

═══════════════════════════════════════════════════════
💻 ALEX (Engineer) - KOD YAZIYOR...
───────────────────────────────────────────────────────
✅ ALEX: Kod tamamlandı! (1234 karakter)

═══════════════════════════════════════════════════════
🧪 BOB (Tester) - TEST YAZIYOR...
───────────────────────────────────────────────────────
✅ BOB: Testler tamamlandı! (456 karakter)

═══════════════════════════════════════════════════════
🔍 CHARLIE (Reviewer) - KOD İNCELİYOR...
───────────────────────────────────────────────────────
✅ CHARLIE: Review tamamlandı! (789 karakter)

═══════════════════════════════════════════════════════
📊 GÖREV METRİKLERİ
═══════════════════════════════════════════════════════
📌 Görev: Listedeki sayıların çarpımını...
✅ Durum: Başarılı
⏱️  Süre: 2.5m
🎯 Karmaşıklık: M
🔄 Düzeltme Turları: 0
🪙 Tahmini Token: ~1500
💰 Tahmini Maliyet: $3.0000
═══════════════════════════════════════════════════════
```

---

## 📁 Dosya Yapısı

```
/home/engine/project/
├── README.md                      ← Bu dosya
├── examples/
│   └── mgx_style_team.py         ← Ana uygulama (2392 satır)
├── CODE_REVIEW_*.md              ← Kod inceleme raporları
├── mgx_agent_constants.py        ← Proje sabitleri
├── mgx_agent_utils.py            ← Utility fonksiyonları
├── .gitignore                     ← Git ignore kuralları
├── output/                        ← Üretilen dosyaların çıktı
└── (Gelecek: modularization)
    └── mgx_agent/               ← Package yapısı
        ├── __init__.py
        ├── config.py
        ├── metrics.py
        ├── actions.py
        ├── roles.py
        ├── adapter.py
        ├── team.py
        └── cli.py
```

---

## 🧪 Test Etme

### Temel Test
```bash
# Basit bir görev
python examples/mgx_style_team.py --task "Fibonacci fonksiyonu yaz"
```

### Human Reviewer Test
```bash
python examples/mgx_style_team.py --human
```

### Increment Test (Feature Ekleme)
```bash
python examples/mgx_style_team.py --add-feature "Add documentation" --project-path ./test_project
```

### Sonuçları Kontrol Et
```bash
ls -la output/mgx_team_*/
cat output/mgx_team_*/main.py
cat output/mgx_team_*/test_main.py
cat output/mgx_team_*/review.md
```

---

## 🔧 Geliştirme

### Yeni Version'a Katkı
1. Branch oluştur: `git checkout -b feature/your-feature`
2. Değişiklikleri yap ve test et
3. Pull request açıkla

### Kod Kalitesi
- Kod yazarken docstring ekle
- Type hints kullan
- Error handling'i test et

---

## ⚠️ Bilinen Sınırlamalar

| Sorun | Status | Workaround |
|-------|--------|-----------|
| Test coverage = 0% | ⚠️ WIP | [IMPROVEMENT_GUIDE.md](IMPROVEMENT_GUIDE.md) göz at |
| Monolitik yapı | ⚠️ WIP | Modularization'ı yakında yapacağız |
| Human-in-loop incomplete | 🔄 Testing | Terminal input'u kullanıyor |
| Multi-LLM mode | ⚠️ Experimental | Config dosyaları ile test et |
| Token counting | 📊 Estimated | Gerçek değer MetaGPT API'sinden alınır |

---

## 📝 Lisans

MIT License - Detaylar için LICENSE dosyasına bak

---

## 🤝 Destek

Sorularınız veya sorunlarınız varsa:
1. [CODE_REVIEW_REPORT.md](CODE_REVIEW_REPORT.md) - Teknik detaylar
2. [IMPROVEMENT_GUIDE.md](IMPROVEMENT_GUIDE.md) - Çözüm önerileri
3. GitHub Issues - Sorun bildir

---

## 🎯 Roadmap

- [ ] Test altyapısı (Phase 1)
- [ ] Package modularization (Phase 2)
- [ ] Performance optimization (Phase 3)
- [ ] WebUI dashboard (Phase 4)
- [ ] Docker support (Phase 5)

---

**Last Updated:** 2024  
**Status:** ✅ Functional / ⚠️ WIP improvements  
**Version:** v1-core
