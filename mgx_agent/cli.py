# -*- coding: utf-8 -*-
"""
MGX Agent CLI Module

Command-line interface for MGX Style Multi-Agent Team.
"""

import asyncio
import argparse
import json
from pathlib import Path

from .team import MGXStyleTeam


def _print_available_stacks(as_json: bool = False) -> None:
    """Print supported stacks and exit.

    Kept lightweight (no MetaGPT/LLM initialization) so it can be used in CI.
    """

    from .stack_specs import STACK_SPECS

    stacks = {
        stack_id: {
            "name": spec.name,
            "category": getattr(spec.category, "value", str(spec.category)),
            "language": spec.language,
            "test_framework": spec.test_framework,
            "package_manager": spec.package_manager,
        }
        for stack_id, spec in STACK_SPECS.items()
    }

    if as_json:
        print(json.dumps(stacks, ensure_ascii=False, indent=2))
        return

    print("\nDesteklenen Stack'ler:\n")
    for stack_id in sorted(stacks.keys()):
        meta = stacks[stack_id]
        print(
            f"- {stack_id}: {meta['name']} "
            f"({meta['category']}, {meta['language']}, test={meta['test_framework']})"
        )


async def main(human_reviewer: bool = False, custom_task: str = None, enable_profiling: bool = False, enable_tracemalloc: bool = False):
    """
    MGX tarzı takım örneği
    
    Args:
        human_reviewer: True ise Charlie (Reviewer) insan olarak çalışır
        custom_task: Özel görev tanımı (None ise varsayılan görev)
        enable_profiling: Performance profiling aktif mi
        enable_tracemalloc: Tracemalloc ile detaylı hafıza profiling
    """
    
    mode_text = "🧑 İNSAN MODU" if human_reviewer else "🤖 LLM MODU"
    
    print(f"""
    ╔══════════════════════════════════════════════════════════╗
    ║           MGX STYLE MULTI-AGENT TEAM                     ║
    ║                                                          ║
    ║  👤 Mike (Team Leader) - Görev analizi ve planlama       ║
    ║  👤 Alex (Engineer) - Kod yazma                          ║
    ║  👤 Bob (Tester) - Test yazma                            ║
    ║  👤 Charlie (Reviewer) - Kod inceleme [{mode_text}]      ║
    ╚══════════════════════════════════════════════════════════╝
    """)
    
    # Takımı oluştur (profiling dahil)
    from .config import TeamConfig
    config = TeamConfig(
        human_reviewer=human_reviewer,
        enable_profiling=enable_profiling,
        enable_profiling_tracemalloc=enable_tracemalloc,
    )
    mgx_team = MGXStyleTeam(config=config)
    
    # Start profiler if enabled
    if enable_profiling:
        mgx_team._start_profiler("cli_main_run")
    
    # Görev tanımla (varsayılan veya özel)
    task = custom_task or "Listedeki sayıların çarpımını hesaplayan bir Python fonksiyonu yaz"
    
    # 1. Analiz ve Plan (stream ile canlı gösterilir)
    print("\n📋 ADIM 1: Görev Analizi ve Plan Oluşturma")
    print("-" * 50)
    await mgx_team.analyze_and_plan(task)
    # Stream ile canlı gösterildi, tekrar print etmeye gerek yok
    
    # 2. Plan Onayı (gerçek uygulamada kullanıcıdan alınır)
    print("\n✅ ADIM 2: Plan Onayı")
    print("-" * 50)
    mgx_team.approve_plan()
    
    # 3. Görev Yürütme (her agent canlı çıktı verir)
    print("\n🚀 ADIM 3: Görev Yürütme")
    print("-" * 50)
    await mgx_team.execute()  # Karmaşıklığa göre otomatik ayarlanır
    # Agent'ların çıktıları stream ile canlı gösterildi
    
    # 4. Hafıza Günlüğü
    print("\n📋 ADIM 4: Hafıza Günlüğü")
    print("-" * 50)
    print(mgx_team.show_memory_log())
    
    # 5. İlerleme Durumu
    print("\n📊 ADIM 5: İlerleme Durumu")
    print("-" * 50)
    print(mgx_team.get_progress())
    
    print("\n" + "=" * 50)
    print("🎊 MGX Style Takım çalışması tamamlandı!")
    print("=" * 50)
    
    # End profiler if enabled
    if enable_profiling:
        mgx_team._end_profiler()


