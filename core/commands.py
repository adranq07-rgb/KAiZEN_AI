"""Kaizen komutları: model gerektirmeyen yönetim komutları (durum, kaynaklar, parametreler, güncelle...).

Komutlar sohbet satırından yazılır; mesaj bir komutsa cevap döner, değilse None.
"""
from core.text_tr import fold_tr

HELP = """Kaizen komutları:
  yardım                 bu liste
  durum                  hafıza, site deposu, parametre defteri ve model durumu
  kaynaklar              taradığım güvenilir siteler ve her birinden kaç sayfa sakladığım
  parametreler           süzgeçten geçmiş yıllık parametreler (oran, sınır, tavan...)
  parametre <konu>       bir parametrenin yıllara göre geçmişi (ör. parametre asgari ücret)
  yetenekler             Müşavirler Kulübü araçlarından hangilerini yapabiliyorum
  güncelle [sayfa]       sitelerden yeni bilgileri topla (varsayılan 30 sayfa/site) ve süzgeci yeniden çalıştır
  öğrendiklerim          araştırmayla öğrendiğim, henüz onaylanmamış bilgi kartları ve çelişki uyarıları
  onayla: soru           bekleyen bir bilgi kartını onayla (kalıcı hafızaya işlenir, bir daha araştırmam)
  düzelt: soru => doğru cevap    yanlış cevabı öğret (bir dahaki sefere bu cevap verilir)
Soru sorarken: 'muhasebe: ...' ya da 'matematik: ...' ön ekini kullanabilirsin; kullanmasan da anlarım."""


