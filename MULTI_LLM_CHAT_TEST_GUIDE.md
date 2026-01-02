# Multi-LLM ve Canlı Sohbet Test Rehberi

## 🚀 Hızlı Test

### 1. Multi-LLM Yönetimi Sayfası
**URL**: http://localhost:3000/mgx/settings/llm

**Test Adımları**:
1. Tarayıcıda sayfayı açın
2. Provider Health bölümünde tüm provider'ların durumunu görün:
   - ✅ Anthropic (4 model)
   - ✅ Mistral (4 model)
   - ✅ Ollama (6 model - local)
   - ✅ OpenAI (5 model)
   - ✅ Together AI (3 model)
3. Routing Strategy seçin (balanced, cost_optimized, latency_optimized, quality_optimized, local_first)
4. "Test Route" butonuna tıklayın
5. Seçilen provider ve model'i görün

### 2. Canlı Sohbet Akışı
**URL**: http://localhost:3000/mgx/tasks

**Test Adımları**:
1. Tasks sayfasına gidin
2. Bir task seçin veya yeni task oluşturun
3. Task monitoring view'de canlı sohbet paneli görünür
4. WebSocket bağlantısı otomatik kurulur
5. Agent mesajları gerçek zamanlı olarak görünür

## 🔧 Multi-LLM Nasıl Çalışıyor?

### Backend'de Multi-LLM
1. **Team Config**: `use_multi_llm=True` olduğunda her role farklı LLM kullanır
2. **LLM Router**: Stratejiye göre provider seçer (balanced, cost, latency, quality, local_first)
3. **Fallback Chain**: Bir provider başarısız olursa otomatik olarak diğerine geçer

### Canlı Sohbet Akışı
1. **WebSocket Bağlantısı**: `ws://localhost:8000/ws/tasks/{task_id}`
2. **Mesaj Akışı**: 
   - Agent mesajları WebSocket üzerinden gelir
   - Typing indicator gösterilir
   - Mesajlar otomatik scroll edilir
3. **Mesaj Tipleri**:
   - `user` - Kullanıcı mesajları
   - `agent` - Agent mesajları
   - `tool` - Tool execution mesajları
   - `system` - Sistem mesajları
   - `error` - Hata mesajları

## 📊 API Endpoints

### LLM Management
```bash
# Provider health
GET http://localhost:8000/api/llm/health

# Route test
POST http://localhost:8000/api/llm/route
Body: {
  "strategy": "balanced",
  "prefer_local": false
}

# Model listesi
GET http://localhost:8000/api/llm/models?provider=openai
```

### Agent Messages
```bash
# Mesaj listesi
GET http://localhost:8000/api/agents/{agent_id}/messages

# Mesaj gönderme
POST http://localhost:8000/api/agents/{agent_id}/messages
Body: {
  "content": "Merhaba",
  "direction": "outbound"
}
```

### WebSocket
```javascript
// Task events
ws://localhost:8000/ws/tasks/{task_id}

// Agent events
ws://localhost:8000/ws/agents/{agent_id}

// Global stream
ws://localhost:8000/ws/stream
```

## 🎯 Test Senaryoları

### Senaryo 1: Multi-LLM Routing Test
1. LLM Management sayfasına gidin
2. Strategy'yi "cost_optimized" seçin
3. "Test Route" butonuna tıklayın
4. En ucuz provider/model seçildiğini görün

### Senaryo 2: Canlı Sohbet Test
1. Bir task oluşturun
2. Task'ı çalıştırın
3. Canlı sohbet panelinde agent mesajlarını görün
4. WebSocket bağlantısının çalıştığını doğrulayın

### Senaryo 3: Multi-LLM + Canlı Sohbet
1. Team config'de `use_multi_llm=True` ayarlayın
2. Bir task oluşturun
3. Her role farklı LLM kullanıldığını loglardan kontrol edin
4. Canlı sohbet panelinde mesajları görün

## 🔍 Debugging

### WebSocket Bağlantısı Kontrolü
```javascript
// Browser console'da
const ws = new WebSocket('ws://localhost:8000/ws/stream');
ws.onopen = () => console.log('Connected');
ws.onmessage = (e) => console.log('Message:', JSON.parse(e.data));
```

### Provider Health Kontrolü
```bash
curl http://localhost:8000/api/llm/health
```

### Route Test
```bash
curl -X POST http://localhost:8000/api/llm/route \
  -H "Content-Type: application/json" \
  -d '{"strategy":"balanced"}'
```

## 📝 Notlar

- Multi-LLM modu aktif olduğunda her role farklı LLM kullanır
- Canlı sohbet WebSocket ile çalışır, gerçek zamanlı mesaj akışı sağlar
- Routing stratejisi task'a göre otomatik seçilir
- Fallback chain sayesinde provider hatalarında otomatik geçiş yapılır

