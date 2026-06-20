# -*- coding: utf-8 -*-
"""Stockage COMMUNAUTAIRE des decouvertes via Supabase (PostgREST REST API).

L'univers de SpaceCraft est partage entre joueurs -> carte mutualisee.
Modele append-only : 1 ligne = (region, systeme, planete, ressource, auteur). Les inserts
ne s'ecrasent jamais -> aucun conflit d'ecriture concurrente. La hierarchie est reconstruite
a la lecture (discoveries.from_flat).

Config via st.secrets['supabase'] = { url = "...", key = "<anon key>" }.
Si absent -> available() == False -> l'app retombe sur le mode LOCAL (discoveries.py).
"""
import streamlit as st

TABLE = "discoveries"
BANS = "bans"
# "*" = robuste : marche meme si la colonne author_id n'existe pas encore (avant l'ALTER TABLE)
SELECT = "*"


def _cfg():
    try:
        return dict(st.secrets["supabase"])
    except Exception:
        return {}


def available():
    c = _cfg()
    return bool(c.get("url") and c.get("key"))


def _headers():
    key = _cfg().get("key", "")
    return {"apikey": key, "Authorization": f"Bearer {key}", "Content-Type": "application/json"}


def _rest(table):
    return _cfg().get("url", "").rstrip("/") + f"/rest/v1/{table}"


def _base():
    return _rest(TABLE)


def fetch_all():
    """Recupere TOUTES les lignes en paginant : PostgREST plafonne chaque reponse a ~1000
    lignes (max-rows serveur). Sans pagination, l'app ne verrait que les 1000 premieres
    decouvertes (depuis l'import Haronex la base depasse 17 000 lignes)."""
    import requests
    out, step, offset = [], 1000, 0
    while True:
        r = requests.get(_base(), headers=_headers(),
                         params={"select": SELECT, "order": "created_at",
                                 "limit": step, "offset": offset}, timeout=30)
        r.raise_for_status()
        batch = r.json()
        out.extend(batch)
        if len(batch) < step:
            return out
        offset += step


def add(region, system, planet, resources, author, author_id=None):
    """Insere une decouverte (avec le SteamID auteur). Si pas de ressource, enregistre quand meme
    la planete (resource=None). Tolere l'absence de la colonne author_id (reessaye sans)."""
    import requests
    author = (author or "anon").strip() or "anon"
    res = [x for x in (resources or []) if x]
    base = {"region": region, "system": system, "planet": planet, "author": author, "author_id": author_id}
    rows = [dict(base, resource=x) for x in res] if res else [dict(base, resource=None)]
    h = _headers(); h["Prefer"] = "return=minimal"
    r = requests.post(_base(), headers=h, json=rows, timeout=15)
    if r.status_code >= 400:  # ex : colonne author_id pas encore creee -> reessaye sans
        for row in rows:
            row.pop("author_id", None)
        r = requests.post(_base(), headers=h, json=rows, timeout=15)
    r.raise_for_status()


# --- bannissements (table `bans`) ---

def fetch_bans():
    import requests
    r = requests.get(_rest(BANS), headers=_headers(),
                     params={"select": "*", "order": "created_at"}, timeout=15)
    r.raise_for_status()
    return r.json()


def ban(author_id, name):
    import requests
    h = _headers(); h["Prefer"] = "resolution=merge-duplicates,return=minimal"
    r = requests.post(_rest(BANS), headers=h,
                      json=[{"author_id": author_id, "name": name}], timeout=15)
    r.raise_for_status()


def unban(author_id):
    import requests
    r = requests.delete(_rest(BANS), headers=_headers(),
                        params={"author_id": f"eq.{author_id}"}, timeout=15)
    r.raise_for_status()


def delete_by_author(author_id):
    """Supprime toutes les contributions d'un auteur (par SteamID)."""
    delete_where(author_id=author_id)


def delete_planet(region, system, planet, author):
    """Supprime les lignes de CET auteur pour cette planete (chacun gere ses propres entrees)."""
    delete_where(region=region, system=system, planet=planet, author=author)


def delete_where(**filters):
    """Suppression ADMIN : supprime toutes les lignes correspondant aux filtres (sans contrainte
    d'auteur). Au moins un filtre requis (PostgREST refuse un DELETE sans filtre)."""
    import requests
    if not filters:
        raise ValueError("delete_where requiert au moins un filtre")
    params = {k: f"eq.{v}" for k, v in filters.items()}
    r = requests.delete(_base(), headers=_headers(), params=params, timeout=15)
    r.raise_for_status()


def update_where(filters, changes):
    """Édition ADMIN : met à jour (PATCH) les lignes correspondant aux filtres. Sert à RENOMMER
    une région/système/planète (ex {'region':X,'system':Y} -> {'system':'NouveauNom'}).
    Nécessite une policy UPDATE côté Supabase. Au moins un filtre requis."""
    import requests
    if not filters or not changes:
        raise ValueError("update_where requiert des filtres et des changements")
    params = {k: f"eq.{v}" for k, v in filters.items()}
    h = _headers(); h["Prefer"] = "return=representation"  # renvoie les lignes -> on peut compter
    r = requests.patch(_base(), headers=h, params=params, json=changes, timeout=15)
    r.raise_for_status()
    try:
        return len(r.json())  # nb de lignes modifiees (0 = policy UPDATE manquante ou cible introuvable)
    except Exception:
        return 0
