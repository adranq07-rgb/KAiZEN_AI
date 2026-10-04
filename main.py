import sys

from core.engine import KaizenEngine


def main():
    for stream in (sys.stdout, sys.stderr):
        if hasattr(stream, "reconfigure"):
            stream.reconfigure(encoding="utf-8", errors="replace")  # Windows konsolunda Türkçe karakterler bozulmasın

    Kaizen = KaizenEngine()

    print("Kaizen AI baslatildi.")
    print("Cikmak icin 'cikis' yaz.")

    while True:
        try:
            mesaj = input("\nSen: ").strip()

            if mesaj.lower() == "cikis":
                print("Kaizen: Gorusuruz.")
                break

            if not mesaj:
                continue

            cevap = Kaizen.cevap_ver(mesaj)
            print(f"\n{cevap}")

        except KeyboardInterrupt:
            print("\nKaizen: Gorusuruz.")
            break

        except Exception as error:
            Kaizen.logger.error(
                f"Ana dongu hatasi: {type(error).__name__}: {error}"
            )
            print(f"Kaizen: Beklenmeyen bir hata olustu: {error}")

    Kaizen.shutdown()


if __name__ == "__main__":
    main()
