# -*- coding: utf-8 -*-
"""Contrats (économie). La table `contract` du cdb = 204 contrats : items demandés, crédits
(`creditFormula`), récompenses (CorpoCredits / LicensePoints / CorpoReputation), client, niveau.
On calcule le PROFIT NET = crédits − coût de production des items demandés (voie la moins chère)."""
import cdb_model

SKIP = {"Deprecated", "Tuto"}


def contracts(sheets, items, unit_cost, contract_tr=None):
    """-> liste de dicts triés par profit net décroissant."""
    contract_tr = contract_tr or {}
    nm = lambda i: items.get(i, {}).get("name", i)
    out = []
    for c in cdb_model._lines(sheets, "contract"):
        its = c.get("items") or []
        title = contract_tr.get(c["id"]) or c.get("title") or c["id"]
        if not its or c.get("id") in SKIP or cdb_model.is_placeholder(title):
            continue
        cost = sum((x.get("qty") or 0) * (unit_cost.get(x.get("item"), 0) or 0) for x in its)
        credits = c.get("creditFormula") or 0
        lp = sum(r.get("count", 0) for r in (c.get("rewards") or []) if r.get("item") == "LicensePoints")
        rep = sum(r.get("count", 0) for r in (c.get("rewards") or []) if r.get("item") == "CorpoReputation")
        demand = ", ".join(f"{x.get('qty')}× {nm(x.get('item'))}" for x in its)
        out.append({"name": contract_tr.get(c["id"]) or c.get("title") or c["id"],
                    "client": c.get("client") or "", "level": c.get("level") or 0,
                    "demand": demand, "credits": round(credits), "lp": lp, "rep": rep,
                    "cost": round(cost), "net": round(credits - cost)})
    out.sort(key=lambda c: -c["net"])
    return out
