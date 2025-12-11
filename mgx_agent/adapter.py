# -*- coding: utf-8 -*-
"""
MGX Agent Adapter Module

MetaGPT adapter for memory management.
"""

from metagpt.logs import logger


class MetaGPTAdapter:
    """
    MetaGPT'nin iç yapısına erişimi soyutlayan adapter sınıfı.
    
    Bu sınıf, MetaGPT'nin private değişkenlerine doğrudan erişimi engeller
    ve API değişikliklerine karşı koruma sağlar.
    
    MetaGPT güncellendiğinde sadece bu sınıfı güncellemek yeterli olacaktır.
    """
    
    @staticmethod
    def get_memory_store(role) -> object:
        """
        Role'dan memory store'u güvenli şekilde al.
        
        Args:
            role: MetaGPT Role instance
            
        Returns:
            Memory store object veya None
        """
        if not hasattr(role, "rc"):
            return None
        if not hasattr(role.rc, "memory"):
            return None
        return role.rc.memory
    
    @staticmethod
    def get_messages(mem_store) -> list:
        """
        Memory store'dan mesajları güvenli şekilde al.
        
        Args:
            mem_store: Memory store object
            
        Returns:
            Mesaj listesi (boş liste değil, her zaman list)
        """
        if mem_store is None:
            return []
        
        # MetaGPT API'sine göre güvenli erişim
        if hasattr(mem_store, "get"):
            # Standart API: memory.get() -> list[Message]
            try:
                return list(mem_store.get())
            except Exception:
                return []
        elif hasattr(mem_store, "__iter__"):
            # Fallback: iterable olarak kullan
            try:
                return list(mem_store)
            except Exception:
                return []
        else:
            # Son çare: storage attribute'una eriş (eğer varsa)
            if hasattr(mem_store, "storage"):
                return list(mem_store.storage) if mem_store.storage else []
            return []
    
    @staticmethod
    def add_message(mem_store, message) -> bool:
        """
        Memory store'a mesaj ekle.
        
        Args:
            mem_store: Memory store object
            message: Message instance
            
        Returns:
            True if successful, False otherwise
        """
        if mem_store is None:
            return False
        
        try:
            if hasattr(mem_store, "add"):
                mem_store.add(message)
                return True
            else:
                # Fallback: storage'a doğrudan ekle (eğer varsa)
                if hasattr(mem_store, "storage"):
                    if message not in mem_store.storage:
                        mem_store.storage.append(message)
                    return True
                return False
        except Exception as e:
            logger.warning(f"⚠️ Mesaj eklenirken hata: {e}")
            return False
    
    @staticmethod
    def clear_memory(mem_store, keep_last_n: int) -> bool:
        """
        Memory store'u temizle, son N mesajı tut.
        
        Args:
            mem_store: Memory store object
            keep_last_n: Tutulacak mesaj sayısı
            
        Returns:
            True if successful, False otherwise
        """
        if mem_store is None:
            return False
        
        try:
            # Mevcut mesajları al
            messages = MetaGPTAdapter.get_messages(mem_store)
            
            if len(messages) <= keep_last_n:
                # Zaten limit içinde, temizlik gerekmiyor
                return True
            
            # Son N mesajı tut
            messages_to_keep = messages[-keep_last_n:]
            
            # Temizleme stratejileri (öncelik sırasına göre)
            
            # Strateji 1: clear() + add() API'si varsa
            if hasattr(mem_store, "clear") and hasattr(mem_store, "add"):
                mem_store.clear()
                for msg in messages_to_keep:
                    mem_store.add(msg)
                return True
            
            # Strateji 2: storage attribute'una erişim varsa
            if hasattr(mem_store, "storage"):
                mem_store.storage = messages_to_keep
                # Index'i de güncelle (eğer varsa)
                if hasattr(mem_store, "index"):
                    # Index'i sıfırla ve yeniden oluştur
                    mem_store.index.clear()
                    for msg in messages_to_keep:
                        if hasattr(msg, "cause_by") and msg.cause_by:
                            cause_by_key = str(msg.cause_by) if not isinstance(msg.cause_by, str) else msg.cause_by
                            if cause_by_key not in mem_store.index:
                                mem_store.index[cause_by_key] = []
                            mem_store.index[cause_by_key].append(msg)
                return True
            
            # Strateji 3: _memory private attribute (son çare - riskli ama gerekli)
            if hasattr(mem_store, "_memory"):
                mem_store._memory = messages_to_keep
                logger.warning(
                    "⚠️ UYARI: MetaGPT private attribute (_memory) kullanılıyor!\n"
                    "   This is a fallback strategy and may break with MetaGPT updates.\n"
                    "   Please submit public API request to MetaGPT project.\n"
                    "   GitHub: https://github.com/geekan/MetaGPT/issues"
                )
                return True
            
            # Hiçbir strateji çalışmadı
            logger.warning("⚠️ Memory temizliği yapılamadı - uygun API bulunamadı")
            return False
            
        except Exception as e:
            logger.error(f"❌ Memory temizliği hatası: {e}")
            return False
    
    @staticmethod
    def get_messages_by_role(mem_store, role_name: str) -> list:
        """
        Belirli role'den gelen mesajları getir.
        
        Args:
            mem_store: Memory store object
            role_name: Role adı (örn: "Engineer", "Tester")
            
        Returns:
            Mesaj listesi
        """
        if mem_store is None:
            return []
        
        try:
            # Strateji 1: get_by_role() API'si varsa
            if hasattr(mem_store, "get_by_role"):
                return list(mem_store.get_by_role(role_name))
            
            # Strateji 2: Manuel filtreleme
            all_messages = MetaGPTAdapter.get_messages(mem_store)
            return [msg for msg in all_messages if hasattr(msg, "role") and msg.role == role_name]
            
        except Exception as e:
            logger.warning(f"⚠️ Role mesajları alınırken hata: {e}")
            return []
    
    @staticmethod
    def get_news(role) -> list:
        """
        Role'un yeni mesajlarını (rc.news) güvenli şekilde al.
        
        Args:
            role: MetaGPT Role instance
            
        Returns:
            Yeni mesaj listesi (boş liste değil, her zaman list)
        """
        if not hasattr(role, "rc"):
            return []
        if not hasattr(role.rc, "news"):
            return []
        
        try:
            news = role.rc.news
            if news is None:
                return []
            # news bir liste olabilir veya başka bir iterable
            return list(news) if hasattr(news, "__iter__") else []
        except Exception as e:
            logger.warning(f"⚠️ News alınırken hata: {e}")
            return []
