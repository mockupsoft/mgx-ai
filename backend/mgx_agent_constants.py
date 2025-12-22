#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
MGX Agent Constants - Magic Numbers and Configuration Values

Bu dosya proje içinde saçılmış tüm sabitleri merkezileştirer.
Kullanım: from mgx_agent_constants import DEFAULT_MAX_ROUNDS, PROGRESS_BAR_LENGTH
"""

# ============================================
# Task Complexity Levels
# ============================================
COMPLEXITY_XS = "XS"   # Çok basit - tek dosya, tek fonksiyon
COMPLEXITY_S = "S"     # Basit - birkaç fonksiyon
COMPLEXITY_M = "M"     # Orta - birden fazla dosya
COMPLEXITY_L = "L"     # Büyük - mimari gerektirir
COMPLEXITY_XL = "XL"   # Çok büyük - tam takım gerektirir

COMPLEXITY_LEVELS = [COMPLEXITY_XS, COMPLEXITY_S, COMPLEXITY_M, COMPLEXITY_L, COMPLEXITY_XL]

# ============================================
# Default Configuration Values
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
MAX_CACHE_TTL_SECONDS = 86400     # Maximum 1 day (24 hours)

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
RELEVANT_MEMORY_LIMIT = 5          # Keep top N relevant memories per role
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
# Pattern Matching (Regular Expressions)
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
# Model Pricing (Example - Update with real prices)
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

# ============================================
# Error Messages (Standardized)
# ============================================
ERROR_NO_CODE_FOUND = "No code found"
ERROR_NO_TESTS_FOUND = "No tests found"
ERROR_NO_REVIEW_FOUND = "No review found"
ERROR_PLAN_NOT_APPROVED = "Plan henüz onaylanmadı! Önce plan onaylamalısınız."
ERROR_PLAN_MISSING = "❌ Plan bulunamadı, varsayılan context kullanılıyor..."

# ============================================
# Success Messages
# ============================================
MSG_PLAN_APPROVED = "✅ Plan onaylandı! Görev dağıtımı başlıyor..."
MSG_EXECUTION_COMPLETE = "✅ Görev tamamlandı"
MSG_REVIEW_APPROVED = "✅ Review ONAYLANDI - Düzeltme gerekmiyor."

# ============================================
# Helper: Get Complexity Display Name
# ============================================
COMPLEXITY_LABELS = {
    COMPLEXITY_XS: "Çok Basit (XS)",
    COMPLEXITY_S: "Basit (S)",
    COMPLEXITY_M: "Orta (M)",
    COMPLEXITY_L: "Büyük (L)",
    COMPLEXITY_XL: "Çok Büyük (XL)",
}

def get_complexity_label(complexity: str) -> str:
    """Get human-readable complexity label"""
    return COMPLEXITY_LABELS.get(complexity, "Bilinmiyor")


if __name__ == "__main__":
    # Test script
    print("MGX Agent Constants - Test\n")
    print(f"Complexity Levels: {COMPLEXITY_LEVELS}")
    print(f"Default Max Rounds: {DEFAULT_MAX_ROUNDS}")
    print(f"Cache TTL: {DEFAULT_CACHE_TTL_SECONDS} seconds")
    print(f"Progress Bar Length: {PROGRESS_BAR_LENGTH}")
    print(f"Test: {get_complexity_label(COMPLEXITY_M)}")
    print("\n✅ Constants module is working correctly!")
