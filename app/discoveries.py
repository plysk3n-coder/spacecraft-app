# -*- coding: utf-8 -*-
"""Journal de decouvertes du joueur : Region -> Systeme -> Planete -> ressources.

Le monde de SpaceCraft est genere proceduralement (seed serveur) -> ces infos ne sont
PAS dans data.cdb : le joueur les saisit au fur et a mesure qu'il explore.

Stocke en JSON LOCAL a la racine du projet (my_discoveries.json), HORS de app/ et de
extracted/ -> NON copie par sync_deploy.ps1 -> reste prive, jamais pousse sur le repo public.
"""
import io, json, os

STORE = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "my_discoveries.json")


def empty():
    return {"regions": {}}


def load(path=STORE):
    if not os.path.exists(path):
        return empty()
    try:
        with io.open(path, "r", encoding="utf-8") as f:
            d = json.load(f)
    except Exception:
        return empty()
    if not isinstance(d, dict):
        return empty()
    d.setdefault("regions", {})
    return d


def save(data, path=STORE):
    with io.open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)


def add_system(data, region, system):
    r = data["regions"].setdefault(region, {"systems": {}})
    r["systems"].setdefault(system, {"planets": {}})


def add_planet(data, region, system, planet):
    add_system(data, region, system)
    data["regions"][region]["systems"][system]["planets"].setdefault(planet, {"resources": []})


def add_resources(data, region, system, planet, resources):
    """Ajoute (sans doublon) une liste d'item-ids de ressources a une planete. Cree la
    hierarchie au besoin. Renvoie le nb de ressources reellement ajoutees."""
    add_planet(data, region, system, planet)
    pl = data["regions"][region]["systems"][system]["planets"][planet]["resources"]
    n = 0
    for r in resources:
        if r and r not in pl:
            pl.append(r); n += 1
    return n


def remove_planet(data, region, system, planet):
    try:
        del data["regions"][region]["systems"][system]["planets"][planet]
    except KeyError:
        pass


def from_flat(flat):
    """Construit l'arbre {regions:...} a partir de lignes plates
    (region, system, planet, resource) — ex. depuis la base communautaire Supabase."""
    data = empty()
    for r in flat or []:
        rg, sy, pl, res = r.get("region"), r.get("system"), r.get("planet"), r.get("resource")
        if not (rg and sy and pl):
            continue
        add_planet(data, rg, sy, pl)
        if res:
            add_resources(data, rg, sy, pl, [res])
    return data


def rows(data):
    """Lignes a plat pour affichage en arbre : {depth, kind, name, resources}."""
    out = []
    for rg, rgd in data.get("regions", {}).items():
        out.append({"depth": 0, "kind": "region", "name": rg, "resources": []})
        for sy, syd in rgd.get("systems", {}).items():
            out.append({"depth": 1, "kind": "system", "name": sy, "resources": []})
            for pl, pld in syd.get("planets", {}).items():
                out.append({"depth": 2, "kind": "planet", "name": pl,
                            "resources": pld.get("resources", [])})
    return out


def all_resource_ids(data):
    seen = set()
    for rgd in data.get("regions", {}).values():
        for syd in rgd.get("systems", {}).values():
            for pld in syd.get("planets", {}).values():
                seen.update(pld.get("resources", []))
    return seen


def abundance_map(flat):
    """Index {(region, system, planete, resource): {density, count, source_type, body_type}}
    construit depuis les lignes plates communautaires. Les colonnes density/count/source_type/
    body_type ont ete ajoutees lors de l'import du quadrant Haronex (spacecraft.tools) ; absentes
    des saisies manuelles plus anciennes -> valeurs None tolerees."""
    idx = {}
    for r in flat or []:
        rg, sy, pl, res = r.get("region"), r.get("system"), r.get("planet"), r.get("resource")
        if not (rg and sy and pl and res):
            continue
        idx[(rg, sy, pl, res)] = {
            "density": r.get("density"), "count": r.get("count"),
            "source_type": r.get("source_type"), "body_type": r.get("body_type"),
        }
    return idx


def find_resource(data, res_id):
    """Liste des (region, systeme, planete) ou cette ressource a ete trouvee."""
    hits = []
    for rg, rgd in data.get("regions", {}).items():
        for sy, syd in rgd.get("systems", {}).items():
            for pl, pld in syd.get("planets", {}).items():
                if res_id in pld.get("resources", []):
                    hits.append((rg, sy, pl))
    return hits