async def incremental_main(requirement: str, project_path: str = None, fix_bug: bool = False, ask_confirmation: bool = True):
    """
    Artımlı geliştirme modu
    
    Args:
        requirement: Yeni gereksinim veya bug açıklaması
        project_path: Mevcut proje yolu
        fix_bug: True ise bug düzeltme modu
        ask_confirmation: True ise plan onayı bekle (sessiz mod için False)
    """
    mode = "🐛 BUG DÜZELTME" if fix_bug else "➕ YENİ ÖZELLİK"
    
    print(f"""
    ╔══════════════════════════════════════════════════════════╗
    ║        MGX STYLE - INCREMENTAL DEVELOPMENT               ║
    ║                                                          ║
    ║  {mode:^52} ║
    ╚══════════════════════════════════════════════════════════╝
    """)
    
    mgx_team = MGXStyleTeam(human_reviewer=False)
    
    if project_path:
        print(f"\n📁 Proje: {project_path}")
        print(mgx_team.get_project_summary(project_path))
    
    result = await mgx_team.run_incremental(requirement, project_path, fix_bug, ask_confirmation)
    print(result)


async def json_input_main(json_path: str):
    """
    JSON dosyasından görev yükle ve çalıştır (Phase B)
    
    Args:
        json_path: JSON dosya yolu
    """
    print(f"""
    ╔══════════════════════════════════════════════════════════╗
    ║        MGX STYLE - JSON INPUT MODE                       ║
    ║                                                          ║
    ║  📄 Yapılandırılmış görev girişi                         ║
    ╚══════════════════════════════════════════════════════════╝
    """)
    
    # JSON dosyasını oku
    try:
        with open(json_path, 'r', encoding='utf-8') as f:
            task_input = json.load(f)
    except FileNotFoundError:
        print(f"❌ Hata: JSON dosyası bulunamadı: {json_path}")
        return
    except json.JSONDecodeError as e:
        print(f"❌ Hata: Geçersiz JSON formatı: {e}")
        return
    
    # JSON yapısını doğrula ve parse et
    from .config import TeamConfig
    
    task = task_input.get("task")
    if not task:
        print("❌ Hata: 'task' alanı zorunludur")
        return
    
    # TeamConfig oluştur
    config = TeamConfig(
        target_stack=task_input.get("target_stack"),
        project_type=task_input.get("project_type"),
        output_mode=task_input.get("output_mode", "generate_new"),
        strict_requirements=task_input.get("strict_requirements", False),
        existing_project_path=task_input.get("existing_project_path"),
        constraints=task_input.get("constraints", []),
    )
    
    print(f"\n📋 Görev: {task}")
    print(f"🎯 Stack: {config.target_stack or 'otomatik'}")
    print(f"📁 Proje Tipi: {config.project_type or 'otomatik'}")
    print(f"📝 Mod: {config.output_mode}")
    if config.constraints:
        print(f"⚠️ Kısıtlamalar: {', '.join(config.constraints)}")
    
    # Takımı oluştur ve çalıştır
    mgx_team = MGXStyleTeam(config=config)
    
    # 1. Analiz ve Plan
    print("\n📋 ADIM 1: Görev Analizi ve Plan Oluşturma")
    print("-" * 50)
    await mgx_team.analyze_and_plan(task)
    
    # 2. Plan Onayı
    print("\n✅ ADIM 2: Plan Onayı")
    print("-" * 50)
    mgx_team.approve_plan()
    
    # 3. Görev Yürütme
    print("\n🚀 ADIM 3: Görev Yürütme")
    print("-" * 50)
    await mgx_team.execute()
    
    # 4. Sonuç
    print("\n📊 ADIM 4: Sonuç")
    print("-" * 50)
    print(mgx_team.get_progress())
    
    print("\n" + "=" * 50)
    print("🎊 JSON görev tamamlandı!")
    print("=" * 50)


