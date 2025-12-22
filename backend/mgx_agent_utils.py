#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
MGX Agent Utility Functions - DRY Helpers

Bu dosya sık kullanılan utility fonksiyonları merkezileştirerek
code duplication'ı azaltır.

Kullanım:
    from mgx_agent_utils import extract_code_blocks, parse_json_block
"""

import re
import json
from typing import List, Optional, Dict
import mgx_agent_constants as constants

# MetaGPT logger - optional import
try:
    from metagpt.logs import logger
except ImportError:
    import logging
    logger = logging.getLogger(__name__)


# ============================================
# CODE BLOCK PARSING (DRY)
# ============================================

def extract_code_blocks(text: str) -> List[str]:
    """
    Metinden Python kod bloklarını çıkar.
    
    Farklı formatlardaki kod bloklarını destekler:
    - ```python code ```
    - ``` code ```
    
    Args:
        text: İçinde kod bloğu olabilecek metin
        
    Returns:
        Bulunan kod bloklarının listesi (boş olabilir)
        
    Example:
        >>> text = "```python\\nprint('hello')\\n```"
        >>> blocks = extract_code_blocks(text)
        >>> assert len(blocks) == 1
        >>> assert "print('hello')" in blocks[0]
    """
    if not text:
        return []
    
    # Code block pattern'ini kullan
    matches = re.findall(constants.CODE_BLOCK_PATTERN, text, re.DOTALL)
    
    # Her match'i strip et ve boş olanları filtrele
    result = [match.strip() for match in matches if match.strip()]
    
    logger.debug(f"Extracted {len(result)} code blocks from text")
    return result


def extract_first_code_block(text: str) -> Optional[str]:
    """
    Metinden ilk kod bloğunu çıkar.
    
    WriteCode ve WriteTest gibi single-output parsing için kullanışlıdır.
    
    Args:
        text: İçinde kod bloğu olabilecek metin
        
    Returns:
        İlk kod bloğu, yoksa None
        
    Example:
        >>> text = "Açıklama\\n```python\\nx=1\\n```\\nDiğer blok\\n```python\\ny=2\\n```"
        >>> block = extract_first_code_block(text)
        >>> assert "x=1" in block
    """
    blocks = extract_code_blocks(text)
    if blocks:
        logger.debug(f"Found first code block ({len(blocks[0])} chars)")
        return blocks[0]
    
    logger.warning("No code blocks found in text")
    return None


# ============================================
# JSON PARSING (DRY)
# ============================================

def parse_json_block(text: str, 
                     start_marker: str = None,
                     end_marker: str = None) -> Optional[Dict]:
    """
    Gömülü JSON'u metinden çıkar ve parse et.
    
    Varsayılan markers: ---JSON_START--- ve ---JSON_END---
    Custom markers de kullanılabilir.
    
    Args:
        text: İçinde JSON olabilecek metin
        start_marker: JSON başlangıç markeri (default: ---JSON_START---)
        end_marker: JSON bitiş markeri (default: ---JSON_END---)
        
    Returns:
        Parse edilen dict, başarısızsa None
        
    Example:
        >>> text = '''---JSON_START---
        ... {"key": "value", "number": 42}
        ... ---JSON_END---'''
        >>> data = parse_json_block(text)
        >>> assert data["key"] == "value"
    """
    # Default markers'ı kullan
    if start_marker is None:
        start_marker = constants.JSON_START_MARKER
    if end_marker is None:
        end_marker = constants.JSON_END_MARKER
    
    # Marker kontrolü
    if start_marker not in text or end_marker not in text:
        logger.debug(f"JSON markers not found in text (length: {len(text) if text else 0})")
        return None
    
    try:
        # JSON string'i çıkar
        json_str = text.split(start_marker)[1].split(end_marker)[0].strip()
        
        # Boş kontrol
        if not json_str:
            logger.warning("JSON block is empty (no content between markers)")
            return None
        
        # Parse et
        data = json.loads(json_str)
        logger.debug(f"Successfully parsed JSON with keys: {list(data.keys())}")
        return data
        
    except IndexError as e:
        logger.warning(f"Failed to extract JSON block: marker mismatch - {e}")
        return None
    except json.JSONDecodeError as e:
        logger.warning(f"Invalid JSON format in block: {e}")
        logger.debug(f"JSON string preview: {json_str[:100] if 'json_str' in locals() else 'N/A'}...")
        return None
    except Exception as e:
        logger.error(f"Unexpected error parsing JSON block: {e}")
        return None


# ============================================
# COMPLEXITY EXTRACTION
# ============================================

def extract_complexity(text: str) -> str:
    """
    Metinden karmaşıklık seviyesini çıkar.
    
    Desteklenen formatlar:
    - "KARMAŞIKLIK: M"
    - "karmaşıklık: L"
    - Vb. (case-insensitive)
    
    Args:
        text: İçinde karmaşıklık bilgisi olabilecek metin
        
    Returns:
        Karmaşıklık seviyesi (XS, S, M, L, XL), yoksa XS (default)
        
    Example:
        >>> text = "Görev karmaşıklığı: KARMAŞIKLIK: L"
        >>> assert extract_complexity(text) == "L"
        >>> assert extract_complexity("") == "XS"
    """
    if not text:
        logger.debug("extract_complexity: Empty text, returning default XS")
        return constants.COMPLEXITY_XS
    
    # Regex pattern'i kullan
    m = re.search(constants.COMPLEXITY_PATTERN, text.upper())
    
    if m:
        complexity = m.group(1)
        logger.debug(f"Extracted complexity: {complexity}")
        return complexity
    
    logger.debug("Complexity pattern not found, returning default XS")
    return constants.COMPLEXITY_XS


# ============================================
# OUTPUT FORMATTING
# ============================================

def print_phase_header(phase: str, emoji: str = "🔄"):
    """
    Faz başlığı yazdır (beautified section header).
    
    Args:
        phase: Faz/bölüm adı
        emoji: Başında gösterilecek emoji
        
    Example:
        >>> print_phase_header("Görev Yürütme", "🚀")
        # Prints:
        # ============================================================
        # 🚀 Görev Yürütme
        # ============================================================
    """
    print(f"\n{constants.SECTION_SEPARATOR}")
    print(f"{emoji} {phase}")
    print(f"{constants.SECTION_SEPARATOR}")


def print_step_progress(step: int, total: int, description: str, role=None):
    """
    Adım adım progress bar göster.
    
    Args:
        step: Mevcut adım numarası
        total: Toplam adım sayısı
        description: İşlem açıklaması
        role: Role instance (team referansı için) - opsiyonel
        
    Example:
        >>> print_step_progress(2, 5, "Kod yazılıyor...")
        # Prints: [████████░░░░░░░░░░] 40% - Kod yazılıyor...
    """
    # Eğer role'un team referansı varsa onu kullan
    if role and hasattr(role, '_team_ref') and hasattr(role._team_ref, '_print_progress'):
        role._team_ref._print_progress(step, total, description)
        return
    
    # Fallback: Global progress bar
    bar_length = constants.PROGRESS_BAR_LENGTH
    filled = int(bar_length * step / total)
    bar = constants.PROGRESS_BAR_FILLED * filled + constants.PROGRESS_BAR_EMPTY * (bar_length - filled)
    percent = int(100 * step / total)
    
    print(f"\r[{bar}] {percent}% - {description}", end="", flush=True)
    
    # Tamamlandığında yeni satır
    if step == total:
        print()


# ============================================
# INPUT VALIDATION & SANITIZATION
# ============================================

def validate_task_description(task: str, max_length: int = 10000) -> str:
    """
    Görev açıklamasını validate et - injection attacks'tan korunma.
    
    Kontroller:
    - Null/type check
    - Uzunluk kontrolü
    - Tehlikeli pattern detection
    
    Args:
        task: Validate edilecek görev açıklaması
        max_length: Maksimum uzunluk (default: 10000)
        
    Returns:
        Validate edilen görev
        
    Raises:
        ValueError: Geçersiz görev
        
    Example:
        >>> task = "Fibonacci fonksiyonu yaz"
        >>> validated = validate_task_description(task)
        >>> assert validated == task
        
        >>> try:
        ...     validate_task_description("exec()")
        ... except ValueError as e:
        ...     print(f"Rejected: {e}")
    """
    # Null/type check
    if not task or not isinstance(task, str):
        raise ValueError("Task must be a non-empty string")
    
    # Uzunluk check
    if len(task) > max_length:
        raise ValueError(f"Task exceeds max length of {max_length} chars (got {len(task)})")
    
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
            logger.warning(f"⚠️ Suspicious pattern in task: {reason}")
            raise ValueError(f"Dangerous pattern detected: {reason}")
    
    logger.debug(f"Task validation passed (length: {len(task)} chars)")
    return task


def sanitize_filename(filename: str, max_length: int = 255) -> str:
    """
    Dosya adını güvenli hale getir.
    
    Kontroller:
    - Sadece safe characters izin ver (alphanumeric, underscore, hyphen, dot)
    - Uzunluk sınırla
    - Path traversal attack'larını önle
    
    Args:
        filename: Sanitize edilecek dosya adı
        max_length: Maksimum uzunluk
        
    Returns:
        Sanitize edilmiş dosya adı
        
    Example:
        >>> name = "my../file!.txt"
        >>> safe = sanitize_filename(name)
        >>> assert safe == "my__file_.txt"
    """
    # Sadece safe characters izin ver
    sanitized = re.sub(r'[^a-zA-Z0-9._-]', '_', filename)
    
    # Uzunluk sınırla
    if len(sanitized) > max_length:
        sanitized = sanitized[:max_length]
    
    # Boşsa default
    if not sanitized or sanitized.startswith('.'):
        sanitized = "output"
    
    logger.debug(f"Sanitized filename: {filename[:50]}... → {sanitized}")
    return sanitized


# ============================================
# TEST FUNCTION
# ============================================

def run_tests():
    """Test utility functions"""
    print("Testing MGX Agent Utils...\n")
    
    # Test 1: extract_code_blocks
    print("Test 1: extract_code_blocks")
    text = "Kod:\n```python\nprint('hello')\n```\nSonra"
    blocks = extract_code_blocks(text)
    assert len(blocks) == 1
    assert "print" in blocks[0]
    print("✅ PASS\n")
    
    # Test 2: extract_first_code_block
    print("Test 2: extract_first_code_block")
    block = extract_first_code_block(text)
    assert block is not None
    assert "hello" in block
    print("✅ PASS\n")
    
    # Test 3: parse_json_block
    print("Test 3: parse_json_block")
    json_text = '---JSON_START---\n{"key": "value", "num": 42}\n---JSON_END---'
    data = parse_json_block(json_text)
    assert data is not None
    assert data["key"] == "value"
    assert data["num"] == 42
    print("✅ PASS\n")
    
    # Test 4: extract_complexity
    print("Test 4: extract_complexity")
    comp_text = "KARMAŞIKLIK: L\nBu görev büyük"
    complexity = extract_complexity(comp_text)
    assert complexity == "L"
    print("✅ PASS\n")
    
    # Test 5: validate_task_description
    print("Test 5: validate_task_description")
    valid_task = "Bir fonksiyon yaz"
    result = validate_task_description(valid_task)
    assert result == valid_task
    print("✅ PASS\n")
    
    # Test 6: sanitize_filename
    print("Test 6: sanitize_filename")
    unsafe = "my@#$file!.txt"
    safe = sanitize_filename(unsafe)
    assert "@" not in safe
    assert "#" not in safe
    assert "!" not in safe
    assert safe == "my___file_.txt"
    print("✅ PASS\n")
    
    print("=" * 50)
    print("✅ All tests passed!")
    print("=" * 50)


if __name__ == "__main__":
    run_tests()
