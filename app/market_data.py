# -*- coding: utf-8 -*-
"""Prix de rachat des stations (sheet spaceObject@props@buyout) : où VENDRE un item et à quel prix.
`value` = prix payé par la station quand tu lui vends (prix de vente joueur).
`price` = prix d'achat à la station (si présent). Les ventes scénarisées (tutoriel : props.mission
ou requiredEvent = one-shot) sont exclues : pas du marché répétable."""
import cdb_model

# 6 stations hubs du quadrant Haronex : id cdb (spaceObject) -> nom in-game
STATION_NAMES = {
    "Station_Start": "Babylon", "Station_Threshold": "Raqmu", "Station_Cairn": "Syracuse",
    "Station_Justice": "Nemea", "Station_Horizon": "Ur", "Station_Terminus": "Helicon",
}


def sell_index(sheets):
    """{item_id: [{station, sell, buy}]} trié par meilleur prix de vente décroissant."""
    idx = {}
    for l in cdb_model._lines(sheets, "spaceObject"):
        station = STATION_NAMES.get(l.get("id"))
        if not station:
            continue
        for e in (l.get("props") or {}).get("buyout") or []:
            p = e.get("props") or {}
            if p.get("mission") or p.get("requiredEvent"):
                continue  # vente scénarisée (tuto) -> pas du marché libre
            item = e.get("item")
            if not item:
                continue
            idx.setdefault(item, []).append({"station": station, "sell": e.get("value"), "buy": e.get("price")})
    for item in idx:
        idx[item].sort(key=lambda d: -(d["sell"] or 0))
    return idx
