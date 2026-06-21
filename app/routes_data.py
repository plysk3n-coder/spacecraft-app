# -*- coding: utf-8 -*-
"""Routes FTL du quadrant Haronex (scrape spacecraft.tools, `connectionEdges`). Graphe des systèmes.
Données : app/haronex_routes.json = {systems:{id:{name,sector,x,y}}, edges:[[src,dst,cost], ...]}.
Le graphe est traité comme NON orienté (on peut sauter dans les deux sens)."""
import json, io, os, heapq

DATA = os.path.join(os.path.dirname(os.path.abspath(__file__)), "haronex_routes.json")


def load():
    with io.open(DATA, encoding="utf-8") as f:
        return json.load(f)


def adjacency(data):
    """{system_id: {voisin_id: coût}} symétrique (coût min si doublon)."""
    adj = {}
    for s, d, c in data["edges"]:
        adj.setdefault(s, {})[d] = min(c, adj.get(s, {}).get(d, c))
        adj.setdefault(d, {})[s] = min(c, adj.get(d, {}).get(s, c))
    return adj


def name_to_id(data):
    return {v["name"]: k for k, v in data["systems"].items()}


def neighbors(data, sys_id):
    """Voisins DIRECTS [(id, coût)] triés par coût croissant."""
    return sorted(adjacency(data).get(sys_id, {}).items(), key=lambda x: x[1])


def shortest_path(data, src, dst, adj=None):
    """Chemin FTL le moins coûteux de src à dst (Dijkstra + reconstruction).
    -> {path:[sid...], cost, hops} ou None si non atteignable."""
    adj = adj or adjacency(data)
    if src == dst:
        return {"path": [src], "cost": 0, "hops": 0}
    INF = float("inf")
    dist = {src: 0}
    hops = {src: 0}
    prev = {}
    pq = [(0, 0, src)]
    while pq:
        c, h, u = heapq.heappop(pq)
        if u == dst:
            break
        if c > dist.get(u, INF):
            continue
        for v, w in adj.get(u, {}).items():
            nc = c + w
            if nc < dist.get(v, INF):
                dist[v] = nc
                hops[v] = h + 1
                prev[v] = u
                heapq.heappush(pq, (nc, h + 1, v))
    if dst not in dist:
        return None
    path = [dst]
    while path[-1] != src:
        path.append(prev[path[-1]])
    path.reverse()
    return {"path": path, "cost": dist[dst], "hops": hops[dst]}


def nearest_with(data, src, target_ids, adj=None):
    """Parmi target_ids (systèmes ayant la ressource cherchée), celui le moins coûteux
    à atteindre depuis src + le chemin pour y aller. -> {path, cost, hops, target} ou None."""
    adj = adj or adjacency(data)
    costs = costs_from(data, src, adj)
    best = None
    for sid in target_ids:
        c = costs.get(sid)
        if c is not None and (best is None or c < best[1]):
            best = (sid, c)
    if best is None:
        return None
    sp = shortest_path(data, src, best[0], adj)
    if sp:
        sp["target"] = best[0]
    return sp


def costs_from(data, sys_id, adj=None):
    """Dijkstra : coût FTL minimal de `sys_id` vers tous les systèmes atteignables.
    -> {system_id: (coût_total, nb_sauts)}."""
    adj = adj or adjacency(data)
    INF = float("inf")
    dist = {sys_id: (0, 0)}
    pq = [(0, 0, sys_id)]
    while pq:
        c, h, u = heapq.heappop(pq)
        if c > dist.get(u, (INF,))[0]:
            continue
        for v, w in adj.get(u, {}).items():
            nc = c + w
            if nc < dist.get(v, (INF,))[0]:
                dist[v] = (nc, h + 1)
                heapq.heappush(pq, (nc, h + 1, v))
    return dist
