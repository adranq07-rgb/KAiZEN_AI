"""Günlük güncelleme: güvenilir siteleri Kaizen'in kendi toplayıcısıyla tarar, süzgeci yeniler.

Kullanım (proje klasöründe):
    python -m accounting.refresh                 # tüm kaynaklar, kaynak başına en çok 60 sayfa
    python -m accounting.refresh --quick         # hızlı tur (kaynak başına 15 sayfa)
    python -m accounting.refresh --source "Muhasebe TR" --max-pages 200
    python -m accounting.refresh --backfill      # son 2 yıldan eski sayfaları da al
    python -m accounting.refresh --stats         # depodaki durumu göster
"""
import argparse
import json
import sys
from datetime import datetime
from pathlib import Path

from accounting.crawler import HermesFallbackFetcher, SiteCrawler, UrllibFetcher
from accounting.facts import FactRegistry
from accounting.site_store import SiteStore
from accounting.source_registry import TRUSTED_SOURCES, source_by_name

REPORT_PATH = Path(__file__).resolve().parent.parent / "data" / "refresh_report.json"


def run_refresh(sources=None, max_pages=60, since_years=2, backfill=False, min_delay=1.5,
                max_seconds=900, hermes_fallback=False, store=None, fetcher=None, registry=None,
                log=print, report_path=REPORT_PATH):
    store = store or SiteStore()
    fallback = None
    if hermes_fallback:
        from core.ai.hermes_provider import HermesProvider
        fallback = HermesFallbackFetcher(HermesProvider())
    crawler = SiteCrawler(store, fetcher or UrllibFetcher(min_delay=min_delay), fallback=fallback)
    chosen = [s for s in (sources or TRUSTED_SOURCES)]
    reports = []
    for source in chosen:
        log(f"[{source.name}] taranıyor...")
        report = crawler.crawl_source(
            source, max_pages=max_pages, since_years=since_years, backfill=backfill,
            max_seconds=max_seconds,
            progress=lambda name, n, url: log(f"   {n}. {url}") if n % 10 == 0 else None,
        )
        reports.append(report)
        note = f" ({report['stopped']})" if report.get("stopped") else ""
        log(f"[{source.name}] yeni={report['new']} güncel={report['updated']} değişmedi={report['unchanged']} "
            f"eski={report['old_skipped']} engelli={len(report['blocked'])} hata={len(report['errors'])}{note}")
    registry = registry or FactRegistry(store.db_path)
    facts = registry.rebuild(store)
    log(f"Süzgeç: {facts['topics_found']} parametre ({facts['verified']} doğrulanmış, "
        f"{facts['pending']} tek kaynak, {facts['conflict']} çelişkili)")
    summary = {
        "run_at": datetime.now().isoformat(timespec="seconds"),
        "sources": reports, "facts": facts, "stats": store.stats(),
    }
    if report_path:
        report_path = Path(report_path)
        report_path.parent.mkdir(parents=True, exist_ok=True)
        report_path.write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")
    return summary


def rebuild_only(store=None, registry=None, log=print):
    """Siteleri tekrar tarama; yalnız daha önce indirilmiş sayfalardan süzgeci (facts) yeniden kur.

    Süzgeç çıkarım/uzlaşı kurallarında düzeltme yapıldığında (ör. sayı ayrıştırma hatası), tüm
    kaynakları saatlerce tekrar taramak yerine bu kullanılır -- kayıtlı sayfalar zaten depoda.
    """
    store = store or SiteStore()
    registry = registry or FactRegistry(store.db_path)
    facts = registry.rebuild(store)
    log(f"Süzgeç yeniden kuruldu: {facts['topics_found']} parametre ({facts['verified']} doğrulanmış, "
        f"{facts['single_source']} tek kaynak, {facts['partially_verified']} kismen doğrulanmış, "
        f"{facts['conflict']} çelişkili)")
    return facts


def print_stats(store=None, registry=None, out=print):
    store = store or SiteStore()
    registry = registry or FactRegistry(store.db_path)
    out("KAYNAK                       SAYFA  İÇERİKLİ  EN GÜNCEL YIL  SON TARAMA")
    for row in store.stats():
        out(f"{row['source_name']:<28} {row['pages']:>5} {row['with_content']:>9} {str(row['latest_year'] or '-'):>14}  {row['last_fetch'][:19]}")
    verified = [r for r in registry.rows() if r["status"] == "verified"]
    out(f"\nYıllık parametre: {len(registry.rows())} kayıt, {len(verified)} doğrulanmış")


def main(argv=None):
    parser = argparse.ArgumentParser(description="Kaizen güvenilir site güncellemesi")
    parser.add_argument("--source", action="append", help="Yalnız bu kaynak (birden çok kez verilebilir)")
    parser.add_argument("--max-pages", type=int, default=60)
    parser.add_argument("--since-years", type=int, default=2)
    parser.add_argument("--backfill", action="store_true")
    parser.add_argument("--quick", action="store_true")
    parser.add_argument("--delay", type=float, default=1.5, help="Aynı siteye istekler arası saniye")
    parser.add_argument("--hermes-fallback", action="store_true")
    parser.add_argument("--stats", action="store_true")
    parser.add_argument("--list", action="store_true")
    parser.add_argument("--rebuild-only", action="store_true",
                        help="Siteleri tekrar tarama; yalnız daha önce indirilmiş sayfalardan süzgeci "
                             "(facts) yeniden kur. Süzgeç kurallarında/çıkarımda düzeltme yapıldığında kullanılır.")
    args = parser.parse_args(argv)
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    if args.list:
        for s in TRUSTED_SOURCES:
            print(f"{s.name:<26} {', '.join(s.domains)}" + ("  [yalnız referans]" if s.reference_only else ""))
        return 0
    if args.stats:
        print_stats()
        return 0
    if args.rebuild_only:
        rebuild_only()
        return 0
    chosen = None
    if args.source:
        chosen = []
        for name in args.source:
            source = source_by_name(name)
            if source is None:
                print(f"Bilinmeyen kaynak: {name}. --list ile kaynak adlarına bakın.")
                return 2
            chosen.append(source)
    run_refresh(chosen, max_pages=15 if args.quick else args.max_pages, since_years=args.since_years,
                backfill=args.backfill, min_delay=args.delay, hermes_fallback=args.hermes_fallback)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
