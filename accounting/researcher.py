from datetime import date

from accounting.knowledge_store import AccountingKnowledgeStore
from accounting.source_registry import search_domains

# Kaizen'in TÜM cevap yollarında (yerel hafıza, araştırma, süzgeç) aynı ses: Türkiye'de
# çalışan bir mali müşavir gibi düşünüp cevap vermek. accounting/retriever.py::build_prompt
# yerel hafıza yolunda bunu zaten söylüyordu; araştırma zincirinin (bu dosya) prompt'larında
# yalnızca "araştırmacı" kimliği vardı, mali müşavir çerçevesi eksikti -- burada eklendi.
_ADVISOR_VOICE = (
    "Sen Kaizen AI'sın: Türkiye'de çalışan bir mali müşavir gibi düşünüp cevap veriyorsun. "
    "Kuruşu kuruşuna doğru, kaynağını gösteren, bilmediğini uydurmayan bir mali müşavir üslubu kullan.\n"
)


class AccountingResearcher:
    def __init__(self, provider, knowledge_store=None):
        self.provider = provider
        self.knowledge_store = knowledge_store or AccountingKnowledgeStore()

    def research(self, question):
        today = date.today()
        try:
            two_years_ago = today.replace(year=today.year - 2)
        except ValueError:
            two_years_ago = today.replace(year=today.year - 2, day=28)

        cached = self.knowledge_store.find_recent(question, two_years_ago)
        if cached:
            return (
                f"{cached['answer']}\n\n"
                f"Kaizen yerel bilgi deposu: {cached['source_name']}\n"
                f"Kaynak: {cached['url']}"
            )

        local_pages = self.knowledge_store.search_latest(question, limit=3)
        if local_pages:
            context = "\n\n".join(
                f"KAYNAK: {row['url']}\n{row['content'][:6000]}"
                for row in local_pages
            )
            local_prompt = f"""{_ADVISOR_VOICE}
Kaizen'in yerel muhasebe bilgi deposunu kullan.
Soru: {question}
Yalniz asagidaki metinlere dayanarak net ve kisa cevap ver. Bilgi yoksa
"yerel bilgide bulunamadi" de. Oran veya tutar uydurma. Kaynak URL'yi yaz.

{context}
"""
            ask = getattr(self.provider, "ask", None)
            if callable(ask):
                local_answer = ask(local_prompt)
                if "yerel bilgide bulunamadi" not in local_answer.casefold():
                    return local_answer

        all_domains = search_domains()
        official_domains = ", ".join(all_domains[:2])
        professional_domains = ", ".join(all_domains[2:])

        prompt = f"""{_ADVISOR_VOICE}
Şu an Türkiye muhasebe, vergi ve SGK konusunda araştırma yapıyorsun.
Bugun: {today.isoformat()}. Soru: {question}

1. web_search ile once {two_years_ago.isoformat()} ve sonrasi kaynaklari ara.
   Yalniz su resmi alan adlarini kullan: {official_domains}
2. Buldugun en ilgili kaynagi web_extract ile ac ve metnini oku.
   Gerekirse ikinci kaynakla karsilastir. Son iki yilda cevap yoksa
   daha eski kaynaga git; bugun hala gecerli olup olmadigini ara.
3. Sadece arama ozetine dayanarak kesin cevap verme. Kaynak acilmazsa
   bunu acikca soyle. Tarih, madde numarasi veya URL uydurma.
4. Kisa cevap yaz: SONUC, DAYANAK, UYGULAMA (gerekirse), KAYNAKLAR.
   KAYNAKLAR bolumune actigin sayfanin tam URL adresini ekle.
   Yalniz sorulan ana sonucu yaz; sorulmayan ozel oranlari listeleme.
5. En sona tek satirlik KANIT: ekle. Actigin kaynaktan sonucu dogrudan
   destekleyen en az 20 karakterlik cumleyi aynen aktar. Cevapta
   yuzdelik oran varsa bu oran KANIT cumlesinde de gecsin.
6. KANIT satirindan once YAYIN_TARIHI: YYYY-AA-GG satiri yaz.
   Sayfada gun yoksa tarih uydurma; kesin cevap verme.
"""

        research_method = getattr(self.provider, "research_packet", None)
        if not callable(research_method):
            research_method = getattr(self.provider, "research", None)
        if not callable(research_method):
            return "Kaizen: Kullanilan AI provider arastirma ozelligini desteklemiyor."

        result = research_method(prompt)
        if not isinstance(result, dict):
            return result
        if not result.get("verified"):
            professional_prompt = f"""{_ADVISOR_VOICE}
Soru: {question}
Bugun: {today.isoformat()}. Son iki yilda su mesleki alan adlarinda ara:
{professional_domains}
Forum, soru-cevap ve yorum kullanma. web_search sonucundan en ilgili sayfayi
web_extract ile ac. Yalniz sorulan ana sonucu yaz. Cevap bicimi: SONUC,
DAYANAK, KAYNAKLAR (tam URL), YAYIN_TARIHI: YYYY-AA-GG, tek satirda ve
kaynaktan aynen KANIT:. Kaynak acilmazsa veya tarih yoksa kesin cevap verme.
"""
            result = research_method(professional_prompt)
            if not isinstance(result, dict):
                return result
        if isinstance(result, dict) and not result.get("verified"):
            deep_prompt = f"""{_ADVISOR_VOICE}
DERIN ARASTIRMA: {question}
Bugun {today.isoformat()}. Oncelikli kaynak katalogunda sonuc bulunamadi.
Web genelinde ara; en az iki bagimsiz kaynagi web_extract ile ac.
Iki kaynak ayni sonucu desteklemiyorsa kesin cevap verme.
SONUC, DAYANAK, KAYNAKLAR, YAYIN_TARIHI: YYYY-AA-GG ve kaynaktan
aynen alinmis KANIT: satiri ile kisa cevap ver. URL veya tarih uydurma.
"""
            try:
                result = research_method(deep_prompt, trusted_only=False)
            except TypeError:
                return result.get("answer", "Kaizen: Guvenilir kaynakta cevap bulunamadi.")
            if not isinstance(result, dict) or not result.get("verified"):
                return result.get("answer", "Kaizen: Derin arastirmada dogrulanmis cevap bulunamadi.")

        for source in result.get("sources", []):
            self.knowledge_store.save(
                question=question,
                answer=result["answer"],
                evidence=source["evidence"],
                source_name=source["source_name"],
                url=source["url"],
                content=source["content"],
                published_at=source["published_at"],
                effective_year=source.get("effective_year"),
                metadata={"priority": source["priority"], "title": source["title"]},
            )
        return result["answer"]
