"""Wikipedia のウィキテキストを扱う小さな道具（標準ライブラリのみ）。"""
import re


def _remove_nested(text, open_, close):
    """入れ子の open_...close を内側から順に取り除く。"""
    pat = re.compile(re.escape(open_) + r"(?:(?!" + re.escape(open_) + "|" + re.escape(close) + r").)*" + re.escape(close), re.S)
    prev = None
    while prev != text:
        prev = text
        text = pat.sub("", text)
    return text


def clean(text):
    """ウィキの記法を取り除いてプレーンテキストにする。"""
    if not text:
        return ""
    text = re.sub(r"<!--.*?-->", "", text, flags=re.S)
    text = re.sub(r"<ref[^>/]*/>", "", text)
    text = re.sub(r"<ref[^>]*>.*?</ref>", "", text, flags=re.S)
    text = re.sub(r"<br\s*/?>", " ", text, flags=re.I)
    text = _remove_nested(text, "{{", "}}")
    text = re.sub(r"\[\[(?:File|Image|ファイル|画像):[^\[\]]*(?:\[\[[^\]]*\]\][^\[\]]*)*\]\]", "", text, flags=re.I)
    text = re.sub(r"\[\[Category:[^\]]*\]\]|\[\[カテゴリ:[^\]]*\]\]", "", text)
    text = re.sub(r"\[\[([^\]|]*)\|([^\]]*)\]\]", r"\2", text)
    text = re.sub(r"\[\[([^\]]*)\]\]", r"\1", text)
    text = re.sub(r"\[https?://\S+\s+([^\]]*)\]", r"\1", text)
    text = re.sub(r"\[https?://\S+\]", "", text)
    text = re.sub(r"<[^>]+>", "", text)
    text = text.replace("'''", "").replace("''", "")
    text = re.sub(r"[ \t　]+", " ", text)
    text = re.sub(r"\n{3,}", "\n\n", text)
    return text.strip()


def find_infobox(wikitext):
    """神社の情報欄（{{...}}）を探して (テンプレート名, {項目: 値}) を返す。"""
    for m in re.finditer(r"\{\{", wikitext):
        start = m.start()
        depth, i = 0, start
        while i < len(wikitext):
            two = wikitext[i:i + 2]
            if two == "{{":
                depth += 1
                i += 2
            elif two == "}}":
                depth -= 1
                i += 2
                if depth == 0:
                    break
            else:
                i += 1
        body = wikitext[start + 2:i - 2]
        name = body.split("|", 1)[0].strip()
        if ("神社" in name or "Infobox" in name or "infobox" in name) and "|" in body:
            return name, _params(body.split("|", 1)[1])
    return "", {}


def _params(s):
    parts, buf, d_brace, d_brack = [], [], 0, 0
    i = 0
    while i < len(s):
        two = s[i:i + 2]
        if two == "{{":
            d_brace += 1; buf.append(two); i += 2; continue
        if two == "}}":
            d_brace -= 1; buf.append(two); i += 2; continue
        if two == "[[":
            d_brack += 1; buf.append(two); i += 2; continue
        if two == "]]":
            d_brack -= 1; buf.append(two); i += 2; continue
        if s[i] == "|" and d_brace == 0 and d_brack == 0:
            parts.append("".join(buf)); buf = []; i += 1; continue
        buf.append(s[i]); i += 1
    parts.append("".join(buf))
    out = {}
    for p in parts:
        if "=" in p:
            k, v = p.split("=", 1)
            out[k.strip()] = v.strip()
    return out


def split_sections(wikitext):
    """本文を (見出し, 本文) の一覧に分ける。先頭は見出し ''。"""
    pieces = re.split(r"^==+\s*([^=\n]+?)\s*==+\s*$", wikitext, flags=re.M)
    sections = [("", pieces[0])]
    for i in range(1, len(pieces), 2):
        sections.append((clean(pieces[i]), pieces[i + 1]))
    return sections
