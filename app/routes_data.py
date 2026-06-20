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
