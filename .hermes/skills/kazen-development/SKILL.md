---
name: kazen-development
description: "Kazen AI projesini güvenli, kontrollü ve test odaklı biçimde geliştirmek için proje-yerel geliştirme kuralları."
version: 0.1.0
---

# Kazen Development

## Amaç

Kazen AI üzerinde geliştirme yapılırken bu skill kullanılmalıdır.

## Kurallar

1. Değişiklikten önce mevcut kodu incele.
2. Büyük değişiklikleri küçük adımlara böl.
3. Gereksiz dosya veya kod oluşturma.
4. Çalışan özellikleri sebepsiz değiştirme.
5. Kritik işlemlerden önce kullanıcı onayı iste.
6. İzinsiz dosya silme veya sistem ayarı değiştirme.
7. Kod değişikliğinden sonra test çalıştır.
8. Test başarısızsa hatayı gizleme.
9. Kazen'e ait kodları KAZEN_AI proje klasöründe tut.
10. Hermes ana kurulumunu doğrudan değiştirmek yerine Kazen'e özel katmanları kullan.

## Local-First

Kazen'in temel çalışma modeli yerel olmalıdır.

Kullanıcı açıkça istemedikçe bulut modeli veya ücretli API, Kazen'in zorunlu bağımlılığı yapılmamalıdır.

## Geliştirme Akışı

Planla -> İncele -> Değiştir -> Test Et -> Sonucu Bildir