# -*- coding: utf-8 -*-
"""Graphes/tableaux : chaines de craft (voie la moins chere) + carte de l'univers."""
import cdb_model

_COLORS = {
    "product": "#e8542f", "intermediate": "#4575b4", "raw": "#1a9850",
    "sector": "#9b59b6", "system": "#16a085", "planet": "#2980b9",
    "object": "#e67e22", "instance": "#c0392b",
}


# Stations a EXCLURE de la production "normale" (recyclage = inputs a prix 0, pas une vraie chaine)
_EXCLUDE_WHERE = {"Workshop_Recycle", "Workshop_Uncraftable", ""}


def _craft_index(sheets):
    """item_id -> liste de (recipe_id, [(in_item, qty)], out_qty, where)."""
    produced_by = {}
    for c in cdb_model._lines(sheets, "craft"):
        where = c.get("where", "")
        ins = [(i.get("item"), int(i.get("qty", 1) or 1)) for i in (c.get("inputs") or [])]
        for o in (c.get("outputs") or []):
            oq = int(o.get("qty", 1) or 1)
            produced_by.setdefault(o.get("item"), []).append((c.get("id"), ins, oq, where))
    return produced_by


def _candidates(recs):
    """Recettes de production normale (hors recyclage) ; sinon tout (fallback)."""
    norm = [r for r in recs if r[3] not in _EXCLUDE_WHERE]
    return norm or recs


def best_recipes(sheets, items):
    """Pour chaque item craftable, la recette de production qui MINIMISE le cout des entrees
    (compare minerai vs pepite, etc., hors recyclage). Cycle-safe. -> item -> (ins, out_qty)."""
    produced_by = _craft_index(sheets)
    price = lambda i: items.get(i, {}).get("price", 0) or 0
    memo, inprog = {}, set()

    def unit_cost(i):
        if i in memo:
            return memo[i]
        recs = produced_by.get(i)
        if not recs or i in inprog:
            return price(i)  # brut, ou cycle coupe
        inprog.add(i)
        best = min(sum(unit_cost(ii) * q for ii, q in ins) / (oq or 1) for _, ins, oq, _w in _candidates(recs))
        inprog.discard(i)
        memo[i] = best
        return best

    best = {}
    for i, recs in produced_by.items():
        chosen = min(_candidates(recs),
                     key=lambda r: sum((price(ii) if ii == i else unit_cost(ii)) * q for ii, q in r[1]) / (r[2] or 1))
        best[i] = (chosen[1], chosen[2])  # (ins, out_qty)
    return best


def craft_chain(sheets, items, product_id, max_depth=4, max_nodes=70):
    best = best_recipes(sheets, items)
    nm = lambda i: items.get(i, {}).get("name", i)
    pr = lambda i: items.get(i, {}).get("price", 0)
    nodes, edges, seen = {}, [], set()

    def add(i):
        kind = "product" if i == product_id else ("intermediate" if i in best else "raw")
        nodes[i] = {"label": nm(i), "title": f"{nm(i)} — {pr(i)}", "kind": kind}

    def rec(i, depth):
        if len(nodes) > max_nodes:
            return
        add(i)
        if i in seen or depth >= max_depth or i not in best:
            return
        seen.add(i)
        ins, _ = best[i]
        for ii, q in ins:
            edges.append((ii, i, f"x{q}"))
            rec(ii, depth + 1)

    rec(product_id, 0)
    return nodes, edges


def craft_tree_rows(sheets, items, product_id, max_depth=4, max_rows=250):
    """Nomenclature indentee (DFS) : lignes {depth,name,qty,price,station,craftable}."""
    best = best_recipes(sheets, items)
    stations = _item_station(sheets)
    nm = lambda i: items.get(i, {}).get("name", i)
    pr = lambda i: items.get(i, {}).get("price", 0)
    rows, seen = [], set()

    def rec(i, qty, depth):
        if len(rows) >= max_rows:
            return
        craftable = i in best
        rows.append({"depth": depth, "name": nm(i), "qty": qty, "price": pr(i),
                     "station": stations.get(i, "") if craftable else "", "craftable": craftable})
        if depth >= max_depth or i in seen or not craftable:
            return
        seen.add(i)
        ins, _ = best[i]
        for ii, q in ins:
            rec(ii, q, depth + 1)

    rec(product_id, 1, 0)
    return rows


def raw_materials(sheets, items, product_id, qty=1.0, max_depth=14):
    """Rollup : matieres BRUTES totales (voie la moins chere) pour `qty` du produit."""
    best = best_recipes(sheets, items)
    totals = {}

    def rec(i, need, path):
        if i not in best or i in path or len(path) > max_depth:
            totals[i] = totals.get(i, 0.0) + need
            return
        ins, oq = best[i]
        runs = need / (oq or 1)
        for ii, q in ins:
            rec(ii, q * runs, path | {i})

    rec(product_id, float(qty), frozenset())
    nm = lambda i: items.get(i, {}).get("name", i)
    pr = lambda i: items.get(i, {}).get("price", 0)
    out = [{"name": nm(i), "qty": round(q, 2), "price": pr(i), "cost": round(q * pr(i), 2)}
           for i, q in totals.items()]
    out.sort(key=lambda r: -r["cost"])
    return out


def _item_station(sheets):
    st = {}
    for c in cdb_model._lines(sheets, "craft"):
        for o in (c.get("outputs") or []):
            st.setdefault(o.get("item"), c.get("where", ""))
    return st


