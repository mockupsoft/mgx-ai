# -*- coding: utf-8 -*-
"""
MGX Agent CLI Module

Command-line interface for MGX Style Multi-Agent Team.
"""

import asyncio
import argparse

from .team import MGXStyleTeam


async def main(human_reviewer: bool = False, custom_task: str = None):
    """
    MGX tarzı takım örneği
    
    Args:
        human_reviewer: True ise Charlie (Reviewer) insan olarak çalışır
        custom_task: Özel görev tanımı (None ise varsayılan görev)
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
    
    # Takımı oluştur (human_reviewer=True yaparak insan olarak katılabilirsin)
    mgx_team = MGXStyleTeam(human_reviewer=human_reviewer)
    
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
    
    args = parser.parse_args()
    
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
        
        asyncio.run(main(human_reviewer=args.human, custom_task=args.task))


if __name__ == "__main__":
    cli_main()
