# -*- coding: utf-8 -*-
"""Charge data.cdb et construit items + recettes avec Valeur Ajoutee, station, temps, energie.

VA (Valeur Ajoutee) = somme(prix sortie x qty) - somme(prix entree x qty). SOLIDE.
Temps de craft = ESTIMATION : temps de base de la station x facteurs de la recette.
Energie/craft = PowerBaseCost de la station (craftValues). Reel.
"""
import json, io, os, re

EXTRACTED = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "extracted", "data.cdb")
_UNLOCK = {0: "Permit", 1: "Unique BP", 2: "Random BP", 3: "Cannot", 4: "Study", 5: "Dismantle", 6: "Custo"}

# Marqueurs de contenu dev/placeholder du cdb (à masquer partout dans l'UI)
_PLACEHOLDER = ("[", "???", "placeholder", "template", "débog", "debog", "debug", "deprecat",
                "not impl", "notimpl", "(sujet", "wip", "todo", "dummy", "fixme", " test")


def is_placeholder(name):
    """True si le nom est une entrée de dev/placeholder (NOT IMPL, DEPRECATED, test, ???, template…)."""
    if not name or not str(name).strip():
        return True
    n = str(name).strip().lower()
    return n == "???" or n.startswith("test") or any(m in n for m in _PLACEHOLDER)


def load_cdb(path=EXTRACTED):
    with io.open(path, "r", encoding="utf-8") as f:
        data = json.load(f)
    return {s["name"]: s for s in data["sheets"]}


def _lines(sheets, name):
    return sheets.get(name, {}).get("lines", [])


def _clean(s):
    return re.sub(r"<[^>]+>", "", s or "").strip()


def build(sheets, price_overrides=None, tr=None):
    price_overrides = price_overrides or {}
    tr = tr or {}
    item_tr = tr.get("item", {})
    tag_tr = tr.get("itemTag", {})
    type_tr = tr.get("itemType", {})

    # items
    items = {}
    for l in _lines(sheets, "item"):
        iid = l.get("id")
        name = item_tr.get(iid) or l.get("name", iid)
        if is_placeholder(name):
            continue  # masque le contenu dev/déprécié (coques épaves, items test, [TODO]…)
        items[iid] = {
            "id": iid,
            "name": name,
            "price": float(l.get("price", 0) or 0),
            "type": l.get("type", ""),
            "lootLevel": l.get("lootLevel", 0),
        }

    def price(iid):
        if iid in price_overrides:
            return float(price_overrides[iid])
        return items.get(iid, {}).get("price", 0.0)

    def iname(iid):
        return item_tr.get(iid) or items.get(iid, {}).get("name", iid)

    # stations (itemTag) : label EN/FR + temps de base
    tags = {l["id"]: (l.get("props") or {}) for l in _lines(sheets, "itemTag")}

    def station_label(sid):
        if not sid:
            return "-"
        return tag_tr.get(sid) or _clean(tags.get(sid, {}).get("label")) or sid

    # categories (itemType) : name EN/FR
    type_name_en = {l["id"]: l.get("name", l["id"]) for l in _lines(sheets, "itemType")}

    def cat_label(cid):
        if not cid:
            return "-"
        return type_tr.get(cid) or type_name_en.get(cid) or cid

    # energie par station (craftValues PowerBaseCost)
    power = {}
    for l in _lines(sheets, "craftValues"):
        if l.get("id") == "PowerBaseCost":
            for v in (l.get("values") or []):
                power[v.get("craftKind")] = v.get("value", 0)

    recipes = []
    for l in _lines(sheets, "craft"):
        ins = l.get("inputs", []) or []
        outs = l.get("outputs", []) or []
        pr = l.get("props", {}) or {}
        in_list = [(x.get("item"), int(x.get("qty", 1) or 1)) for x in ins]
        out_list = [(x.get("item"), int(x.get("qty", 1) or 1)) for x in outs]
        in_cost = sum(price(i) * q for i, q in in_list)
        out_val = sum(price(i) * q for i, q in out_list)
        va = out_val - in_cost

        where = l.get("where", "")
        base = tags.get(where, {})
        ctf = pr.get("craftTimeFactor", 1) or 1
        mtf = pr.get("manualTimeFactor", 1) or 1
        bauto = base.get("autoCraftTime")
        bman = base.get("manualCraftTime")
        t_auto = (bauto * ctf) if bauto else None
        t_manual = (bman * mtf * ctf) if bman else None
        # VA/heure basee sur le craft AUTO (machines en base) sinon manuel
        t_ref = t_auto or t_manual
        va_per_h = round(va / (t_ref / 3600.0), 2) if t_ref else None

        main_out = out_list[0][0] if out_list else l.get("id")
        if is_placeholder(iname(main_out)):
            continue  # recette d'un produit dev/déprécié
        recipes.append({
            "id": l.get("id"),
            "product": iname(main_out),
            "product_id": main_out,
            "all_outputs": out_list,  # [(item_id, qty)] toutes sorties (recettes multi-output)
            "va": round(va, 2),
            "out_qty": out_list[0][1] if out_list else 1,
            "va_per_h": va_per_h,
            "t_auto": round(t_auto, 1) if t_auto else None,
            "t_manual": round(t_manual, 1) if t_manual else None,
            "power": power.get(where, 0),
            "station": station_label(where),
            "category": cat_label(l.get("category", "")),
            "unlock": _UNLOCK.get(l.get("unlockType", 0), str(l.get("unlockType"))),
            "inputs_str": " + ".join(f"{q}x {iname(i)}" for i, q in in_list) or "-",
            "outputs_str": " + ".join(f"{q}x {iname(i)}" for i, q in out_list) or "-",
        })
    return items, recipes


if __name__ == "__main__":
    sheets = load_cdb()
    items, recipes = build(sheets)
    print(f"{len(items)} items, {len(recipes)} recettes")
    for r in sorted([x for x in recipes if x["va_per_h"] is not None], key=lambda x: x["va_per_h"], reverse=True)[:6]:
        print(f"  {r['va_per_h']:+9.1f}/h  VA={r['va']:+8.2f}  {r['product']:<20} [{r['station']}] {r['t_auto']}s")
