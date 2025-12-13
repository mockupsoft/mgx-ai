# -*- coding: utf-8 -*-
"""
MGX Agent File Utilities Module

Dosya işlemleri için güvenli ve stack-aware yardımcı fonksiyonlar.
"""

import os
import re
import shutil
from pathlib import Path
from typing import Dict, List, Optional, Tuple
from datetime import datetime

from metagpt.logs import logger

__all__ = [
    'parse_file_manifest',
    'validate_output_constraints',
    'safe_write_file',
    'apply_patch',
    'create_backup',
    'validate_stack_structure',
]


def parse_file_manifest(content: str) -> Dict[str, str]:
    """
    FILE manifest formatından dosyaları parse et
    
    Format:
        FILE: path/to/file.ext
        content here
        ...
        FILE: another/file.ext
        more content
    
    Args:
        content: Manifest içeriği
        
    Returns:
        {dosya_yolu: içerik} dictionary
    """
    files = {}
    current_file = None
    current_content = []
    
    lines = content.split('\n')
    
    for line in lines:
        # FILE: marker'ı tespit et
        if line.strip().startswith('FILE:'):
            # Önceki dosyayı kaydet
            if current_file:
                files[current_file] = '\n'.join(current_content).strip()
            
            # Yeni dosya başlat
            current_file = line.replace('FILE:', '').strip()
            current_content = []
        elif current_file:
            # İçeriği topla
            current_content.append(line)
    
    # Son dosyayı kaydet
    if current_file:
        files[current_file] = '\n'.join(current_content).strip()
    
    logger.debug(f"📄 Parse edildi: {len(files)} dosya bulundu")
    return files


def validate_output_constraints(
    files: Dict[str, str],
    stack_id: Optional[str] = None,
    constraints: Optional[List[str]] = None,
    strict_mode: bool = False
) -> Tuple[bool, List[str]]:
    """
    Çıktının kısıtlamalara uygunluğunu doğrula
    
    Args:
        files: {dosya_yolu: içerik} dictionary
        stack_id: Hedef stack ID
        constraints: Ek kısıtlamalar listesi
        strict_mode: Katı mod (açıklama yasak)
        
    Returns:
        (geçerli_mi, hata_mesajları)
    """
    errors = []
    
    # Stack-aware validation
    if stack_id:
        from .stack_specs import get_stack_spec
        spec = get_stack_spec(stack_id)
        
        if not spec:
            errors.append(f"❌ Geçersiz stack_id: {stack_id}")
            return False, errors
        
        # Dosya uzantı kontrolü
        expected_extensions = spec.file_extensions
        for file_path in files.keys():
            ext = Path(file_path).suffix
            if ext and expected_extensions and ext not in expected_extensions:
                logger.warning(f"⚠️ Beklenmeyen dosya uzantısı: {file_path} (beklenen: {expected_extensions})")
        
        # Proje yapısı kontrolü
        required_files = list(spec.project_layout.keys())
        for req_file in required_files:
            if req_file.endswith('/'):
                # Klasör kontrolü
                folder = req_file.rstrip('/')
                has_folder = any(f.startswith(folder + '/') for f in files.keys())
                if not has_folder:
                    logger.warning(f"⚠️ Beklenen klasör bulunamadı: {folder}/")
            else:
                # Dosya kontrolü
                if req_file not in files:
                    logger.warning(f"⚠️ Beklenen dosya bulunamadı: {req_file}")
    
    # Constraint validation
    if constraints:
        for constraint in constraints:
            constraint_lower = constraint.lower()
            
            # Package manager kontrolü
            if 'pnpm' in constraint_lower:
                # package.json'da pnpm script'leri olmalı
                pkg_json = files.get('package.json', '')
                if 'pnpm' not in pkg_json.lower():
                    errors.append(f"❌ Constraint ihlali: '{constraint}' - package.json'da pnpm kullanılmamış")
            
            # No extra libraries
            if 'no extra lib' in constraint_lower or 'minimum dep' in constraint_lower:
                # Bağımlılık sayısını kontrol et (basit heuristic)
                for file_path, content in files.items():
                    if 'package.json' in file_path or 'requirements.txt' in file_path or 'composer.json' in file_path:
                        # Satır sayısı kontrolü (çok fazla bağımlılık uyarısı)
                        dep_lines = [line for line in content.split('\n') if line.strip() and not line.strip().startswith(('#', '//'))]
                        if len(dep_lines) > 20:
                            logger.warning(f"⚠️ Çok fazla bağımlılık olabilir: {file_path} ({len(dep_lines)} satır)")
            
            # Environment variables
            if 'env' in constraint_lower and 'var' in constraint_lower:
                has_env_example = '.env.example' in files or 'env.example' in files
                if not has_env_example:
                    errors.append(f"❌ Constraint ihlali: '{constraint}' - .env.example dosyası eksik")
    
    # Strict mode: No prose outside FILE blocks
    if strict_mode:
        # Bu kontrol parse_file_manifest başarıyla çalıştıysa zaten geçmiş demektir
        if not files:
            errors.append("❌ Strict mode: Hiçbir FILE bloğu bulunamadı")
    
    # Dosya içerik kontrolü
    for file_path, content in files.items():
        if not content.strip():
            errors.append(f"❌ Boş dosya: {file_path}")
    
    is_valid = len(errors) == 0
    return is_valid, errors


