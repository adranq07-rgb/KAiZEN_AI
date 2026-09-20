from core.engine import KazenEngine

kazen = KazenEngine()

print("Kazen AI baslatildi.")
print("Cikmak icin 'cikis' yaz.")

while True:
    mesaj = input("\nSen: ")

    if mesaj.lower() == "cikis":
        print("Kazen: Gorusuruz.")
        break

    cevap = kazen.cevap_ver(mesaj)
    print(cevap)