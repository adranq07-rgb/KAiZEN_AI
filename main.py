from core.engine import KazenEngine


def main():
    kazen = KazenEngine()

    print("Kazen AI baslatildi.")
    print("Cikmak icin 'cikis' yaz.")

    while True:
        try:
            mesaj = input("\nSen: ").strip()

            if mesaj.lower() == "cikis":
                print("Kazen: Gorusuruz.")
                break

            if not mesaj:
                continue

            cevap = kazen.cevap_ver(mesaj)
            print(f"\n{cevap}")

        except KeyboardInterrupt:
            print("\nKazen: Gorusuruz.")
            break

        except Exception as error:
            kazen.logger.error(
                f"Ana dongu hatasi: {type(error).__name__}: {error}"
            )
            print(f"Kazen: Beklenmeyen bir hata olustu: {error}")


if __name__ == "__main__":
    main()