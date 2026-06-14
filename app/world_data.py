# -*- coding: utf-8 -*-
"""Jointures du monde : secteur -> resGen -> resGroup -> resource -> items.
Permet 'ou trouver un item' (gisements + secteurs) et 'que miner dans un secteur'.
"""
import cdb_model

RESTYPE = {0: "Default", 1: "Gravite", 2: "Node", 3: "Deposit", 4: "Shell", 5: "Geyser",
           6: "Pool", 7: "ShipWreck", 8: "ShipWreckPart", 9: "Biological", 10: "BiologicalRoot",
           11: "Deco", 12: "Decal"}


def build_world(sheets):
    resources = {r["id"]: r for r in cdb_model._lines(sheets, "resource")}
    groups = {g["id"]: g for g in cdb_model._lines(sheets, "resGroup")}
    gens = {g["id"]: g for g in cdb_model._lines(sheets, "resGen")}
    sectors = {s["id"]: s for s in cdb_model._lines(sheets, "sector")}

    def group_resources(gid, seen=None):
        seen = seen or set()
        if gid in seen:
            return set()
        seen.add(gid)
        out = set()
        g = groups.get(gid)
        if g:
            for grp in (g.get("generation") or {}).get("groups", []):
                rr = (grp.get("gen") or {}).get("res")
                if rr in resources:
                    out.add(rr)
                elif rr in groups:
                    out |= group_resources(rr, seen)
        return out

    def gen_resources(genid):
        out = set()
        g = gens.get(genid)
        if g:
            for r in (g.get("resources") or []):
                rr = r.get("res")
                if rr in resources:
                    out.add(rr)
                elif rr in groups:
                    out |= group_resources(rr)
        return out

    def res_items(rid):
        return [it.get("item") for it in (resources.get(rid, {}).get("items") or []) if it.get("item")]

    sector_items, sector_res = {}, {}
    for sid, s in sectors.items():
        ritems, rres = set(), set()
        for x in (s.get("generation") or {}).get("regularResGen", []):
            for rid in gen_resources(x.get("resGen")):
                rres.add(rid)
                ritems |= set(res_items(rid))
        for lm in (s.get("props", {}).get("lootMaterial") or []):
            if lm.get("item"):
                ritems.add(lm["item"])
        sector_items[sid] = ritems
        sector_res[sid] = rres

    item_sectors = {}
    for sid, its in sector_items.items():
        for it in its:
            item_sectors.setdefault(it, set()).add(sid)

    # item -> liste de gisements (resource) qui le donnent
    item_sources = {}
    for rid, r in resources.items():
        for it in (r.get("items") or []):
            iid = it.get("item")
            if iid:
                item_sources.setdefault(iid, []).append({
                    "res": rid, "name": r.get("name"), "type": RESTYPE.get(r.get("type"), r.get("type")),
                    "tier": r.get("tier"), "proba": it.get("proba"),
                    "qtyMin": it.get("qtyMin"), "qtyMax": it.get("qtyMax"),
                })

    # gisements (resource) minables : id -> {name EN, items de sortie}
    deposits = {rid: {"name": r.get("name", rid),
                      "items": [it.get("item") for it in (r.get("items") or []) if it.get("item")]}
                for rid, r in resources.items() if (r.get("items"))}

    return {"sector_items": sector_items, "sector_res": sector_res,
            "item_sectors": item_sectors, "item_sources": item_sources,
            "deposits": deposits,
            "sector_name": {sid: s.get("name", sid) for sid, s in sectors.items()},
            "sector_reslevel": {sid: s.get("resLevel") for sid, s in sectors.items()},
            "sector_req": {sid: (s.get("props", {}).get("requirements") or []) for sid, s in sectors.items()}}


if __name__ == "__main__":
    import io, sys
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8")
    sheets = cdb_model.load_cdb()
    w = build_world(sheets)
    print("Calcite -> gisements:", [(s["name"], s["type"], "t"+str(s["tier"]), str(s["proba"])+"%") for s in w["item_sources"].get("Calcite", [])])
    print("Calcite -> secteurs:", sorted([w["sector_name"][s] for s in w["item_sectors"].get("Calcite", set())]))