class CommandHandler:
    def __init__(self, engine):
        self.engine = engine

    def handle(self, message):
        text = message.strip()
        folded = fold_tr(text)
        head = folded.split(" ", 1)[0] if folded else ""
        single = folded == head  # tek kelimelik komutlar, cümlenin ilk kelimesi olarak yanlış anlaşılmasın
        if single and head in ("yardim", "help", "komutlar"):
            return HELP
        if single and head == "durum":
            return self.status()
        if single and head == "kaynaklar":
            return self.sources()
        if single and head == "parametreler":
            return self.parameters()
        if single and head in ("yetenekler", "yetenek"):
            return self.abilities()
        if head == "parametre":
            return self.parameter_history(text.split(None, 1)[1] if " " in text else "")
        if head == "guncelle" and len(folded.split()) <= 2:
            return self.refresh(text)
        if head.startswith("duzelt") and ("=>" in text):
            return self.correct(text)
        if single and head in ("ogrendiklerim", "ogrenilenler"):
            return self.learned()
        if head.startswith("onayla") and ":" in text:
            return self.approve(text)
        return None

    # --- komutlar -------------------------------------------------------------------
    def status(self):
        e = self.engine
        lines = ["Kaizen durumu:"]
        try:
            stats = e.learning_store.stats()
            kinds = ", ".join(f"{k}: {v}" for k, v in stats["by_type"].items())
            lines.append(f"- Ders/öğretilmiş bilgi: {stats['total']} parça ({kinds})")
        except Exception:
            pass
        if e.site_store is not None:
            per_source = e.site_store.stats()
            pages = sum(r["with_content"] or 0 for r in per_source)
            years = [r["latest_year"] for r in per_source if r["latest_year"]]
            lines.append(f"- Site deposu: {pages} sayfa, {len(per_source)} kaynaktan"
                         + (f"; en güncel yıl: {max(years)}" if years else ""))
        if e.facts is not None:
            rows = e.facts.rows()
            verified = sum(1 for r in rows if r["status"] == "verified")
            lines.append(f"- Parametre defteri: {len(rows)} kayıt ({verified} doğrulanmış)")
        if getattr(e, "cards", None) is not None:
            stats = e.cards.stats()
            lines.append(
                f"- Öğrenilen bilgi kartları: {stats.get('pending', 0)} beklemede, "
                f"{stats.get('confirmed', 0)} onaylanmış, {stats.get('contradictions', 0)} çelişki uyarısı"
            )
        provider = e.provider_manager.provider
        names = [type(p).__name__ for p in getattr(provider, "providers", [provider])]
        lines.append("- Model zinciri: " + " -> ".join(names))
        return "\n".join(lines)

    def sources(self):
        e = self.engine
        if e.site_store is None:
            return "Kaizen: Site deposu kapalı."
        from accounting.source_registry import TRUSTED_SOURCES
        lines = ["Güvenilir kaynaklarım (öncelik 1 = resmî):"]
        for source in TRUSTED_SOURCES:
            count = e.site_store.count(source.name, with_content=True)
            lines.append(f"- {source.name} [öncelik {source.priority}]: {count} sayfa | {', '.join(source.domains)}")
        return "\n".join(lines)

    def abilities(self):
        import json
        from pathlib import Path
        path = Path(__file__).resolve().parent.parent / "knowledge" / "kaizen_yetenekleri.json"
        try:
            chunks = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            return "Kaizen: Yetenek listesi okunamadı."
        return "\n\n".join(f"{c['section']}:\n{c['text']}" for c in chunks[:3])

    def parameters(self):
        e = self.engine
        if e.facts is None:
            return "Kaizen: Parametre defteri kapalı."
        rows = e.facts.rows()
        if not rows:
            return "Kaizen: Parametre defteri boş. 'güncelle' komutuyla siteleri tarayıp doldurabilirsin."
        titles = {t.id: t.title for t in e.facts.topics}
        lines = ["Parametre defteri (en yeni yıl önce):"]
        for r in rows:
            mark = {"verified": "✔ doğrulanmış", "pending": "… tek kaynak", "conflict": "✖ çelişkili"}.get(r["status"], r["status"])
            lines.append(f"- {titles.get(r['topic'], r['topic'])} ({r['year']}): {r['value']}  [{mark}]")
        return "\n".join(lines)

    def parameter_history(self, query):
        e = self.engine
        if e.facts is None or not query.strip():
            return "Kullanım: parametre <konu>  (ör. parametre asgari ücret)"
        topic = e.facts.find_topic(query)
        if topic is None:
            return f"Kaizen: '{query}' için tanımlı bir parametre konusu bulamadım. 'parametreler' ile listeyi görebilirsin."
        lines = [f"{topic.title} - kayıtlar:"]
        for r in e.facts.rows(topic.id):
            lines.append(f"- {r['year']}: {r['value']} [{r['status']}]")
        history = e.facts.history(topic.id)
        if history:
            lines.append("Değişiklik geçmişi:")
            for h in history[-5:]:
                lines.append(f"- {h.get('changed_at', '')}: {h.get('year', '')} {h.get('old_value', '')} -> {h.get('new_value', '')}")
        return "\n".join(lines)

    def refresh(self, text):
        e = self.engine
        if e.site_store is None:
            return "Kaizen: Site deposu kapalı."
        parts = text.split()
        pages = int(parts[1]) if len(parts) > 1 and parts[1].isdigit() else 30
        from accounting.refresh import run_refresh
        log = []
        summary = run_refresh(store=e.site_store, max_pages=pages, log=log.append, registry=e.facts)
        new = sum(r["new"] for r in summary["sources"])
        updated = sum(r["updated"] for r in summary["sources"])
        blocked = sum(len(r["blocked"]) for r in summary["sources"])
        errors = sum(len(r["errors"]) for r in summary["sources"])
        facts = summary["facts"]
        return (f"Güncelleme bitti: {new} yeni, {updated} değişen sayfa; {blocked} adres robots.txt nedeniyle atlandı, {errors} hata.\n"
                f"Süzgeç: {facts['topics_found']} parametre ({facts['verified']} doğrulanmış, "
                f"{facts['pending']} tek kaynak, {facts['conflict']} çelişkili).")

    def learned(self):
        e = self.engine
        if getattr(e, "cards", None) is None:
            return "Kaizen: Bilgi kartı sistemi kapalı."
        pending = e.cards.all_cards(status="pending")
        confirmed = e.cards.all_cards(status="confirmed")
        contradictions = e.cards.contradictions()
        lines = [f"Öğrenilen bilgi kartları: {len(pending)} beklemede, {len(confirmed)} onaylanmış."]
        if pending:
            lines.append("\nBekleyenler (onaylamak için: onayla: <soru>):")
            for card in pending[:10]:
                lines.append(f"- \"{card['question']}\" — {card['answer'][:120]}...")
        if contradictions:
            lines.append("\nÇelişki uyarıları (araştırma ile parametre defteri uyuşmuyor):")
            for c in contradictions[:5]:
                lines.append(f"- {c['detail']}")
        return "\n".join(lines)

    def approve(self, text):
        e = self.engine
        if getattr(e, "cards", None) is None:
            return "Kaizen: Bilgi kartı sistemi kapalı."
        _, _, question = text.partition(":")
        question = question.strip()
        if not question:
            return "Kullanım: onayla: <soru>"
        card = e.brain.confirm_card(question)
        if card is None:
            return f"Kaizen: '{question}' için bekleyen bir bilgi kartı bulamadım. 'öğrendiklerim' ile listeyi görebilirsin."
        return f"Kaizen: Onaylandı, kalıcı hafızaya işlendi -> \"{card['question']}\""

    def correct(self, text):
        e = self.engine
        _, _, body = text.partition(":")
        question, _, correct = body.partition("=>")
        question, correct = question.strip(), correct.strip()
        if not question or not correct:
            return "Kullanım: düzelt: soru => doğru cevap"
        return e.accounting_agent.learn(question=question, wrong_answer="(kullanıcı düzeltmesi)", correct_answer=correct)
