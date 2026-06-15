# -*- coding: utf-8 -*-
"""Arbre de permits / licences (tech tree).

La table `permit` du cdb = 107 permits nommés avec position (pos_x/pos_y = layout du jeu),
`cost` (en License Points), `requires` (prérequis) et `unlocks` (crafts/items/attributs débloqués).
On reconstruit l'arbre + un résolveur « quel permit débloque l'item X et à quel coût total ».
"""
import cdb_model


def build_tree(sheets, items, permit_tr=None):
    """-> (nodes, edges, item_to_permit).
    nodes[pid] = {name, cost, x, y, requires:[pid], unlocks:[noms], unlock_ids:[item ids]}.
    edges = [(prereq_pid, pid)]. item_to_permit = {item_id: pid qui le débloque}."""
    permit_tr = permit_tr or {}
    # craft id -> item produit (pour traduire ce qu'un permit débloque)
    craft_out = {}
    for c in cdb_model._lines(sheets, "craft"):
        outs = c.get("outputs") or []
        if outs:
            craft_out[c.get("id")] = outs[0].get("item")
    iname = lambda i: items.get(i, {}).get("name", i)

    nodes, edges, item_to_permit = {}, [], {}
    for p in cdb_model._lines(sheets, "permit"):
        if not p.get("name") or p.get("pos_x") is None:
            continue  # ignore Locked/Deprecated/non positionnés
        pid = p["id"]
        unl = p.get("unlocks") or {}
        names, ids = [], []
        for cu in unl.get("craft", []):
            oi = craft_out.get(cu.get("craft"), cu.get("craft"))
            if oi:
                ids.append(oi); names.append(iname(oi))
        for iu in unl.get("item", []):
            ii = iu.get("item")
            if ii:
                ids.append(ii); names.append(iname(ii))
        reqs = [r.get("permit") for r in (p.get("requires") or []) if r.get("permit")]
        nodes[pid] = {"name": permit_tr.get(pid) or p.get("name"), "cost": p.get("cost", 0) or 0,
                      "x": p.get("pos_x") or 0, "y": p.get("pos_y") or 0,
                      "requires": reqs, "unlocks": names, "unlock_ids": ids,
                      "family": "corpo" if pid.startswith("PCorpo") else "tech"}
        for ii in ids:
            item_to_permit.setdefault(ii, pid)
    # edges seulement vers des permits existants
    for pid, d in nodes.items():
        for r in d["requires"]:
            if r in nodes:
                edges.append((r, pid))
    return nodes, edges, item_to_permit


def unlock_cost(nodes, item_to_permit, item_id):
    """Permit qui débloque item_id + toute la chaîne de prérequis + coût total (License Points)."""
    pid = item_to_permit.get(item_id)
    if not pid or pid not in nodes:
        return None
    seen, stack = set(), [pid]
    while stack:
        x = stack.pop()
        if x in seen or x not in nodes:
            continue
        seen.add(x)
        stack += nodes[x]["requires"]
    total = sum(nodes[p]["cost"] for p in seen)
    chain = sorted(seen, key=lambda p: (nodes[p]["x"], nodes[p]["cost"]))
    return {"permit": pid, "chain": chain, "total": total}


def permit_html(nodes, edges, highlight=None, height="660px"):
    """Rend l'arbre via pyvis, positions x/y du jeu (physique off). highlight = set de pid à surligner."""
    from pyvis.network import Network
    highlight = highlight or set()
    net = Network(height=height, width="100%", directed=True, bgcolor="#0e1117", font_color="#eee")
    net.toggle_physics(False)
    for pid, d in nodes.items():
        if pid in highlight:
            color = "#e8542f"
        elif d["cost"] == 0:
            color = "#1a9850"
        else:
            color = "#3a6ea5"
        title = f"{d['name']} — {d['cost']} PL"
        if d["unlocks"]:
            extra = ", ".join(d["unlocks"][:14]) + (" …" if len(d["unlocks"]) > 14 else "")
            title += f" | débloque : {extra}"
        net.add_node(pid, label=f"{d['name']}\n{d['cost']} PL", title=title,
                     x=float(d["x"]) * 190, y=float(d["y"]) * 115, physics=False,
                     color=color, shape="box", font={"size": 13})
    for a, b in edges:
        if a in nodes and b in nodes:
            both = a in highlight and b in highlight
            net.add_edge(a, b, color="#e8542f" if both else "#555", width=3 if both else 1)
    return net.generate_html(notebook=False)
