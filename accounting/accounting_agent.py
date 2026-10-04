from accounting.document_verifier import deterministic_matches, format_deterministic_block
from accounting.knowledge_base import AccountingKnowledgeBase
from accounting.learning_memory import LearningMemory
from accounting.researcher import AccountingResearcher, _ADVISOR_VOICE


class AccountingAgent:
    def __init__(self, provider, learning_memory_path=None):
        self.provider = provider
        self.knowledge_base = AccountingKnowledgeBase()
        self.learning_memory = LearningMemory(file_path=learning_memory_path)
        self.researcher = AccountingResearcher(provider)

    def ask(self, question):
        question = question.strip()

        if not question:
            return "Kaizen: Muhasebe sorusu bos olamaz."

        # 1. Daha once kullanici tarafindan duzeltilmis bilgi var mi?
        learned = self.learning_memory.get_all()

        normalized_question = " ".join(question.casefold().split())
        for record in reversed(learned):
            if " ".join(record["question"].casefold().split()) == normalized_question:
                return (
                    "KULLANICININ SON DUZELTMESI (guncelligi yeniden dogrulanmadi):\n"
                    f"{record['correct_answer']}"
                )

        # 2. Kaizen'in kendi bilgi tabaninda bilgi var mi?
        knowledge_results = self.knowledge_base.search(question)

        if knowledge_results:
            result = knowledge_results[0]

            answer = result["answer"]

            if result.get("source"):
                answer += f"\n\nKaynak: {result['source']}"

            return answer

        # 3. Bilgi yoksa arastirma katmanina git
        return self.researcher.research(question)

    def verify_document(self, file_text, facts_context="", facts_registry=None):
        """Kullanicinin kendi belgesindeki (excel/pdf) rakamlari Kaizen'in doğrulanmış
        parametre defteriyle karsilastirir. 'excel bilgisini teyit et' / 'hesaplarımı
        kontrol et' istegi icin: sohbetten cagrilir (bkz. core/commands.py::verify_file).

        Yeni web aramasi yapmaz; yalniz elde var olan belge metnini ve Kaizen'in
        zaten dogrulanmis parametrelerini (facts_context) karsilastirir. Bu yuzden
        arastirma onbellegine (knowledge_store) yazmaz -- researcher.research()'ten
        farkli, tek seferlik bir kontrol islemidir.

        DÜZELTME (2026-09-23): Eskiden "uyuşuyor/uyuşmuyor" kararının TAMAMI modele
        bırakılıyordu; ayrıca modele yalnız belge metninin ilk 8.000 karakteri gönderiliyor,
        bu kesilme kullanıcıya hiç bildirilmiyordu -- büyük bir belgenin tamamı kontrol edilmiş
        SANILABİLİYORDU. Artık, `facts_registry` verilirse (bkz. accounting/document_verifier.py),
        parametre defterinde doğrulanmış karşılığı olan HER kalem, belge metninin TAMAMI
        üzerinde (8.000 karakter sınırından ETKİLENMEDEN) kodla -- model hiç karışmadan --
        kesin olarak karşılaştırılıp "KESİN KOD KARŞILAŞTIRMASI" bloğu olarak öne ekleniyor.
        Model yalnızca bu blokta yer ALMAYAN (parametre defterinde tanımlı bir konu olmayan)
        kalemler için serbest yorum ekliyor; modele giden metin hâlâ (maliyet/bağlam nedeniyle)
        8.000 karakterle sınırlı ama artık bu kesilme, kesilme varsa açıkça bildiriliyor.
        """
        file_text = (file_text or "").strip()
        if not file_text:
            return "Kaizen: Kontrol edilecek belge içeriği boş."

        facts_block = facts_context.strip() if facts_context else "(Parametre defterimde doğrulanmış kayıt yok.)"

        # KESİN (kodla) katman: belge metninin TAMAMI üzerinde çalışır, aşağıdaki 8.000
        # karakterlik model penceresinden bağımsızdır.
        matches = deterministic_matches(file_text, facts_registry)
        deterministic_block = format_deterministic_block(matches)

        excerpt = file_text[:8000]
        truncated = len(file_text) > 8000
        truncation_note = ""
        if truncated:
            truncation_note = (
                f"\nNOT: Belge {len(file_text)} karakter uzunluğunda; aşağıda yalnız ilk 8.000 "
                "karakterini görüyorsun. Yorumunun belgenin TAMAMINI kapsadığını varsayma -- "
                "yukarıdaki KESİN KOD KARŞILAŞTIRMASI (varsa) belge metninin tamamı taranarak "
                "üretildi, yalnız SENİN bu serbest yorumun kesilmiş metne dayanıyor.\n"
            )

        prompt = f"""{_ADVISOR_VOICE}
Görev: Aşağıdaki belgedeki (kullanıcının kendi Excel/PDF dosyası) rakamları,
kalemleri ve oranları, Kaizen'in doğrulanmış parametre defteriyle karşılaştır.
Bir mali müşavirin, müşterisinin getirdiği tabloyu satır satır kontrol etmesi gibi çalış.

Kaizen'in doğrulanmış parametreleri (yıl: değer):
{facts_block}
{truncation_note}
Belge içeriği:
{excerpt}

Kurallar:
1. Yalnız belgede GEÇEN kalemleri kontrol et; belgede olmayan bir şeyi sorma veya ekleme.
2. Belgedeki bir değer parametre defteriyle karşılaştırılabiliyorsa: UYUŞUYOR ya da
   UYUŞMUYOR de (uyuşmuyorsa doğru değeri ve kaynağını yaz).
3. Parametre defterinde karşılığı olmayan (KDV, stopaj, asgari ücret gibi bilinen bir
   oran/parametre değil) kalemler için "bu kalemi doğrulanmış verimle karşılaştıramıyorum"
   de -- rakamı uydurma, tahmin etme.
4. Kısa ve maddeler halinde yaz: her kalem için tek satır.
5. Sonunda tek cümlelik özet: kaç kalem uyuştu, kaç kalem uyuşmadı, kaç kalem
   karşılaştırılamadı.
"""
        ask = getattr(self.provider, "ask", None)
        research = getattr(self.provider, "research", None)
        if callable(ask):
            ai_text = ask(prompt)
        elif callable(research):
            ai_text = research(prompt)
        else:
            ai_text = None

        if ai_text is None:
            if deterministic_block:
                return deterministic_block  # AI yok ama kesin katman var -- o, belgenin tamamını zaten taradı
            return "Kaizen: Kullanılan AI provider bu özelliği desteklemiyor."

        if not deterministic_block:
            result = ai_text  # eski davranış: facts_registry verilmediyse (veya eşleşme yoksa) çıktı değişmez
        else:
            result = (
                f"{deterministic_block}\n\n"
                "AI YORUMU (modelin serbest incelemesi; yukarıdaki KESİN KOD KARŞILAŞTIRMASI ile "
                "çelişirse KESİN olanı esas al):\n"
                f"{ai_text}"
            )

        # DÜZELTME (2026-09-23): kesilme uyarısını yalnız MODELE göndermek yetmez -- model bunu
        # cevabına yansıtmayabilir. Bu yüzden kesilme varsa, çıktıya kodla (garanti şekilde) EK
        # bir not ekleniyor; kullanıcı bunu modelin ne yazdığından bağımsız her zaman görür.
        if truncated:
            result += (
                f"\n\n(NOT: Belge {len(file_text)} karakter; yukarıdaki AI yorumu yalnız ilk "
                "8.000 karakteri kapsıyor -- bu yorumun belgenin TAMAMINI kontrol ettiğini "
                "varsayma. "
                + ("KESİN KOD KARŞILAŞTIRMASI (yukarıda) belge metninin TAMAMI taranarak üretildi, "
                   "bu kesilmeden etkilenmedi.)" if deterministic_block else
                   "Bu belge için parametre defterinde kodla otomatik karşılaştırılabilecek "
                   "bilinen bir kalem bulunamadı; büyük belgelerde `oku:` ile parça parça okuyup "
                   "ayrıca gözden geçirmen önerilir.)")
            )
        return result

    def learn(
        self,
        question,
        wrong_answer,
        correct_answer,
        user_note=None
    ):
        self.learning_memory.add_correction(
            question=question,
            wrong_answer=wrong_answer,
            correct_answer=correct_answer,
            user_note=user_note
        )

        return "Kaizen: Duzeltme kaydedildi."