def create_backup(file_path: str) -> str:
    """
    Dosyanın yedek kopyasını oluştur
    
    Args:
        file_path: Yedeklenecek dosya yolu
        
    Returns:
        Yedek dosya yolu
    """
    if not os.path.exists(file_path):
        return ""
    
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    backup_path = f"{file_path}.{timestamp}.bak"
    
    shutil.copy2(file_path, backup_path)
    logger.info(f"💾 Yedek oluşturuldu: {backup_path}")
    return backup_path


def safe_write_file(file_path: str, content: str, create_backup_flag: bool = True) -> bool:
    """
    Dosyayı güvenli şekilde yaz (yedek oluştur)
    
    Args:
        file_path: Hedef dosya yolu
        content: Yazılacak içerik
        create_backup_flag: Yedek oluşturulsun mu
        
    Returns:
        Başarılı mı
    """
    try:
        # Tam yol
        full_path = Path(file_path)
        
        # Yedek oluştur (dosya mevcutsa)
        if create_backup_flag and full_path.exists():
            create_backup(str(full_path))
        
        # Klasörü oluştur
        full_path.parent.mkdir(parents=True, exist_ok=True)
        
        # Dosyayı yaz
        full_path.write_text(content, encoding='utf-8')
        logger.info(f"✅ Dosya yazıldı: {file_path}")
        return True
    
    except Exception as e:
        logger.error(f"❌ Dosya yazma hatası ({file_path}): {e}")
        return False


def apply_patch(file_path: str, patch_content: str) -> Tuple[bool, str]:
    """
    Unified diff patch uygula
    
    Args:
        file_path: Hedef dosya yolu
        patch_content: Unified diff formatında patch
        
    Returns:
        (başarılı_mı, hata_mesajı)
    """
    try:
        import patch_ng as patch
        
        # Yedek oluştur
        backup_path = create_backup(file_path)
        
        # Patch uygula
        patchset = patch.fromstring(patch_content.encode('utf-8'))
        if patchset.apply():
            logger.info(f"✅ Patch uygulandı: {file_path}")
            return True, ""
        else:
            logger.error(f"❌ Patch uygulanamadı: {file_path}")
            return False, "Patch uygulama başarısız"
    
    except ImportError:
        # patch_ng yoksa manuel olarak yap
        logger.warning("⚠️ patch_ng bulunamadı, manuel patch desteği henüz yok")
        
        # Fallback: .mgx_new dosyası oluştur
        new_file_path = f"{file_path}.mgx_new"
        safe_write_file(new_file_path, patch_content, create_backup_flag=False)
        
        return False, f"patch_ng bulunamadı. Yeni içerik {new_file_path} dosyasına yazıldı. Manuel merge gerekli."
    
    except Exception as e:
        logger.error(f"❌ Patch hatası: {e}")
        return False, str(e)


def validate_stack_structure(
    project_path: str,
    stack_id: str
) -> Tuple[bool, List[str]]:
    """
    Projenin stack yapısına uygunluğunu doğrula
    
    Args:
        project_path: Proje kök klasörü
        stack_id: Stack ID
        
    Returns:
        (geçerli_mi, uyarı_mesajları)
    """
    from .stack_specs import get_stack_spec
    
    spec = get_stack_spec(stack_id)
    if not spec:
        return False, [f"Geçersiz stack_id: {stack_id}"]
    
    warnings = []
    project = Path(project_path)
    
    if not project.exists():
        return False, [f"Proje klasörü bulunamadı: {project_path}"]
    
    # Temel dosya/klasör kontrolü
    for key, description in spec.project_layout.items():
        path = project / key
        
        if key.endswith('/'):
            # Klasör kontrolü
            if not path.exists() or not path.is_dir():
                warnings.append(f"⚠️ Eksik klasör: {key} - {description}")
        else:
            # Dosya kontrolü (tam eşleşme veya wildcard)
            if '*' in key:
                # Wildcard desteği
                pattern = key.replace('*', '.*')
                matches = list(project.glob(pattern))
                if not matches:
                    warnings.append(f"⚠️ Eksik dosya: {key} - {description}")
            else:
                if not path.exists():
                    warnings.append(f"⚠️ Eksik dosya: {key} - {description}")
    
    is_valid = len(warnings) == 0
    return is_valid, warnings
