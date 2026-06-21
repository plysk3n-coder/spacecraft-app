# -*- coding: utf-8 -*-
"""Rendu 'joli' des ressources d'une planète : cartes avec icône du jeu, groupées par catégorie.
Rendu HTML inline (st.markdown unsafe_allow_html) -> hauteur naturelle, PAS d'ascenseur.
Les icônes viennent de app/res_icons.json (croppées des sprite sheets du res.pak)."""

# ordre + emoji par catégorie (RESTYPE du cdb)
_CATS = [
    ("Deposit", "⛏️"), ("Node", "🔹"), ("Gravite", "🪨"), ("Shell", "🐚"),
    ("Geyser", "💧"), ("Pool", "🌊"), ("Biological", "🌿"), ("BiologicalRoot", "🌱"),
    ("ShipWreckPart", "🛰️"), ("ShipWreck", "🛰️"), ("Default", "◆"), ("Autre", "◆"),
]
_EMOJI = dict(_CATS)
_ORDER = {c: i for i, (c, _) in enumerate(_CATS)}


def _esc(s):
    return str(s).replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")


def _card(img, name, qty, dens, cat, lab_q, lab_d):
    ico = (f'<img src="{img}" style="width:46px;height:46px;flex:0 0 46px;border-radius:6px;"/>'
           if img else
           f'<div style="width:46px;height:46px;flex:0 0 46px;border-radius:6px;background:#2c3140;'
           f'display:flex;align-items:center;justify-content:center;font-size:22px;">{_EMOJI.get(cat,"◆")}</div>')
    sub = []
    if qty not in (None, ""):
        sub.append(f'{lab_q} <b style="color:#cfe3ff">{qty}</b>')
    if dens not in (None, ""):
        sub.append(f'{lab_d} <b style="color:#cfe3ff">{dens}</b>')
    subline = " · ".join(sub) or "&nbsp;"
    return (
        '<div style="display:inline-flex;align-items:center;gap:11px;background:#161922;'
        'border:1px solid #2c3140;border-radius:11px;padding:9px 15px;margin:5px;min-width:235px;'
        'box-shadow:0 1px 3px rgba(0,0,0,.4);">'
        f'{ico}'
        '<div style="line-height:1.3;">'
        f'<div style="color:#f0f2f6;font-weight:600;font-size:14.5px;">{_esc(name)}</div>'
        f'<div style="color:#8b94a7;font-size:12px;">{subline}</div>'
        '</div></div>'
    )


def ingot_cards(planets, resname, icons, title, via_word):
    """Section 'Lingots possibles' par planète. planets = [(nom, [(ingot_id, [noms_minerais]), ...])]."""
    multi = len(planets) > 1
    html = ['<div style="font-family:Inter,system-ui,sans-serif;">']
    for pl, ings in planets:
        if not ings:
            continue
        head = f'🔩 {_esc(title)}'
        if multi:
            head += f' — <span style="color:#fff;">{_esc(pl)}</span>'
        html.append(f'<div style="color:#ffd479;font-weight:700;font-size:15px;margin:14px 0 2px;">{head}</div>')
        html.append('<div style="display:flex;flex-wrap:wrap;">')
        for iid, ores in sorted(ings, key=lambda x: resname(x[0])):
            img = icons.get(iid, {}).get("img")
            ico = (f'<img src="{img}" style="width:46px;height:46px;flex:0 0 46px;border-radius:6px;"/>'
                   if img else '<div style="width:46px;height:46px;flex:0 0 46px;border-radius:6px;'
                   'background:#2c3140;display:flex;align-items:center;justify-content:center;">🔩</div>')
            sub = f'{_esc(via_word)} ' + ", ".join(_esc(resname(o)) for o in ores[:3]) if ores else "&nbsp;"
            html.append(
                '<div style="display:inline-flex;align-items:center;gap:11px;background:#1a1710;'
                'border:1px solid #45391f;border-radius:11px;padding:9px 15px;margin:5px;min-width:235px;">'
                f'{ico}<div style="line-height:1.3;">'
                f'<div style="color:#f3e6c8;font-weight:600;font-size:14.5px;">{_esc(resname(iid))}</div>'
                f'<div style="color:#a8966f;font-size:12px;">{sub}</div></div></div>')
        html.append('</div>')
    html.append('</div>')
    return "".join(html)


def render(planets, resname, cat_label, icons, lab_qty, lab_dens):
    """planets = liste ordonnée de (nom_planète, [(rid, count, density), ...]).
    resname(rid)->nom traduit ; cat_label(restype_en)->libellé traduit ; icons = res_icons.json."""
    multi = len(planets) > 1
    html = ['<div style="font-family:Inter,system-ui,sans-serif;">']
    for pl, rows in planets:
        if multi:
            html.append(f'<div style="color:#fff;font-weight:800;font-size:18px;margin:18px 0 4px;'
                        f'padding-bottom:4px;border-bottom:1px solid #333;">🪐 {_esc(pl)}</div>')
        # regrouper par catégorie
        by_cat = {}
        for rid, cnt, dens in rows:
            meta = icons.get(rid, {})
            by_cat.setdefault(meta.get("cat", "Autre"), []).append((rid, cnt, dens, meta.get("img")))
        for cat in sorted(by_cat, key=lambda c: _ORDER.get(c, 99)):
            items = sorted(by_cat[cat], key=lambda x: (-(x[1] or 0), resname(x[0])))
            html.append(f'<div style="color:#7fb3ff;font-weight:700;font-size:15px;margin:14px 0 2px;">'
                        f'{_EMOJI.get(cat,"◆")} {_esc(cat_label(cat))} <span style="color:#667;">({len(items)})</span></div>')
            html.append('<div style="display:flex;flex-wrap:wrap;">')
            for rid, cnt, dens, img in items:
                html.append(_card(img, resname(rid), cnt, dens, cat, lab_qty, lab_dens))
            html.append('</div>')
    html.append('</div>')
    return "".join(html)
