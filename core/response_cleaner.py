import re


class ResponseCleaner:
    @staticmethod
    def _strip_ansi(text):
        ansi_pattern = re.compile(
            r"\x1B(?:[@-Z\\-_]|\[[0-?]*[ -/]*[@-~])"
        )

        return ansi_pattern.sub("", text)

    @staticmethod
    def clean(text):
        if not text:
            return ""

        text = ResponseCleaner._strip_ansi(text)
        text = text.replace("\r", "")

        # Hermes oturum bilgisini temizle.
        footer_markers = [
            "\nResume this session with:",
            "\nSession:",
        ]

        for marker in footer_markers:
            position = text.find(marker)

            if position != -1:
                text = text[:position]

        # Hermes'in nihai cevap bloklarini bul.
        #
        # Promptun icinde de SONUC: kelimesi bulunabilecegi
        # icin ilkini degil, SONUNCU SONUC: bolumunu aliyoruz.
        result_positions = []

        for marker in ["SONUC:", "SONUÇ:"]:
            start = 0

            while True:
                position = text.find(marker, start)

                if position == -1:
                    break

                result_positions.append(position)
                start = position + len(marker)

        if result_positions:
            final_start = max(result_positions)
            text = text[final_start:]

        else:
            # SONUC bolumu yoksa reasoning ve arac ciktilarini
            # cevap olarak gostermeyelim.
            noisy_markers = [
                "Initializing agent...",
                "Reasoning",
                "preparing web_search",
                "preparing web_extract",
            ]

            if any(marker in text for marker in noisy_markers):
                return (
                    "Kaizen: Arastirma tamamlanamadi veya "
                    "nihai cevap olusturulamadi."
                )

        # Son cevap sonrasinda Hermes cercevesi kalirsa temizle.
        end_markers = [
            "\n╰─",
            "\n└─",
            "\nInitializing agent...",
        ]

        for marker in end_markers:
            position = text.find(marker)

            if position != -1:
                text = text[:position]

        # Gereksiz terminal cerceve satirlarini temizle.
        cleaned_lines = []

        for line in text.splitlines():
            stripped = line.strip()

            if not stripped:
                cleaned_lines.append("")
                continue

            if stripped.startswith("╭─"):
                continue

            if stripped.startswith("╰─"):
                continue

            if stripped.startswith("┌─"):
                continue

            if stripped.startswith("└─"):
                continue

            if set(stripped) <= {"─"}:
                continue

            cleaned_lines.append(line)

        text = "\n".join(cleaned_lines)

        # Fazla bos satirlari azalt.
        text = re.sub(
            r"\n{3,}",
            "\n\n",
            text
        )

        return text.strip()