def cli_main():
    """CLI entry point"""
    parser = argparse.ArgumentParser(
        description="MGX Style Multi-Agent Team",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Örnekler:
  # Normal mod (yeni görev)
  python -m mgx_agent.cli
  
  # İnsan reviewer modu
  python -m mgx_agent.cli --human
  
  # Yeni özellik ekle (mevcut projeye)
  python -m mgx_agent.cli --add-feature "Add login system" --project-path "./my_project"
  
  # Bug düzelt
  python -m mgx_agent.cli --fix-bug "TypeError: x is not defined" --project-path "./my_project"
  
  # Özel görev
  python -m mgx_agent.cli --task "Fibonacci hesaplayan fonksiyon yaz"
        """
    )
    
    parser.add_argument(
        "--human", 
        action="store_true", 
        help="Charlie (Reviewer) için insan modu aktif et"
    )
    
    parser.add_argument(
        "--task",
        type=str,
        default=None,
        help="Özel görev tanımı"
    )
    
    parser.add_argument(
        "--project-path",
        type=str,
        default=None,
        help="Mevcut proje yolu (incremental development için)"
    )
    
    parser.add_argument(
        "--add-feature",
        type=str,
        default=None,
        help="Mevcut projeye yeni özellik ekle"
    )
    
    parser.add_argument(
        "--fix-bug",
        type=str,
        default=None,
        help="Mevcut projedeki bug'ı düzelt"
    )
    
    parser.add_argument(
        "--no-confirm",
        action="store_true",
        help="Plan onayı bekleme (sessiz mod)"
    )
    
    parser.add_argument(
        "--profile",
        action="store_true",
        help="Performance profiling aktif et"
    )
    
    parser.add_argument(
        "--profile-memory",
        action="store_true",
        help="Tracemalloc ile detaylı hafıza profiling aktif et"
    )
    
    parser.add_argument(
        "--json",
        type=str,
        default=None,
        help="JSON dosyasından görev yükle (Phase B - Web Stack Support)"
    )

    parser.add_argument(
        "--list-stacks",
        action="store_true",
        help="Desteklenen stack listesini yazdır ve çık"
    )

    parser.add_argument(
        "--list-stacks-json",
        action="store_true",
        help="Desteklenen stack listesini JSON olarak yazdır ve çık"
    )
    
    args = parser.parse_args()

    # Stack listesi (Phase 7 validation helper)
    if args.list_stacks or args.list_stacks_json:
        _print_available_stacks(as_json=args.list_stacks_json)
        return
    
    # JSON Input modu (Phase B)
    if args.json:
        print("\n📄 JSON INPUT MODU")
        asyncio.run(json_input_main(args.json))
        return
    
    # Incremental Development modları
    if args.add_feature:
        print("\n➕ YENİ ÖZELLİK EKLEME MODU")
        asyncio.run(incremental_main(args.add_feature, args.project_path, fix_bug=False, ask_confirmation=not args.no_confirm))
    
    elif args.fix_bug:
        print("\n🐛 BUG DÜZELTME MODU")
        asyncio.run(incremental_main(args.fix_bug, args.project_path, fix_bug=True, ask_confirmation=not args.no_confirm))
    
    # Normal mod
    else:
        if args.human:
            print("\n🧑 İNSAN MODU AKTİF: Charlie olarak siz review yapacaksınız!")
            print("   Sıra size geldiğinde terminal'den input beklenir.\n")
        
        if args.task:
            print(f"\n📝 ÖZEL GÖREV: {args.task}\n")
        
        if args.profile:
            print("\n📊 PERFORMANCE PROFILING AKTİF")
        
        asyncio.run(main(
            human_reviewer=args.human, 
            custom_task=args.task, 
            enable_profiling=args.profile,
            enable_tracemalloc=args.profile_memory
        ))


if __name__ == "__main__":
    cli_main()
