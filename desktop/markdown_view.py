"""KAİZEN Desktop -- hafif Markdown ayrıştırıcı (tkinter'sız, test edilebilir).

Kaizen cevapları: başlıklar (#), paragraflar, madde işaretleri (-, *, •, ▸), numaralı listeler,
tablolar (| a | b |), kod blokları (```), **kalın**, `kod`, ve 'SONUÇ:' / 'KAYNAKLAR:' gibi büyük
harfli bölüm satırları. Çıktı: [Block(kind, spans|rows|text)]; çizimi `kazen_ui.py` yapar."""
from __future__ import annotations

import re
from dataclasses import dataclass, field

_BOLD = re.compile(r"\*\*(.+?)\*\*")
_CODE = re.compile(r"`([^`]+)`")
_BULLET = re.compile(r"^\s*(?:[-*•▸])\s+(.*)$")
_NUMBERED = re.compile(r"^\s*(\d{1,3})[.)]\s+(.*)$")
_HEADING = re.compile(r"^(#{1,4})\s+(.*)$")
_TABLE_ROW = re.compile(r"^\s*\|.*\|\s*$")
_TABLE_SEP = re.compile(r"^\s*\|?\s*:?-{2,}:?\s*(\|\s*:?-{2,}:?\s*)*\|?\s*$")
_SECTION = re.compile(r"^([A-ZÇĞİÖŞÜ][A-ZÇĞİÖŞÜ0-9 /_\-]{2,40}):\s*(.*)$")


@dataclass
class Block:
    kind: str                                   # heading | para | bullet | numbered | table | code | section | rule | blank
    spans: list = field(default_factory=list)   # [(text, style)] style: "" | "bold" | "code"
    level: int = 0
    rows: list = field(default_factory=list)    # table: [[cell,...]]
    text: str = ""                              # code
    marker: str = ""                            # numbered: "1."


def inline_spans(text):
    """**kalın** ve `kod` -> [(metin, stil)]. İşaretçiler kaldırılır; Türkçe karakterler aynen kalır."""
    spans, pos = [], 0
    pattern = re.compile(r"\*\*(.+?)\*\*|`([^`]+)`")
    for m in pattern.finditer(text):
        if m.start() > pos:
            spans.append((text[pos:m.start()], ""))
        if m.group(1) is not None:
            spans.append((m.group(1), "bold"))
        else:
            spans.append((m.group(2), "code"))
        pos = m.end()
    if pos < len(text):
        spans.append((text[pos:], ""))
    return spans or [("", "")]


def _cells(line):
    return [c.strip() for c in line.strip().strip("|").split("|")]


def parse_markdown(text):
    blocks = []
    lines = str(text or "").replace("\r\n", "\n").split("\n")
    i = 0
    while i < len(lines):
        line = lines[i]
        stripped = line.strip()
        if stripped.startswith("```"):
            i += 1
            code = []
            while i < len(lines) and not lines[i].strip().startswith("```"):
                code.append(lines[i])
                i += 1
            blocks.append(Block("code", text="\n".join(code)))
            i += 1
            continue
        if not stripped:
            if blocks and blocks[-1].kind != "blank":
                blocks.append(Block("blank"))
            i += 1
            continue
        if re.fullmatch(r"[-_=*]{3,}", stripped):
            blocks.append(Block("rule"))
            i += 1
            continue
        h = _HEADING.match(stripped)
        if h:
            blocks.append(Block("heading", spans=inline_spans(h.group(2)), level=len(h.group(1))))
            i += 1
            continue
        if _TABLE_ROW.match(line):
            rows = []
            while i < len(lines) and _TABLE_ROW.match(lines[i]):
                if not _TABLE_SEP.match(lines[i]):
                    rows.append(_cells(lines[i]))
                i += 1
            blocks.append(Block("table", rows=rows))
            continue
        b = _BULLET.match(line)
        if b:
            blocks.append(Block("bullet", spans=inline_spans(b.group(1)), level=(len(line) - len(line.lstrip())) // 2))
            i += 1
            continue
        n = _NUMBERED.match(line)
        if n:
            blocks.append(Block("numbered", spans=inline_spans(n.group(2)), marker=n.group(1) + "."))
            i += 1
            continue
        s = _SECTION.match(stripped)
        if s and len(stripped) < 200:
            blocks.append(Block("section", spans=[(s.group(1) + ":", "bold")] + ([(" " + s.group(2), "")] if s.group(2) else [])))
            i += 1
            continue
        blocks.append(Block("para", spans=inline_spans(stripped)))
        i += 1
    while blocks and blocks[-1].kind == "blank":
        blocks.pop()
    return blocks


def table_as_text(rows):
    """Tabloyu hizalı (monospace) metne çevirir -- Türkçe karakter genişliği 1 sayılır."""
    if not rows:
        return ""
    width = max(len(r) for r in rows)
    norm = [r + [""] * (width - len(r)) for r in rows]
    widths = [max(len(r[c]) for r in norm) for c in range(width)]
    out = []
    for idx, r in enumerate(norm):
        out.append("  ".join(cell.ljust(widths[c]) for c, cell in enumerate(r)).rstrip())
        if idx == 0 and len(norm) > 1:
            out.append("  ".join("─" * widths[c] for c in range(width)))
    return "\n".join(out)
