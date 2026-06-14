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
SELECT = "region,system,planet,resource,author,created_at"


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


def _base():
    return _cfg().get("url", "").rstrip("/") + f"/rest/v1/{TABLE}"


def fetch_all():
    import requests
    r = requests.get(_base(), headers=_headers(),
                     params={"select": SELECT, "order": "created_at"}, timeout=15)
    r.raise_for_status()
    return r.json()


def add(region, system, planet, resources, author):
    """Insere une decouverte. Si pas de ressource, enregistre quand meme la planete (resource=None)."""
    import requests
    author = (author or "anon").strip() or "anon"
    res = [x for x in (resources or []) if x]
    rows = ([{"region": region, "system": system, "planet": planet, "resource": x, "author": author} for x in res]
            if res else [{"region": region, "system": system, "planet": planet, "resource": None, "author": author}])
    h = _headers(); h["Prefer"] = "return=minimal"
    r = requests.post(_base(), headers=h, json=rows, timeout=15)
    r.raise_for_status()


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
    h = _headers(); h["Prefer"] = "return=minimal"
    r = requests.patch(_base(), headers=h, params=params, json=changes, timeout=15)
    r.raise_for_status()