def craftable_products(sheets, items):
    out = set()
    for c in cdb_model._lines(sheets, "craft"):
        for o in (c.get("outputs") or []):
            out.add(o.get("item"))
    return sorted(out, key=lambda i: items.get(i, {}).get("name", i))


def universe_tree_rows(sheets, world=None, items=None):
    """Arborescence indentee Secteur -> Systeme -> Planete/Station/Instance."""
    sysn = {l["id"]: l.get("name", l["id"]) for l in cdb_model._lines(sheets, "system")}
    pln = {l["id"]: l.get("name", l["id"]) for l in cdb_model._lines(sheets, "planet")}
    insn = {l["id"]: l.get("name", l["id"]) for l in cdb_model._lines(sheets, "instance")}
    itname = lambda i: (items or {}).get(i, {}).get("name", i)
    rows = []
    for s in cdb_model._lines(sheets, "sector"):
        sid = s["id"]
        res = ""
        if world:
            names = sorted(itname(i) for i in world["sector_items"].get(sid, set()))
            if names:
                res = f"{len(names)} ressources : " + ", ".join(names[:12]) + (" …" if len(names) > 12 else "")
        ngen = (s.get("generation") or {}).get("maxSystem")
        extra = res or (f"~{ngen} systèmes générés" if ngen and not s.get("content") else "")
        rows.append({"depth": 0, "kind": "Secteur", "name": s.get("name", sid), "extra": extra})
        sys_children, direct = {}, []
        for c in (s.get("content") or []):
            sy, pl, ob, ins = c.get("system"), c.get("planet"), c.get("object"), c.get("instance")
            bucket = sys_children.setdefault(sy, []) if sy else direct
            if pl: bucket.append(("Planète", pln.get(pl, pl)))
            if ob: bucket.append(("Station", ob))
            if ins: bucket.append(("Instance", insn.get(ins, ins)))
        for sy, kids in sys_children.items():
            rows.append({"depth": 1, "kind": "Système", "name": sysn.get(sy, sy), "extra": ""})
            for kind, name in kids:
                rows.append({"depth": 2, "kind": kind, "name": name, "extra": ""})
        for kind, name in direct:
            rows.append({"depth": 1, "kind": kind, "name": name, "extra": ""})
    return rows


def universe_graph(sheets, world=None, items=None, res_label="Ressources"):
    sysn = {l["id"]: l.get("name", l["id"]) for l in cdb_model._lines(sheets, "system")}
    pln = {l["id"]: l.get("name", l["id"]) for l in cdb_model._lines(sheets, "planet")}
    insn = {l["id"]: l.get("name", l["id"]) for l in cdb_model._lines(sheets, "instance")}
    itname = lambda i: (items or {}).get(i, {}).get("name", i)
    nodes, edges, eset = {}, [], set()

    def add(i, label, kind):
        nodes[i] = {"label": label or i, "title": f"{label or i} ({kind})", "kind": kind}

    def edge(a, b):
        if a != b and (a, b) not in eset:
            eset.add((a, b)); edges.append((a, b, ""))

    for s in cdb_model._lines(sheets, "sector"):
        sid = s["id"]
        ngen = (s.get("generation") or {}).get("maxSystem")
        lbl = s.get("name", sid)
        if not s.get("content"):
            lbl = f"{lbl} (~{ngen} sys. générés)" if ngen else lbl
        title = s.get("name", sid)
        if world:
            names = sorted(itname(i) for i in world["sector_items"].get(sid, set()))
            if names:
                shown = ", ".join(names[:20]) + (f" (+{len(names) - 20})" if len(names) > 20 else "")
                title = f"{title} — {len(names)} {res_label}: {shown}"
        nodes[sid] = {"label": lbl, "title": title, "kind": "sector"}
        for c in (s.get("content") or []):
            sy, pl, ob, ins = c.get("system"), c.get("planet"), c.get("object"), c.get("instance")
            parent = sid
            if sy:
                add(sy, sysn.get(sy, sy), "system"); edge(sid, sy); parent = sy
            if pl:
                add(pl, pln.get(pl, pl), "planet"); edge(parent, pl)
            if ob:
                add(ob, ob, "object"); edge(parent, ob)
            if ins:
                add(ins, insn.get(ins, ins), "instance"); edge(parent, ins)
    return nodes, edges


def to_html(nodes, edges, height="640px", hierarchical=False, direction="UD"):
    """direction : 'UD' = racine en haut (univers) ; 'DU' = puits en haut (craft : produit final)."""
    from pyvis.network import Network
    net = Network(height=height, width="100%", directed=True, bgcolor="#0e1117", font_color="#eee")
    if hierarchical:
        net.set_options('{"layout":{"hierarchical":{"enabled":true,"direction":"%s","sortMethod":"directed","levelSeparation":110,"nodeSpacing":150,"treeSpacing":200}},"physics":{"enabled":false}}' % direction)
    else:
        net.barnes_hut(gravity=-12000, spring_length=120)
    for nid, d in nodes.items():
        net.add_node(nid, label=d["label"], title=d.get("title", d["label"]),
                     color=_COLORS.get(d["kind"], "#888"), shape="dot", size=16)
    for a, b, lbl in edges:
        if a in nodes and b in nodes:
            net.add_edge(a, b, label=lbl, color="#555")
    return net.generate_html(notebook=False)
