# -*- coding: utf-8 -*-
"""Connexion « Sign in through Steam » (OpenID 2.0).

Steam ne donne ni email ni mot de passe : il renvoie un SteamID64 verifie. On s'en sert
comme identite/signature pour gater l'ECRITURE de la carte communautaire (la lecture reste
ouverte). Le pseudo Steam est recupere via l'API Web Steam si une cle est fournie.

Config via st.secrets['steam'] = { return_url = "https://ton-app.streamlit.app/",
                                    realm = "<optionnel, defaut = return_url>",
                                    api_key = "<optionnel, cle API Steam pour le pseudo>" }
Si return_url absent -> configured() == False -> l'app retombe sur le champ pseudo libre.

NB : la connexion est valable le temps de la SESSION (un rafraichissement complet de la page
deconnecte ; il suffit de se reconnecter, Steam s'en souvient).
"""
import base64
import hashlib
import hmac
import json
import re
import time
import urllib.parse
import streamlit as st

LOGIN = "https://steamcommunity.com/openid/login"
NS = "http://specs.openid.net/auth/2.0"
TOKEN_TTL = 30 * 24 * 3600  # 30 jours


def _cfg():
    try:
        return dict(st.secrets["steam"])
    except Exception:
        return {}


def configured():
    return bool(_cfg().get("return_url"))


def login_url():
    ret = _cfg().get("return_url", "")
    realm = _cfg().get("realm") or ret
    params = {
        "openid.ns": NS,
        "openid.mode": "checkid_setup",
        "openid.return_to": ret,
        "openid.realm": realm,
        "openid.identity": "http://specs.openid.net/auth/2.0/identifier_select",
        "openid.claimed_id": "http://specs.openid.net/auth/2.0/identifier_select",
    }
    return LOGIN + "?" + urllib.parse.urlencode(params)


def _verify(params):
    """Re-soumet les parametres openid.* a Steam (mode check_authentication).
    Renvoie le SteamID64 si la signature est valide, sinon None."""
    import requests
    data = dict(params)
    data["openid.mode"] = "check_authentication"
    try:
        r = requests.post(LOGIN, data=data, timeout=15)
    except Exception:
        return None
    if "is_valid:true" not in r.text:
        return None
    m = re.search(r"/openid/id/(\d+)$", params.get("openid.claimed_id", ""))
    return m.group(1) if m else None


def _steam_name(steamid):
    """Pseudo Steam via l'API Web (si cle fournie), sinon le SteamID."""
    key = _cfg().get("api_key")
    if not key:
        return steamid
    try:
        import requests
        r = requests.get("https://api.steampowered.com/ISteamUser/GetPlayerSummaries/v2/",
                         params={"key": key, "steamids": steamid}, timeout=15)
        players = r.json().get("response", {}).get("players", [])
        return players[0].get("personaname") or steamid if players else steamid
    except Exception:
        return steamid


def current_user():
    """{'id', 'name'} si connecte, sinon None. Traite le retour OpenID present dans l'URL."""
    if st.session_state.get("steam_user"):
        return st.session_state["steam_user"]
    qp = st.query_params
    if qp.get("openid.mode") == "id_res":
        params = {k: qp[k] for k in qp.keys() if k.startswith("openid.")}
        sid = _verify(params)
        if sid:
            user = {"id": sid, "name": _steam_name(sid)}
            st.session_state["steam_user"] = user
            # ne nettoie QUE les parametres openid.* (garde les autres, ex region/system)
            for k in [k for k in list(qp.keys()) if k.startswith("openid.")]:
                try:
                    del qp[k]
                except Exception:
                    pass
            return user
    return None


def logout():
    st.session_state.pop("steam_user", None)


# --- jeton signe pour persister la connexion dans un cookie (resiste au F5) ---

def _secret():
    c = _cfg()
    return (c.get("cookie_secret") or c.get("api_key") or "spacecraft-default").encode()


def make_token(user):
    payload = {"id": user["id"], "name": user["name"], "exp": int(time.time()) + TOKEN_TTL}
    raw = base64.urlsafe_b64encode(json.dumps(payload).encode()).decode()
    sig = hmac.new(_secret(), raw.encode(), hashlib.sha256).hexdigest()
    return f"{raw}.{sig}"


def parse_token(token):
    """Renvoie {'id','name'} si le jeton est valide et non expire, sinon None."""
    try:
        raw, sig = token.split(".", 1)
        good = hmac.new(_secret(), raw.encode(), hashlib.sha256).hexdigest()
        if not hmac.compare_digest(sig, good):
            return None
        data = json.loads(base64.urlsafe_b64decode(raw.encode()))
        if data.get("exp", 0) < int(time.time()):
            return None
        return {"id": data["id"], "name": data["name"]}
    except Exception:
        return None
