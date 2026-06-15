# -*- coding: utf-8 -*-
"""Extrait data.cdb depuis res.pak (format Heaps/HashLink). Rejouable a chaque patch.

Format res.pak (reverse 2026-06-14, cf. notes/pak_format.md) :
  header  : "PAK" + version(1) + headerSize(int32)
  index   : headerSize octets, prefixe de 5 octets, puis entrees :
            dir  (flag&1) : flag + int32 nbEnfants + nameLen + name
            file         : flag + position + int32 size + int32 crc + nameLen + name
                           position = Double(8o) si flag&2 (LARGE file), sinon uint32(4o)
  data    : a partir de dataStart = 8 + headerSize ; fichiers stockes BRUTS (non compresses)
Le parse est "flag-d'abord" (le format officiel est "nom-d'abord" -> les champs lus
sont decales d'une entree : les vrais champs de data.cdb sont ceux de l'entree i+1).
"""
import struct, io, os, sys

DEFAULT_GAME_DIRS = [
    r"C:\Program Files (x86)\Steam\steamapps\common\SpaceCraft",
    r"D:\Steam\steamapps\common\SpaceCraft",
    r"D:\SteamLibrary\steamapps\common\SpaceCraft",
]
OUT = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "extracted", "data.cdb")


def find_pak():
    for d in DEFAULT_GAME_DIRS:
        p = os.path.join(d, "res.pak")
        if os.path.isfile(p):
            return p
    raise FileNotFoundError("res.pak introuvable. Edite DEFAULT_GAME_DIRS dans extract_cdb.py.")


def game_available():
    """True si le jeu (res.pak) est installe localement -> permet la re-extraction.
    False en mode cloud (l'app tourne alors sur les donnees deja extraites)."""
    try:
        find_pak()
        return True
    except Exception:
        return False


def parse_index(idx):
    """Retourne la liste des fichiers (pos, size, name) dans l'ordre du parse flag-d'abord."""
    files = []
    p = 5  # prefixe
    n = len(idx)
    while p < n - 4:
        flag = idx[p]; p += 1
        if flag & 1:  # repertoire
            p += 4
            nl = idx[p]; p += 1; p += nl
        else:  # fichier
            if flag & 2:  # large file -> position Double
                pos = struct.unpack_from("<d", idx, p)[0]; p += 8
            else:
                pos = float(struct.unpack_from("<I", idx, p)[0]); p += 4
            size = struct.unpack_from("<i", idx, p)[0]; p += 4
            p += 4  # crc
            nl = idx[p]; p += 1
            if p + nl > n:
                break
            name = idx[p:p+nl].decode("utf-8", "replace"); p += nl
            files.append((pos, size, name))
    return files


def extract_named(target, out_path, start_byte, pak_path=None):
    """Extrait un fichier texte du pak. start_byte = 1er octet attendu (b'{' JSON, b'<' XML).
    Retourne (out_path, taille) ou (None, 0) si le fichier n'existe pas dans le pak."""
    pak_path = pak_path or find_pak()
    with open(pak_path, "rb") as f:
        head = f.read(8)
        assert head[:3] == b"PAK", "magic PAK absent"
        header_size = struct.unpack_from("<i", head, 4)[0]
        idx = f.read(header_size)
        data_start = 8 + header_size
        files = parse_index(idx)
        names = [x[2] for x in files]
        if target not in names:
            return None, 0
        i = names.index(target)
        pos, size, _ = files[i + 1]            # decalage "nom-d'abord"
        base = data_start + int(pos)
        # vrai debut : 1ere occurrence de start_byte dans [base-16, base+16]
        f.seek(base - 16)
        win = f.read(32)
        k = win.find(start_byte)
        true_off = (base - 16 + k) if k != -1 else (base - 8)
        f.seek(true_off)
        buf = f.read(size)

    s = buf.decode("utf-8", "replace")
    a = s.find(start_byte.decode())
    if a > 0:
        s = s[a:]
    os.makedirs(os.path.dirname(out_path), exist_ok=True)
    with io.open(out_path, "w", encoding="utf-8") as out:
        out.write(s)
    return out_path, len(s)


def extract(pak_path=None, out_path=OUT):
    """Extrait data.cdb (JSON) et corrige la fin au dernier '}'."""
    path, n = extract_named("data.cdb", out_path, b"{", pak_path)
    with io.open(out_path, "r", encoding="utf-8") as f:
        s = f.read()
    end = s.rfind("}")
    if end != len(s) - 1:
        s = s[:end + 1]
        with io.open(out_path, "w", encoding="utf-8") as f:
            f.write(s)
    return out_path, len(s)


LANG_DIR = os.path.join(os.path.dirname(OUT))


def extract_lang(code="fr", pak_path=None):
    """Extrait export_<code>.xml (traductions). Retourne le chemin ou None.
    Marqueur racine = b'<cdb' (PAS b'<' seul : sinon on attrape le '</cdb>' de l'entrée
    précédente du pak -> XML mal formé). Trimme aussi la fin au dernier '</cdb>'."""
    out = os.path.join(LANG_DIR, f"export_{code}.xml")
    path, n = extract_named(f"export_{code}.xml", out, b"<cdb", pak_path)
    if path:
        with io.open(out, "r", encoding="utf-8") as f:
            s = f.read()
        a = s.find("<cdb")
        end = s.rfind("</cdb>")
        if a > 0 or (end != -1 and end != len(s) - 6):
            s = s[max(a, 0): end + 6 if end != -1 else len(s)]
            with io.open(out, "w", encoding="utf-8") as f:
                f.write(s)
    return path


def extract_all(langs=("fr",)):
    extract()
    for code in langs:
        extract_lang(code)


if __name__ == "__main__":
    p, n = extract()
    print(f"data.cdb -> {p} ({n:,} car)")
    for code in ("fr",):
        lp = extract_lang(code)
        print(f"export_{code}.xml -> {lp}")
