# -*- coding: utf-8 -*-
import os, sys, json, datetime
import pandas as pd
import streamlit as st
import extra_streamlit_components as stx

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import streamlit.components.v1 as components
import cdb_model
import extract_cdb
import i18n
import graph_data
import build_data
import permit_data
import contract_data
import world_data
import discoveries
import cloud_store
import steam_auth
import market_data
import routes_data

st.set_page_config(page_title="SpaceCraft - Rentabilite", page_icon="🚀", layout="wide",
                   initial_sidebar_state="collapsed")
# Masque entierement la barre laterale (langue -> drapeaux en haut ; parametres -> expander)
st.markdown(
    "<style>[data-testid='stSidebar'],[data-testid='stSidebarCollapsedControl']{display:none!important;}</style>",
    unsafe_allow_html=True)


@st.cache_data(show_spinner=False)
def load_sheets():
    return cdb_model.load_cdb()


@st.cache_data(show_spinner=False)
def load_world(_schema_v=5):  # _schema_v : bump pour invalider le cache quand world_data change
    return world_data.build_world(cdb_model.load_cdb())


@st.cache_data(show_spinner=False)
def load_market():
    return market_data.sell_index(cdb_model.load_cdb())


@st.cache_data(show_spinner=False)
def load_routes():
    return routes_data.load()


@st.cache_data(show_spinner=False)
def load_res_icons():
    p = os.path.join(os.path.dirname(os.path.abspath(__file__)), "res_icons.json")
    try:
        with open(p, encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return {}


@st.cache_data(show_spinner=False)
def load_ore2ingot():
    """item-minerai -> [lingots] qu'on peut en faire (recettes dont un output contient 'Ingot')."""
    o2i = {}
    for c in cdb_model._lines(cdb_model.load_cdb(), "craft"):
        ings = [o.get("item") for o in (c.get("outputs") or []) if (o.get("item") or "").find("Ingot") >= 0]
        if ings:
            for inp in (c.get("inputs") or []):
                if inp.get("item"):
                    o2i.setdefault(inp["item"], set()).update(ings)
    return {k: sorted(v) for k, v in o2i.items()}


@st.cache_data(show_spinner=False)
def load(overrides_key, lang):
    sheets = cdb_model.load_cdb()
    tr = i18n.load_translations(lang)
    items, recipes = cdb_model.build(sheets, price_overrides=dict(overrides_key), tr=tr)
    return items, recipes


# ttl long : le cache est déjà vidé manuellement à chaque écriture (fetch_shared.clear()),
# donc un contributeur voit toujours ses ajouts ; pas besoin de re-fetch toutes les 20 s.
@st.cache_data(ttl=300, show_spinner=False)
def fetch_shared():
    return cloud_store.fetch_all()


@st.cache_data(ttl=20, show_spinner=False)
def fetch_bans_cached():
    try:
        return cloud_store.fetch_bans()
    except Exception:
        return []  # table `bans` pas encore créée -> aucun banni


@st.cache_data(show_spinner=False)
def res_translations(lang):
    return i18n.load_translations(lang).get("resource", {})


@st.cache_data(show_spinner=False)
def sheet_translations(lang, sheet):
    return i18n.load_translations(lang).get(sheet, {})


# --- langue : drapeaux cliquables en haut de page ---
_langs = i18n.available_langs()
if st.session_state.get("lang") not in _langs:
    st.session_state.lang = "fr" if "fr" in _langs else _langs[0]
lang = st.session_state.lang
T = lambda k: i18n.t(k, lang)

_FLAGS = {"fr": "🇫🇷", "en": "🇬🇧"}
_fcols = st.columns([1] * len(_langs) + [16])
for _i, _code in enumerate(_langs):
    if _fcols[_i].button(_FLAGS.get(_code, _code), key=f"flag_{_code}",
                         help=i18n.LANGS.get(_code, _code),
                         type="primary" if _code == lang else "secondary"):
        st.session_state.lang = _code
        st.rerun()

st.title(T("title"))
st.caption(T("caption"))

# --- connexion Steam : persistee via cookie signe (resiste au F5) ---
AUTH_COOKIE = "sc_auth"
cookies = stx.CookieManager(key="sc_cookies")
if steam_auth.configured():
    steam_auth.current_user()  # traite le retour OpenID -> session
    _user = st.session_state.get("steam_user")
    if _user:
        # connecte : s'assurer que le cookie reflete bien l'identite
        _tok = steam_auth.make_token(_user)
        if cookies.get(AUTH_COOKIE) != _tok:
            cookies.set(AUTH_COOKIE, _tok,
                        expires_at=datetime.datetime.now() + datetime.timedelta(days=30))
    else:
        # pas en session : tenter de restaurer depuis le cookie
        _restored = steam_auth.parse_token(cookies.get(AUTH_COOKIE) or "")
        if _restored:
            st.session_state["steam_user"] = _restored

# --- parametres (ADMIN uniquement) : re-extraction + ajuster un prix ---
if steam_auth.is_admin(st.session_state.get("steam_user")):
    with st.expander("⚙️ " + T("settings"), expanded=False):
        if extract_cdb.game_available():
            if st.button(T("reextract"), help=T("reextract_help")):
                try:
                    extract_cdb.extract_all(langs=("fr",))  # sauvegarde auto en .prev avant d'écraser
                    _diff = extract_cdb.diff_cdb()
                    st.cache_data.clear()
                    st.success(T("reextracted"))
                    if _diff:
                        st.info(T("reextract_diff").format(
                            ia=len(_diff["items_added"]), ir=len(_diff["items_removed"]),
                            pc=len(_diff["price_changes"]),
                            ca=len(_diff["craft_added"]), cr=len(_diff["craft_removed"])))
                        if _diff["items_added"]:
                            st.caption("➕ " + ", ".join(_diff["items_added"][:30]))
                        if _diff["items_removed"]:
                            st.caption("➖ " + ", ".join(_diff["items_removed"][:30]))
                        if _diff["price_changes"]:
                            st.dataframe(pd.DataFrame([{"id": i, "ancien": o, "nouveau": n}
                                                       for i, o, n in _diff["price_changes"][:50]]),
                                         hide_index=True, width="stretch")
                except Exception as e:
                    st.error(f'{T("fail")} {e}')

        st.divider()
        st.subheader(T("adjust_price"))
        st.caption(T("adjust_help"))
        if "overrides" not in st.session_state:
            st.session_state.overrides = {}
        sheets0 = cdb_model.load_cdb()
        items0, _ = cdb_model.build(sheets0, tr=i18n.load_translations(lang))
        names = sorted(items0.keys(), key=lambda i: items0[i]["name"])
        label = {i: f'{items0[i]["name"]} ({items0[i]["price"]})' for i in names}
        sel = st.selectbox(T("item"), ["—"] + names, format_func=lambda i: "—" if i == "—" else label[i])
        if sel != "—":
            newp = st.number_input(f'{T("new_price")} {items0[sel]["name"]}', value=float(items0[sel]["price"]), step=0.01)
            c1, c2 = st.columns(2)
            if c1.button(T("apply")):
                st.session_state.overrides[sel] = newp
            if c2.button(T("reset_all")):
                st.session_state.overrides = {}
        if st.session_state.overrides:
            st.write(T("modified"))
            for i, p in st.session_state.overrides.items():
                st.write(f"- {items0[i]['name']} → {p}")

overrides_key = tuple(sorted(st.session_state.get("overrides", {}).items()))
items, recipes = load(overrides_key, lang)
df = pd.DataFrame(recipes)
# temps de craft auto par produit (recette de BASE en priorité) pour le plan d'usine.
# Indexé sur TOUTES les sorties (pas seulement la principale) -> les sous-produits (Calcite,
# MalachiteStone, QuartzShavings…) sont dimensionnables eux aussi (M3 cause b).
_product_time = {}
def _index_pt(only_base):
    for _r in recipes:
        if only_base and _r.get("unlock") != "Permit":
            continue
        for _oid, _oq in _r.get("all_outputs") or [(_r["product_id"], _r.get("out_qty") or 1)]:
            _product_time.setdefault(_oid, (_r.get("t_auto") or 0, _oq or 1, _r.get("station") or "", _r.get("power") or 0))
_index_pt(True)   # recettes de base d'abord
_index_pt(False)  # fallback : produits sans recette de base

# --- données partagées entre onglets : gisements + carte de découvertes ---
_world0 = load_world()
deposits = _world0.get("deposits", {})
_rtr = res_translations(lang)
# nom anglais de base (champ `name` du cdb) : sert de repli quand la trad de la langue manque
# (cas EN : nos fichiers i18n n'ont pas les noms de ressources -> on prend l'anglais du jeu, pas l'id brut)
_res_name = {l["id"]: l.get("name") for l in cdb_model._lines(load_sheets(), "resource")}
dep_name = lambda d: _rtr.get(d) or _res_name.get(d) or deposits.get(d, {}).get("name", d)
# nom d'affichage : ressource traduite (langue) ; sinon nom anglais du cdb ; sinon item (compat) ; sinon id brut
resname = lambda x: _rtr.get(x) or _res_name.get(x) or items.get(x, {}).get("name", x)
# type de gisement (enum RESTYPE de world_data, en anglais) -> libellé traduit (termes génériques)
_RESTYPE_TR = {
    "Default": {"fr": "Standard", "en": "Default"}, "Gravite": {"fr": "Gravite", "en": "Gravite"},
    "Node": {"fr": "Nodule", "en": "Node"}, "Deposit": {"fr": "Gisement", "en": "Deposit"},
    "Shell": {"fr": "Coquille", "en": "Shell"}, "Geyser": {"fr": "Geyser", "en": "Geyser"},
    "Pool": {"fr": "Bassin", "en": "Pool"}, "Biological": {"fr": "Biologique", "en": "Biological"},
    "BiologicalRoot": {"fr": "Racine biologique", "en": "Biological root"},
}
restype_label = lambda t: _RESTYPE_TR.get(t, {}).get(lang, t)
# type de déblocage d'une recette (unlockType du cdb) -> libellé traduit
_UNLOCK_TR = {0: {"fr": "Base", "en": "Base"}, 1: {"fr": "Blueprint unique", "en": "Unique blueprint"},
              2: {"fr": "Blueprint aléatoire", "en": "Random blueprint"}, 4: {"fr": "Étude", "en": "Study"}}
unlock_label = lambda u: _UNLOCK_TR.get(u, {}).get(lang, str(u))
# options du multiselect = toutes les ressources minables (pas seulement les 70 avec items),
# dedoublonnees par nom traduit (on garde l'id avec items, sinon le plus court -> evite les variantes _Big)
_rec_ids = set(deposits) | set(_world0.get("minable", []))
def _better(a, b):
    ai, bi = a in deposits, b in deposits
    return ai if ai != bi else (len(a) < len(b))
_by_nm = {}
for _d in _rec_ids:
    _nm = dep_name(_d)
    if cdb_model.is_placeholder(_nm):
        continue
    if _nm not in _by_nm or _better(_d, _by_nm[_nm]):
        _by_nm[_nm] = _d
dep_ids = sorted(_by_nm.values(), key=dep_name)
# ce que produit un gisement (noms d'items traduits)
dep_yield = lambda d: [items.get(i, {}).get("name", i) for i in deposits.get(d, {}).get("items", [])]

# --- POI / bases (table `instance`) : stockes en base avec le prefixe "POI:" ---
_poitr = sheet_translations(lang, "instance")
_poi_name = {l["id"]: l.get("name") for l in cdb_model._lines(load_sheets(), "instance")}
is_poi = lambda x: isinstance(x, str) and x.startswith("POI:")
# POI traduit (langue) ; sinon nom anglais du cdb ; sinon l'id (ex "Station" qui n'est pas une instance cdb)
_poiname0 = lambda k: _poitr.get(k) or _poi_name.get(k) or k
poiname = lambda x: _poiname0(x[4:]) if is_poi(x) else _poiname0(x)
# options du multiselect POI, dedoublonnees par nom traduit
_poi_by_nm = {}
for _pid in _world0.get("pois", {}):
    _nm = _poitr.get(_pid, _pid)
    if cdb_model.is_placeholder(_nm):
        continue
    if _nm not in _poi_by_nm or len(_pid) < len(_poi_by_nm[_nm]):
        _poi_by_nm[_nm] = _pid
poi_ids = ["POI:" + _v for _v in sorted(_poi_by_nm.values(), key=lambda i: _poitr.get(i, i))]
# nom d'affichage unifie d'une entree stockee (ressource OU poi prefixe "POI:")
itemname = lambda x: ("🏛️ " + poiname(x)) if is_poi(x) else resname(x)
# Ressources "structurelles" montrees AUSSI comme POI (ex epaves ShipWreck_Core). Elles RESTENT
# des ressources par ailleurs (is_poi() faux) -> toujours presentes dans l'onglet Gisements.
_POI_EXTRA = {"ShipWreck_Core"}
is_poi_like = lambda x: is_poi(x) or x in _POI_EXTRA
poi_label = lambda x: poiname(x) if is_poi(x) else resname(x)
# Traduction des services de station (facilities du scrape spacecraft.tools)
_FACIL_TR = {
    "Dock": {"fr": "Quai", "en": "Dock"},
    "ShipYard": {"fr": "Chantier naval", "en": "Shipyard"},
    "MiningBureau": {"fr": "Bureau minier", "en": "Mining Bureau"},
    "Marketplace": {"fr": "Marché", "en": "Marketplace"},
    "Laboratory": {"fr": "Laboratoire", "en": "Laboratory"},
}
def facil_label(csv):
    if not csv:
        return ""
    return ", ".join(_FACIL_TR.get(f, {}).get(lang, f) for f in str(csv).split(",") if f)
# Type de corps (du scrape) : seul "asteroidField" est notable (minage au vaisseau, pas d'atterrissage)
_BODY_TR = {"asteroidField": {"fr": "Champ d'astéroïdes", "en": "Asteroid field"}}
body_label = lambda b: _BODY_TR.get(b, {}).get(lang, "") if b else ""

shared = cloud_store.available()
map_err = None
if shared:
    try:
        map_data = discoveries.from_flat(fetch_shared())
    except Exception as e:
        map_data, map_err = discoveries.empty(), e
else:
    map_data = discoveries.load()

admin = steam_auth.is_admin(st.session_state.get("steam_user"))
banned_ids = {b.get("author_id") for b in fetch_bans_cached()} if shared else set()

# Objets partagés chargés UNE fois (caches) — dispo quel que soit l'onglet actif, car depuis le
# rendu conditionnel par onglet (cf. nav ci-dessous) seul l'onglet sélectionné s'exécute : on ne
# peut plus compter sur une variable définie dans un autre onglet (ex `w` jadis défini dans « Où trouver »).
sheets = load_sheets()
world = w = _world0

# Navigation par onglets PERSISTANTE (st.tabs perdait l'onglet actif à chaque rerun -> retour
# à l'accueil dès qu'on cherchait/sélectionnait). On garde l'onglet dans un query param `tab`
# (survit aux reruns ET au F5, comme rg/sy) + session_state via la clé du widget.
_qp = st.query_params
# Ordre des menus (exploration/carte d'abord, puis craft/économie, puis builders/progression).
_keys = ["tab_where", "tab_deposits", "tab_galaxymap", "tab_poi", "tab_universe", "tab_routes",
         "tab_recipes", "tab_items", "tab_craftmap",
         "tab_ship", "tab_base", "tab_permits", "tab_contracts"]
if admin:
    _keys.append("tab_admin")
if st.session_state.get("navtab") not in _keys:
    st.session_state["navtab"] = _qp.get("tab") if _qp.get("tab") in _keys else _keys[0]
_sel = st.segmented_control("nav", _keys, format_func=T, key="navtab", label_visibility="collapsed")
_sel = _sel or _qp.get("tab") or _keys[0]
if _sel not in _keys:
    _sel = _keys[0]
if _qp.get("tab") != _sel:
    _qp["tab"] = _sel

if _sel == "tab_routes":
    st.caption(T("routes_help"))
    _rd = load_routes()
    _n2i = routes_data.name_to_id(_rd)
    _origin = st.columns([2, 1, 2])
    _osys = _origin[0].selectbox(T("routes_origin"), sorted(_n2i.keys()), key="routes_origin")
    _maxc = _origin[1].number_input(T("routes_maxcost"), min_value=0, value=0, step=10, key="routes_maxc")
    _onlyd = _origin[2].checkbox(T("routes_only_disc"), key="routes_onlyd")
    _oid = _n2i[_osys]
    _cf = routes_data.costs_from(_rd, _oid)
    if len(_cf) <= 1:
        st.info(T("routes_unknown"))
    else:
        _disc = {sy.lower() for rgd in map_data["regions"].values() for sy in rgd.get("systems", {})}
        _rows = []
        for _sid, (_cst, _hop) in _cf.items():
            if _sid == _oid:
                continue
            _sm = _rd["systems"][_sid]
            if _maxc and _cst > _maxc:
                continue
            _has = _sm["name"].lower() in _disc
            if _onlyd and not _has:
                continue
            _rows.append({T("routes_col_cost"): _cst, T("routes_col_hops"): _hop,
                          T("col_system"): _sm["name"], T("col_sector"): _sm.get("sector"),
                          T("routes_col_disc"): "✓" if _has else ""})
        _rows.sort(key=lambda d: (d[T("routes_col_cost")], d[T("routes_col_hops")]))
        st.caption(T("routes_count").format(n=len(_rows)))
        st.dataframe(pd.DataFrame(_rows), hide_index=True, width="stretch", height=560)

if _sel == "tab_galaxymap":
    import galaxy_map
    st.caption(T("gmap_help"))
    _rd = load_routes()
    _systems = _rd["systems"]
    _name2sid = {_s["name"].lower(): _sid for _sid, _s in _systems.items()}
    _allnames = sorted(_s["name"] for _s in _systems.values())
    # index des découvertes par nom de système (base communautaire) -> garde le nom EXACT stocké
    _sysmap = {}
    for _rg, _rgd in map_data["regions"].items():
        for _sy, _syd in _rgd.get("systems", {}).items():
            _e = _sysmap.setdefault(_sy.lower(), {"sector": _rg, "sysname": _sy, "planets": {}})
            for _pl, _pld in _syd.get("planets", {}).items():
                _lst = _e["planets"].setdefault(_pl, [])
                for _r in _pld.get("resources", []):
                    if _r not in _lst:
                        _lst.append(_r)
    # hover + flag « a des découvertes » par système routé
    _meta = {}
    for _sid, _s in _systems.items():
        _disc = _sysmap.get(_s["name"].lower())
        _hl = ["<b>%s</b>" % _s["name"], _s.get("sector") or ""]
        if _disc and _disc["planets"]:
            for _pl, _res in list(_disc["planets"].items())[:6]:
                _rr = [resname(x) for x in _res if not is_poi(x)][:6]
                _hl.append("• %s : %s" % (_pl, ", ".join(_rr) if _rr else "—"))
            _more = len(_disc["planets"]) - 6
            if _more > 0:
                _hl.append("…+%d" % _more)
        else:
            _hl.append(T("gmap_no_disc"))
        _meta[_sid] = {"hover": "<br>".join(x for x in _hl if x),
                       "disc": bool(_disc and _disc["planets"])}
    # systèmes ayant une station (POI:Station, le nom de la station = nom de la "planète" stockée)
    _stations = {}
    for _rg, _rgd in map_data["regions"].items():
        for _sy, _syd in _rgd.get("systems", {}).items():
            _stn = [_pl for _pl, _pld in _syd.get("planets", {}).items()
                    if "POI:Station" in _pld.get("resources", [])]
            if _stn:
                _sid4 = _name2sid.get(_sy.lower())
                if _sid4:
                    _stations[_sid4] = _stn
    _sectors = {_s.get("sector") for _s in _systems.values() if _s.get("sector")}
    _colors = galaxy_map.sector_colors(_sectors)
    _amap = discoveries.abundance_map(fetch_shared()) if shared else {}
    # compteur de localisations par ressource (façon spacecraft.tools : "Nom (N spots)")
    _rescount = {}
    for _rg, _rgd in map_data["regions"].items():
        for _sy, _syd in _rgd.get("systems", {}).items():
            for _pl, _pld in _syd.get("planets", {}).items():
                for _r in _pld.get("resources", []):
                    if not is_poi(_r):
                        _rescount[_r] = _rescount.get(_r, 0) + 1
    _resopts = sorted(_rescount, key=lambda r: resname(r))
    _c1, _c2, _c3, _c4 = st.columns([2, 3, 2, 2])
    _secsel = _c1.selectbox(T("gmap_sector"), [T("gmap_all")] + sorted(_sectors), key="gmap_sec")
    _focus = None if _secsel == T("gmap_all") else _secsel
    _rsel = _c2.multiselect(T("gmap_res"), _resopts,
                            format_func=lambda r: f"{resname(r)} ({_rescount.get(r, 0)})", key="gmap_res")
    # seuils min densité / quantité : actifs seulement si un filtre ressource est posé ET que la donnée existe
    _seld = [_v for _k, _v in _amap.items() if _rsel and _k[3] in _rsel]
    _maxd = max((_v.get("density") for _v in _seld if isinstance(_v.get("density"), (int, float))), default=0)
    _maxq = max((_v.get("count") for _v in _seld if isinstance(_v.get("count"), (int, float))), default=0)
    _dens = _c3.slider(T("gmap_density"), 0.0, float(_maxd), 0.0, key="gmap_dens") if (_rsel and _maxd > 0) else 0
    _qty = _c4.slider(T("gmap_qty"), 0, int(_maxq), 0, key="gmap_qty") if (_rsel and _maxq > 0) else 0
    # highlight = systèmes routés ayant ≥1 planète avec une ressource sélectionnée (densité ≥ seuil)
    _hlset = None
    if _rsel:
        _want = set(_rsel)
        _hlset = set()
        for _rg, _rgd in map_data["regions"].items():
            for _sy, _syd in _rgd.get("systems", {}).items():
                _ok = False
                for _pl, _pld in _syd.get("planets", {}).items():
                    for _r in _pld.get("resources", []):
                        if _r in _want:
                            if _dens > 0 or _qty > 0:
                                _ab = _amap.get((_rg, _sy, _pl, _r), {})
                                _dv, _cv = _ab.get("density"), _ab.get("count")
                                if _dens > 0 and not (isinstance(_dv, (int, float)) and _dv >= _dens):
                                    continue
                                if _qty > 0 and not (isinstance(_cv, (int, float)) and _cv >= _qty):
                                    continue
                            _ok = True
                            break
                    if _ok:
                        break
                if _ok:
                    _sid2 = _name2sid.get(_sy.lower())
                    if _sid2:
                        _hlset.add(_sid2)
        st.caption(T("gmap_match").format(n=len(_hlset)))
    # 🧭 Planificateur de route (2 modes) — trace le chemin FTL le moins coûteux sur la carte
    _route = None
    with st.expander(T("gmap_route_title")):
        import routes_data as _rdm
        _adj = _rdm.adjacency(_rd)
        _m1, _m2 = T("gmap_route_m1"), T("gmap_route_m2")
        _mode = st.radio(T("gmap_route_mode"), [_m1, _m2], horizontal=True, key="gmap_rmode")
        _rc1, _rc2 = st.columns(2)
        _from = _rc1.selectbox(T("gmap_route_from"), ["—"] + _allnames, key="gmap_rfrom")
        if _mode == _m1:
            _to = _rc2.selectbox(T("gmap_route_to"), ["—"] + _allnames, key="gmap_rto")
            if _from != "—" and _to != "—":
                _sp = _rdm.shortest_path(_rd, _name2sid[_from.lower()], _name2sid[_to.lower()], _adj)
                if not _sp:
                    st.warning(T("gmap_route_none"))
                else:
                    _route = _sp["path"]
                    _pn = " → ".join(_systems[s]["name"] for s in _route)
                    st.success(T("gmap_route_result").format(n=_sp["hops"], c=round(_sp["cost"]), path=_pn))
        else:
            _rres = _rc2.selectbox(T("gmap_route_res"), ["—"] + _resopts, key="gmap_rres",
                                   format_func=lambda r: "—" if r == "—" else f"{resname(r)} ({_rescount.get(r, 0)})")
            # seuils densité/quantité min sur la ressource cherchée (route vers un spot « assez riche »)
            _rd2 = _rq2 = 0
            if _rres != "—":
                _sv2 = [_v for _k, _v in _amap.items() if _k[3] == _rres]
                _md2 = max((_v.get("density") for _v in _sv2 if isinstance(_v.get("density"), (int, float))), default=0)
                _mq2 = max((_v.get("count") for _v in _sv2 if isinstance(_v.get("count"), (int, float))), default=0)
                _rk1, _rk2 = st.columns(2)
                _rd2 = _rk1.slider(T("gmap_density"), 0.0, float(_md2), 0.0, key="gmap_rdens") if _md2 > 0 else 0
                _rq2 = _rk2.slider(T("gmap_qty"), 0, int(_mq2), 0, key="gmap_rqty") if _mq2 > 0 else 0
            if _from != "—" and _rres != "—":
                _tgt = set()
                for _rg, _rgd in map_data["regions"].items():
                    for _sy, _syd in _rgd.get("systems", {}).items():
                        _hit = False
                        for _pl, _pld in _syd.get("planets", {}).items():
                            if _rres in _pld.get("resources", []):
                                if _rd2 > 0 or _rq2 > 0:
                                    _ab = _amap.get((_rg, _sy, _pl, _rres), {})
                                    _dv, _cv = _ab.get("density"), _ab.get("count")
                                    if _rd2 > 0 and not (isinstance(_dv, (int, float)) and _dv >= _rd2):
                                        continue
                                    if _rq2 > 0 and not (isinstance(_cv, (int, float)) and _cv >= _rq2):
                                        continue
                                _hit = True
                                break
                        if _hit:
                            _sid3 = _name2sid.get(_sy.lower())
                            if _sid3:
                                _tgt.add(_sid3)
                _sp = _rdm.nearest_with(_rd, _name2sid[_from.lower()], _tgt, _adj) if _tgt else None
                if not _sp:
                    st.warning(T("gmap_route_nores"))
                else:
                    _route = _sp["path"]
                    _pn = " → ".join(_systems[s]["name"] for s in _route)
                    st.success(T("gmap_route_target").format(sys=_systems[_sp["target"]]["name"], res=resname(_rres)))
                    st.success(T("gmap_route_result").format(n=_sp["hops"], c=round(_sp["cost"]), path=_pn))
    _labels = st.checkbox(T("gmap_labels"), value=bool(_focus), key="gmap_labels",
                          help=T("gmap_labels_help"))
    st.plotly_chart(galaxy_map.build_figure(_rd, _meta, _colors, _focus, _hlset, _route,
                                            _stations, T("gmap_stations"), show_labels=_labels),
                    width="stretch",
                    config={"scrollZoom": True, "displayModeBar": False})
    # détail au « clic » = selectbox système -> ressources par planète (Streamlit ne capte pas
    # le clic natif sur un nœud Plotly ; ce sélecteur joue ce rôle)
    _sysnames = sorted(_s["name"] for _s in _systems.values()
                       if not _focus or _s.get("sector") == _focus)
    _pick = st.selectbox(T("gmap_system"), ["—"] + _sysnames, key="gmap_sys")
    if _pick != "—":
        _d = _sysmap.get(_pick.lower())
        if not _d or not _d["planets"]:
            st.info(T("gmap_sys_empty"))
        else:
            import res_view
            _plopts = sorted(_d["planets"].keys())
            _plpick = st.selectbox(T("gmap_planet"), [T("gmap_all_planets")] + _plopts, key="gmap_pl")
            _icons = load_res_icons()
            if _plpick == T("gmap_all_planets"):
                # AGRÉGÉ : somme des quantités par gisement sur tout le système (densité = meilleur spot)
                _agg = {}
                for _pl in _plopts:
                    for _r in _d["planets"][_pl]:
                        if is_poi(_r):
                            continue
                        _ab = _amap.get((_d["sector"], _d["sysname"], _pl, _r), {})
                        _c, _dn = _ab.get("count"), _ab.get("density")
                        _e = _agg.setdefault(_r, {"c": 0, "has": False, "d": None})
                        if isinstance(_c, (int, float)):
                            _e["c"] += _c; _e["has"] = True
                        if isinstance(_dn, (int, float)) and (_e["d"] is None or _dn > _e["d"]):
                            _e["d"] = _dn
                _rws = [(_r, (_e["c"] if _e["has"] else None), _e["d"]) for _r, _e in _agg.items()]
                _planets = [(_pick, _rws)] if _rws else []
            else:
                # DÉTAIL d'une planète précise
                _rws = [(_r, _amap.get((_d["sector"], _d["sysname"], _plpick, _r), {}).get("count"),
                         _amap.get((_d["sector"], _d["sysname"], _plpick, _r), {}).get("density"))
                        for _r in _d["planets"].get(_plpick, []) if not is_poi(_r)]
                _planets = [(_plpick, _rws)] if _rws else []
            if _planets:
                st.markdown(res_view.render(_planets, resname, restype_label, _icons,
                                            T("col_count"), T("col_density")), unsafe_allow_html=True)
                # lingots faisables : minerais produits par les gisements de la planète -> lingots
                _o2i = load_ore2ingot()
                _ingp = []
                for _pl, _rws in _planets:
                    _found = {}
                    for _rid, _, _ in _rws:
                        for _ore in deposits.get(_rid, {}).get("items", []):
                            for _ing in _o2i.get(_ore, []):
                                _found.setdefault(_ing, set()).add(_ore)
                    _ingp.append((_pl, [(_ing, sorted(_o)) for _ing, _o in _found.items()]))
                if any(_i for _, _i in _ingp):
                    st.markdown(res_view.ingot_cards(_ingp, resname, _icons,
                                                     T("ingots_title"), T("ingots_via")), unsafe_allow_html=True)
            else:
                st.info(T("gmap_sys_empty"))

if _sel == "tab_recipes":
    c = st.columns([2, 1, 1, 1])
    q = c[0].text_input(T("search_recipe"))
    stations = [T("all_f")] + sorted([s for s in df["station"].unique() if s and s != "-"])
    fstat = c[1].selectbox(T("station"), stations)
    unlocks = [T("all_m")] + sorted(df["unlock"].unique())
    funlock = c[2].selectbox(T("unlock"), unlocks)
    sort_keys = ["sort_va_desc", "sort_va_asc", "sort_vah", "sort_az"]
    sort = c[3].selectbox(T("sort_by"), sort_keys, format_func=T)
    only_pos = st.checkbox(T("only_pos"), value=False)

    d = df.copy()
    if q:
        ql = q.lower()
        # recherche aussi dans les SOUS-PRODUITS (recettes multi-output : ex "Malachite" via la recette "Azurite")
        d = d[d["product"].str.lower().str.contains(ql) | d["inputs_str"].str.lower().str.contains(ql)
              | d["outputs_str"].str.lower().str.contains(ql)]
    if fstat != T("all_f"):
        d = d[d["station"] == fstat]
    if funlock != T("all_m"):
        d = d[d["unlock"] == funlock]
    if only_pos:
        d = d[d["va"] > 0]
    if sort == "sort_va_desc":
        d = d.sort_values("va", ascending=False)
    elif sort == "sort_va_asc":
        d = d.sort_values("va", ascending=True)
    elif sort == "sort_vah":
        d = d.sort_values("va_per_h", ascending=False, na_position="last")
    else:
        d = d.sort_values("product")

    st.write(f'**{len(d)} {T("n_recipes")}**')
    cols = {"product": T("col_product"), "va": T("col_va"), "out_qty": T("col_qty"),
            "va_per_h": T("col_vah"), "power": T("col_power"), "station": T("col_station"),
            "unlock": T("col_unlock"), "inputs_str": T("col_inputs"), "outputs_str": T("col_outputs")}
    show = d[list(cols.keys())].rename(columns=cols)

    def color_va(v):
        if pd.isna(v):
            return ""
        return "color:#1a9850;font-weight:bold" if v > 0 else ("color:#d73027;font-weight:bold" if v < 0 else "")

    sty = (show.style
           .map(color_va, subset=[T("col_va")])
           .format({T("col_va"): "{:.2f}", T("col_vah"): "{:.2f}", T("col_power"): "{:.0f}"}, na_rep="—"))
    st.dataframe(sty, width="stretch", height=600, hide_index=True)

if _sel == "tab_items":
    qi = st.text_input(T("search_item"))
    di = pd.DataFrame([{T("col_itemname"): v["name"], T("col_price"): v["price"],
                        T("col_type"): v["type"], T("col_loot"): v["lootLevel"]} for v in items.values()])
    if qi:
        di = di[di[T("col_itemname")].str.lower().str.contains(qi.lower())]
    di = di.sort_values(T("col_price"), ascending=False)
    st.write(f'**{len(di)} {T("n_items")}**')
    st.dataframe(di, width="stretch", height=400, hide_index=True,
                 column_config={T("col_price"): st.column_config.NumberColumn(format="%.2f")})

    # --- Fiche d'un item : stats + produit par / utilisé dans ---
    st.divider()
    st.subheader(T("item_detail"))
    _iids = sorted(items.keys(), key=lambda i: items[i]["name"])
    _isel = st.selectbox(T("item_pick"), _iids, format_func=lambda i: items[i]["name"], key="item_detail_sel")
    if _isel:
        _it = items[_isel]
        _c1, _c2 = st.columns([1, 2])
        with _c1:
            st.metric(T("col_price"), f'{_it.get("price", 0):.2f}')
            st.caption(f'{T("col_type")}: {_it.get("type", "—")}')
            _at = build_data.item_attributes(sheets, _isel)
            if _at:
                _am = build_data.attr_meta(sheets)
                st.dataframe(pd.DataFrame([{
                    T("ir_attr"): _am.get(k, (k, ""))[0] + (f" [{_am.get(k, ('', ''))[1]}]" if _am.get(k, ("", ""))[1] else ""),
                    T("ir_value"): v} for k, v in _at.items()]), hide_index=True, width="stretch")
        with _c2:
            _prod, _used = graph_data.item_recipes(sheets, items, _isel)
            st.caption(T("item_prod_by"))
            if _prod:
                st.dataframe(pd.DataFrame([{T("ir_in"): r["in"], T("ir_out"): r["out"], T("col_station"): r["where"]} for r in _prod]),
                             hide_index=True, width="stretch")
            else:
                st.caption(T("item_prod_none"))
            st.caption(T("item_used_in"))
            if _used:
                st.dataframe(pd.DataFrame([{T("ir_product"): r["product"], T("ir_in"): r["in"], T("col_station"): r["where"]} for r in _used]),
                             hide_index=True, width="stretch")
            else:
                st.caption(T("item_used_none"))

        # --- Où miner cet item (carte communautaire) : ses gisements -> localisations découvertes ---
        st.caption(T("item_mine_where"))
        _src = w["item_sources"].get(_isel, [])
        _abund2 = discoveries.abundance_map(fetch_shared()) if shared else {}
        _mine = []
        for s in _src:
            _rid = s.get("res")
            if not _rid:
                continue
            for rg, sy, pl in discoveries.find_resource(map_data, _rid):
                a = _abund2.get((rg, sy, pl, _rid), {})
                _mine.append({T("col_deposit"): resname(_rid), T("col_sector"): rg, T("col_system"): sy,
                              T("col_planet"): pl, T("col_count"): a.get("count"),
                              T("col_density"): a.get("density"), T("col_bodytype"): body_label(a.get("body_type"))})
        if _mine:
            _mine.sort(key=lambda d: (-(d[T("col_count")] or 0), d[T("col_sector")], d[T("col_system")]))
            st.dataframe(pd.DataFrame(_mine), hide_index=True, width="stretch", height=300)
        else:
            st.caption(T("item_mine_none"))

        # --- Où vendre cet item (prix de rachat des stations, hors ventes scénarisées tuto) ---
        _sell = load_market().get(_isel, [])
        if _sell:
            st.caption(T("item_sell_where"))
            st.dataframe(pd.DataFrame([{T("col_station"): s["station"], T("item_sell_price"): s["sell"],
                                        T("item_buy_price"): s["buy"]} for s in _sell]),
                         hide_index=True, width="stretch",
                         column_config={T("item_sell_price"): st.column_config.NumberColumn(format="%.2f"),
                                        T("item_buy_price"): st.column_config.NumberColumn(format="%.2f")})

if _sel == "tab_craftmap":
    sheets = load_sheets()
    prods = graph_data.craftable_products(sheets, items)
    plabel = {i: items.get(i, {}).get("name", i) for i in prods}
    cc = st.columns([3, 1, 1, 1.2])
    sel_prod = cc[0].selectbox(T("select_product"), prods, format_func=lambda i: plabel.get(i, i))
    depth = cc[1].slider(T("depth"), 1, 8, 4)
    qtymake = cc[2].number_input(T("make_qty"), min_value=1, value=1, step=1)
    cmode = cc[3].radio(T("view"), ["v_table", "v_graph"], format_func=T, key="cmode")
    # aide adaptée à la vue : le tableau (recettes/options) vs le graphe interactif
    st.caption(T("craftmap_help") if cmode == "v_graph" else T("craftmap_help_table"))

    _allrec = graph_data.all_prod_recipes(sheets)
    _best = graph_data.best_recipes(sheets, items)
    _cnm = lambda i: items.get(i, {}).get("name", i)
    _LET = "ABCDEFGHIJKLMNOPQRSTUVWXYZ"
    _esc = lambda s: str(s).replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
    def _node_line(n):  # ligne d'un nœud (item coloré + qté + prix + station, ou option A/B/C)
        if n["kind"] == "item":
            iid = n["id"]; pr = items.get(iid, {}).get("price", 0)
            col = "#e8542f" if n["depth"] == 0 else ("#4575b4" if n["children"] else "#1a9850")  # produit/intermédiaire/brut
            sta = f" · {_esc(n['station'])}" if n.get("station") else ""
            return (f"<b style='color:{col}'>{_esc(_cnm(iid))}</b> "
                    f"<span style='color:#999'>×{n['qty']}</span>"
                    f"<span style='color:#777'> — {pr:.2f}{sta}</span>")
        chosen = " ✅" if n.get("chosen") else ""
        return (f"<span style='color:#d9a441'>⎇ {T('alt_option')} {_LET[n['idx']]} · "
                f"{_esc(unlock_label(n['unlock']))}{chosen}</span>")
    def _tree_html(_rows):  # arbre repliable : <details> = pliage natif navigateur (pas de rerun)
        root = {"depth": -1, "children": []}
        stack = [root]
        for r in _rows:
            node = dict(r, children=[])
            while stack[-1]["depth"] >= r["depth"]:
                stack.pop()
            stack[-1]["children"].append(node)
            stack.append(node)
        def render(nodes):
            out = []
            for n in nodes:
                ln = _node_line(n)
                if n["children"]:
                    out.append(f"<details open style='margin:2px 0 2px 13px'>"
                               f"<summary>{ln}</summary>{render(n['children'])}</details>")
                else:
                    out.append(f"<div style='margin:2px 0 2px 26px'>{ln}</div>")
            return "".join(out)
        return ("<style>body{margin:0;background:#0e1117;color:#fafafa;font-family:'Source Sans Pro',sans-serif;font-size:14px}"
                "summary{cursor:pointer;list-style:none}summary::-webkit-details-marker{display:none}"
                "details>summary:before{content:'▾ ';color:#888}details:not([open])>summary:before{content:'▸ ';color:#888}</style>"
                f"<div style='line-height:1.6'>{render(root['children'])}</div>")
    if cmode == "v_table":
        # recettes du produit : la choisie (moins chère) en 1er, puis les alternatives. Arbre REPLIABLE,
        # qui BRANCHE sur les sous-composants multi-recettes (Options A/B/C + sous-craft).
        _prodrecs = _allrec.get(sel_prod, [])
        _ch = _best.get(sel_prod)
        _chosen = next((r for r in _prodrecs if _ch and list(r[0]) == list(_ch[0])), _prodrecs[0] if _prodrecs else None)
        _ordered = ([_chosen] if _chosen else []) + [r for r in _prodrecs if r is not _chosen]
        for _n, (_ins, _unlock, _rid, _oq, _where) in enumerate(_ordered):
            _batch = f" · {T('alt_batch').format(n=_oq)}" if _oq > 1 else ""
            _head = f"#### {_cnm(sel_prod)} — _{unlock_label(_unlock)}_{_batch}" if _n == 0 \
                else f"#### 🔀 {T('alt_recipe_one')} — _{unlock_label(_unlock)}_{_batch}"
            st.markdown(_head)
            _ot = graph_data.options_tree(sheets, items, sel_prod, _ins, out_qty=_oq, root_where=_where,
                                          qty=qtymake, allrec=_allrec, best=_best, max_depth=depth)
            components.html(_tree_html(_ot), height=min(650, max(120, len(_ot) * 26 + 24)), scrolling=True)
    else:
        nodes, edges = graph_data.craft_chain(sheets, items, sel_prod, max_depth=depth)
        components.html(graph_data.to_html(nodes, edges, height="560px", hierarchical=True, direction="DU"), height=580)

    st.subheader(T("raw_title"))
    raw = graph_data.raw_materials(sheets, items, sel_prod, qty=qtymake)
    if raw:
        c1, c2 = st.columns([3, 1])
        c1.dataframe(pd.DataFrame([{T("col_comp"): r["name"], T("col_rawqty"): r["qty"],
                                    T("col_price"): r["price"], T("col_cost"): r["cost"]} for r in raw]),
                     hide_index=True, width="stretch",
                     column_config={T("col_price"): st.column_config.NumberColumn(format="%.2f"),
                                    T("col_cost"): st.column_config.NumberColumn(format="%.2f")})
        total = sum(r["cost"] for r in raw)
        sell = items.get(sel_prod, {}).get("price", 0) * qtymake
        c2.metric(T("total_cost"), f"{total:.2f}", delta=f"{sell - total:+.2f} VA")

    # --- 🏭 Débits d'usine : machines nécessaires pour un débit cible ---
    st.subheader(T("factory_title"))
    st.caption(T("factory_help"))
    target = st.number_input(T("factory_target"), min_value=1, value=60, step=10, key="fac_target")
    fac = graph_data.factory_plan(sheets, items, _product_time, sel_prod, target_per_h=target, max_depth=depth)
    _nmach = sum(r["machines"] for r in fac if r["machines"])
    _energy = sum(r["energy_h"] for r in fac)
    _fm = st.columns(2)
    _fm[0].metric(T("factory_machines"), f"{_nmach}")
    _fm[1].metric(T("factory_energy"), f"{_energy:,}".replace(",", " "))
    dff = pd.DataFrame([{
        T("col_comp"): (("　" * (r["depth"] - 1) + "└ ") if r["depth"] else "") + r["name"],
        T("fac_c_rate"): r["rate"],
        # None (pas "—") -> colonne numérique -> tri correct ; affiché vide pour les matières brutes
        T("fac_c_machines"): r["machines"],
        T("fac_c_mrate"): r["machine_rate"],
        T("col_station"): r["station"]} for r in fac])
    st.dataframe(dff, hide_index=True, width="stretch", height=400)
    _raw = {}
    for r in fac:
        if r["machines"] is None:
            _raw[r["name"]] = _raw.get(r["name"], 0) + r["rate"]
    if _raw:
        st.caption(T("factory_raw"))
        st.dataframe(pd.DataFrame([{T("col_comp"): k, T("fac_c_rate"): round(v, 1)}
                                   for k, v in sorted(_raw.items(), key=lambda x: -x[1])]),
                     hide_index=True, width="stretch")

if _sel == "tab_universe":
    st.caption(T("universe_help"))
    umode = st.radio(T("view"), ["v_table", "v_graph"], format_func=T, horizontal=True, key="umode")
    sheets = load_sheets(); world = load_world()
    # i18n pour l'arbre/graphe Univers : libellés de niveau + résolveurs de noms (POI, stations) traduits
    _utr = {"kinds": {"sector": T("u_k_sector"), "system": T("u_k_system"), "planet": T("u_k_planet"),
                      "station": T("u_k_station"), "instance": T("u_k_instance")},
            "insname": lambda i: _poiname0(i), "obname": lambda o: market_data.STATION_NAMES.get(o, o),
            "res_word": T("u_resources"), "gen": T("u_gen")}
    if umode == "v_table":
        urows = graph_data.universe_tree_rows(sheets, world=world, items=items, tr=_utr)
        dfu = pd.DataFrame([{
            T("col_place"): ("　" * r["depth"] + ("└ " if r["depth"] else "")) + r["name"],
            T("col_type"): r["kind"], T("col_detail"): r["extra"]} for r in urows])
        st.dataframe(dfu, hide_index=True, width="stretch", height=600)
    else:
        nodes, edges = graph_data.universe_graph(sheets, world=world, items=items, res_label=T("u_resources"), tr=_utr)
        # superpose les découvertes communautaires (systèmes/planètes ajoutés par les joueurs)
        name2sec = {nm: sid for sid, nm in world["sector_name"].items()}
        sys_name2id = world.get("system_name2id", {})
        n_disc = 0
        for rg, rgd in map_data.get("regions", {}).items():
            rid = name2sec.get(rg, "drg:" + rg)
            if rid not in nodes:
                nodes[rid] = {"label": rg, "title": rg, "kind": "sector"}
            for sy, syd in rgd.get("systems", {}).items():
                # réutilise le nœud système du cdb si même nom (évite un doublon, ex "Sawma")
                if sys_name2id.get(sy) in nodes:
                    sid = sys_name2id[sy]
                else:
                    sid = f"dsys:{rg}/{sy}"
                    nodes[sid] = {"label": sy, "title": f"{sy} ({T('mm_k_system')})", "kind": "disc_system"}
                    edges.append((rid, sid, ""))
                for pl, pld in syd.get("planets", {}).items():
                    pid = f"dpl:{rg}/{sy}/{pl}"
                    deps = pld.get("resources", [])
                    ttl = pl + ((" — " + ", ".join(itemname(d) for d in deps)) if deps else "")
                    nodes[pid] = {"label": pl, "title": ttl, "kind": "disc_planet"}
                    edges.append((sid, pid, ""))
                    n_disc += 1
        if n_disc:
            st.caption(T("u_disc_legend"))
        components.html(graph_data.to_html(nodes, edges, height="640px", hierarchical=True, direction="UD"), height=660)

if _sel == "tab_where":
    st.caption(T("where_help"))
    w = load_world()
    mineable = sorted(w["item_sources"].keys(), key=lambda i: items.get(i, {}).get("name", i))
    rlabel = {i: items.get(i, {}).get("name", i) for i in mineable}
    selr = st.selectbox(T("select_res"), mineable, format_func=lambda i: rlabel.get(i, i))
    srcs = w["item_sources"].get(selr, [])
    secs = sorted(w["item_sectors"].get(selr, set()), key=lambda s: (w["sector_reslevel"].get(s) or 99))
    _mlvl = w.get("mining_item", {}).get(selr)
    if _mlvl:
        st.caption(T("where_minlvl").format(lvl=_mlvl))
    if not srcs and not secs:
        st.info(T("where_none"))
    else:
        ca, cb = st.columns(2)
        with ca:
            st.subheader(T("where_mined"))
            st.dataframe(pd.DataFrame([{T("col_deposit"): resname(s.get("res")), T("col_type"): restype_label(s["type"]),
                                        T("col_tier"): s["tier"], T("col_proba"): s["proba"],
                                        T("col_minlvl"): str(w.get("mining_res", {}).get(s.get("res")) or "—")} for s in srcs]),
                         hide_index=True, width="stretch")
        with cb:
            st.subheader(T("where_sectors"))
            def _req(sid):
                r = w["sector_req"].get(sid) or []
                return ", ".join(f'{x.get("attribute")} {x.get("level")}' for x in r) or "-"
            st.dataframe(pd.DataFrame([{T("col_sector"): w["sector_name"].get(s, s),
                                        T("col_reslevel"): w["sector_reslevel"].get(s), T("col_req"): _req(s)}
                                       for s in secs]), hide_index=True, width="stretch")

        # Croisement avec les decouvertes (carte communautaire) : un item provient de
        # gisements (res ids) ; on liste les systemes/planetes ou ces gisements ont ete trouves.
        res_names = {s["res"]: resname(s["res"]) for s in srcs if s.get("res")}
        _abund = discoveries.abundance_map(fetch_shared()) if shared else {}
        found = []
        for rid, dname in res_names.items():
            for rg, sy, pl in discoveries.find_resource(map_data, rid):
                a = _abund.get((rg, sy, pl, rid), {})
                found.append({T("col_sector"): rg, T("col_system"): sy,
                              T("col_planet"): pl, T("col_deposit"): dname,
                              T("col_count"): a.get("count"), T("col_density"): a.get("density"),
                              T("col_bodytype"): body_label(a.get("body_type"))})
        st.subheader(T("where_found"))
        if found:
            # tri par quantite decroissante (meilleurs spots de minage d'abord ; None en dernier)
            found.sort(key=lambda d: (-(d[T("col_count")] or 0), d[T("col_sector")],
                                      d[T("col_system")], d[T("col_planet")]))
            st.dataframe(pd.DataFrame(found), hide_index=True, width="stretch")
        else:
            st.info(T("where_found_none"))

if _sel == "tab_deposits":
    st.caption(T("dep_help"))
    # tous les gisements presents dans la carte communautaire (hors POI), tries par nom traduit
    _all_ids = sorted((x for x in discoveries.all_resource_ids(map_data) if not is_poi(x)), key=resname)
    if not _all_ids:
        st.info(T("dep_empty"))
    else:
        _lab = {resname(x): x for x in _all_ids}
        c1, c2 = st.columns([3, 2])
        with c1:
            _sel_names = st.multiselect(T("dep_select"), sorted(_lab.keys()), key="dep_sel")
        with c2:
            _secf = st.multiselect(T("dep_sector_filter"), sorted(map_data["regions"].keys()), key="dep_secf")
        # ET = planètes ayant TOUS les gisements sélectionnés (intersection) ; OU = au moins un (union)
        _and = st.radio(T("dep_match"), [T("dep_match_all"), T("dep_match_any")],
                        horizontal=True, key="dep_match") == T("dep_match_all")
        if _sel_names:
            _abund = discoveries.abundance_map(fetch_shared()) if shared else {}
            # localisations (secteur, système, planète) par gisement, filtrées secteur
            _locs = {}
            for nm in _sel_names:
                rid = _lab[nm]
                _locs[nm] = {(rg, sy, pl) for rg, sy, pl in discoveries.find_resource(map_data, rid)
                             if not (_secf and rg not in _secf)}
            _sets = list(_locs.values())
            _keep = set.intersection(*_sets) if _and else set.union(*_sets)  # planètes à garder
            _rows = []
            for nm in _sel_names:
                rid = _lab[nm]
                for (rg, sy, pl) in _locs[nm]:
                    if (rg, sy, pl) not in _keep:
                        continue
                    a = _abund.get((rg, sy, pl, rid), {})
                    _rows.append({T("col_deposit"): nm, T("col_sector"): rg, T("col_system"): sy,
                                  T("col_planet"): pl, T("col_count"): a.get("count"),
                                  T("col_density"): a.get("density"),
                                  T("col_bodytype"): body_label(a.get("body_type"))})
            if _rows:
                if _and:
                    # regroupe par planète (toutes ses lignes adjacentes) puis par gisement
                    _rows.sort(key=lambda d: (d[T("col_sector")], d[T("col_system")],
                                              d[T("col_planet")], d[T("col_deposit")]))
                    st.caption(T("dep_count_and").format(n=len(_keep), k=len(_sel_names)))
                else:
                    _rows.sort(key=lambda d: (-(d[T("col_count")] or 0), d[T("col_sector")],
                                              d[T("col_system")], d[T("col_planet")]))
                    st.caption(T("dep_count").format(n=len(_rows)))
                st.dataframe(pd.DataFrame(_rows), hide_index=True, width="stretch", height=560)
            else:
                st.info(T("dep_none"))
        else:
            st.info(T("dep_pick"))

if _sel == "tab_poi":
    st.caption(T("poi_help"))
    # liste a plat des POI decouverts (carte communautaire) : POI | Planete | Systeme | Secteur
    _meta = discoveries.abundance_map(fetch_shared()) if shared else {}
    _prows = []
    for rg, rgd in map_data.get("regions", {}).items():
        for sy, syd in rgd.get("systems", {}).items():
            for pl, pld in syd.get("planets", {}).items():
                for x in pld.get("resources", []):
                    if is_poi_like(x):
                        svc = facil_label(_meta.get((rg, sy, pl, x), {}).get("facilities"))
                        _prows.append({T("poi_col_name"): poi_label(x), T("col_planet"): pl,
                                       T("col_system"): sy, T("col_sector"): rg,
                                       T("poi_col_services"): svc})
    if not _prows:
        st.info(T("poi_empty"))
    else:
        # filtre par type (utile : les epaves dominent en nombre vs les bases planetaires)
        _types = sorted({d[T("poi_col_name")] for d in _prows})
        _tf = st.multiselect(T("poi_type_filter"), _types, key="poi_typef")
        if _tf:
            _prows = [d for d in _prows if d[T("poi_col_name")] in _tf]
        _prows.sort(key=lambda d: (d[T("poi_col_name")], d[T("col_sector")], d[T("col_system")], d[T("col_planet")]))
        st.caption(T("poi_count").format(n=len(_prows)))
        st.dataframe(pd.DataFrame(_prows)[[T("poi_col_name"), T("col_planet"), T("col_system"),
                                           T("col_sector"), T("poi_col_services")]],
                     hide_index=True, width="stretch", height=500)


# --- Onglet SHIP BUILDER : assembler un vaisseau, bilans depuis les stats du cdb ---
if _sel == "tab_ship":
    st.caption(T("ship_help"))
    _ttr = sheet_translations(lang, "itemType")  # libellés = noms de catégorie du jeu
    _CAT_OVR = {"MiningTool": "ShipGatheringTools"}  # header du jeu = nom du parent (« Collecte »)
    _clabel = lambda t: _ttr.get(_CAT_OVR.get(t, t)) or _ttr.get(t) or t
    _cocklist = build_data.grouped(sheets, items, [build_data.COCKPIT_TYPE])
    if not _cocklist:
        st.info(T("sb_empty"))
    else:
        _picks = []
        _co = _cocklist[0]["list"]
        _ci = st.selectbox(_clabel(build_data.COCKPIT_TYPE), range(len(_co)),
                           format_func=lambda i: f"{_co[i]['name']}  ·  {_co[i]['price']:.0f}", key="ship_cockpit")
        _picks.append(_co[_ci])
        _sgroups = build_data.grouped(sheets, items, build_data.ship_module_types(sheets))
        _oc = st.columns(3)
        for _n, _g in enumerate(_sgroups):
            with _oc[_n % 3]:
                _opts = _g["list"]
                for _s in st.multiselect(_clabel(_g["cat"]), range(len(_opts)),
                                         format_func=lambda i, o=_opts: f"{o[i]['name']}  ·  {o[i]['price']:.0f}",
                                         key="ship_" + _g["cat"]):
                    _picks.append(_opts[_s])
        # quantités par module choisi (table éditable)
        _dfq = pd.DataFrame([{T("sb_comp"): c["name"], T("sb_qty"): 1} for c in _picks])
        _ed = st.data_editor(_dfq, hide_index=True, width="stretch", disabled=[T("sb_comp")], key="ship_qty",
                             column_config={T("sb_qty"): st.column_config.NumberColumn(min_value=0, step=1)})
        _chosen = []
        for _k, _c in enumerate(_picks):
            _q = int(_ed[T("sb_qty")].iloc[_k]) if _k < len(_ed) else 1
            _chosen += [_c] * max(_q, 0)
        _tot = build_data.sum_attrs(_chosen)
        _sup, _req = _tot.get("SystemSupport", 0), _tot.get("SystemRequirement", 0)
        _prod, _use = _tot.get("PowerProduction", 0), _tot.get("EngineConsumption", 0)
        _force, _weight = _tot.get("EngineForce", 0), _tot.get("ShipWeight", 0)
        _cost = sum(c["price"] for c in _chosen)
        _uc = graph_data.unit_costs(sheets, items)
        _rawcost = sum(_uc.get(c["id"], 0) or 0 for c in _chosen)
        _heatcap = _tot.get("HeatCapacity", 0)
        _heatgen = sum(v for k, v in _tot.items() if "HeatGeneration" in k)
        _m = st.columns(4)
        _m[0].metric(T("sb_syspoints"), f"{_sup - _req:.0f}", delta=f"{_sup:.0f} / {_req:.0f}", delta_color="off")
        _m[1].metric(T("sb_power"), f"{_prod - _use:.0f}", delta=f"{_prod:.0f} / {_use:.0f}", delta_color="off")
        _m[2].metric(T("sb_weightforce"), f"{_force - _weight:.0f}", delta=f"{_force:.0f} / {_weight:.0f}", delta_color="off")
        _m[3].metric(T("sb_cargo_t"), f"{_tot.get('StorageUnits', 0):.0f}")
        _m2 = st.columns(4)
        _m2[0].metric(T("sb_hull"), f"{_tot.get('Hull', 0):.0f}")
        _m2[1].metric(T("sb_heat"), f"{_heatcap - _heatgen:.0f}", delta=f"{_heatcap:.0f} / {_heatgen:.0f}", delta_color="off")
        _m2[2].metric(T("sb_cost"), f"{_cost:.0f}")
        _m2[3].metric(T("sb_rawcost"), f"{_rawcost:.0f}")
        if _sup - _req < 0:
            st.warning(T("sb_bad_sys"))
        elif _weight > 0 and _force < _weight:
            st.warning(T("sb_bad_force"))
        elif _prod - _use < 0:
            st.warning(T("sb_bad_power"))
        else:
            st.success(T("sb_ok"))
        _am = build_data.attr_meta(sheets)
        _rows = [{T("sb_stat"): _am.get(k, (k, ""))[0] + (f" [{_am.get(k, ('', ''))[1]}]" if _am.get(k, ("", ""))[1] else ""),
                  T("sb_total"): round(v, 2)} for k, v in sorted(_tot.items()) if k in build_data.SHIP_KEYS]
        if _rows:
            st.dataframe(pd.DataFrame(_rows), hide_index=True, width="stretch")

# --- Onglet BASE BUILDER : planifier une base, bilan énergie/coût ---
if _sel == "tab_base":
    st.caption(T("base_help"))
    _bttr = sheet_translations(lang, "itemType")
    _bgroups = build_data.grouped(sheets, items, build_data.BASE_TYPES)
    _picks = []
    _bc = st.columns(3)
    for _n, _g in enumerate(_bgroups):
        with _bc[_n % 3]:
            _opts = _g["list"]
            for _s in st.multiselect(_bttr.get(_g["cat"]) or _g["cat"], range(len(_opts)),
                                     format_func=lambda i, o=_opts: f"{o[i]['name']}  ·  {o[i]['price']:.0f}",
                                     key="base_" + _g["cat"]):
                _picks.append(_opts[_s])
    if not _picks:
        st.info(T("base_help"))
    else:
        _dfq = pd.DataFrame([{T("sb_comp"): c["name"], T("sb_qty"): 1} for c in _picks])
        _ed = st.data_editor(_dfq, hide_index=True, width="stretch", disabled=[T("sb_comp")], key="base_qty",
                             column_config={T("sb_qty"): st.column_config.NumberColumn(min_value=0, step=1)})
        _chosen = []
        for _k, _c in enumerate(_picks):
            _q = int(_ed[T("sb_qty")].iloc[_k]) if _k < len(_ed) else 1
            _chosen += [_c] * max(_q, 0)
        _tot = build_data.sum_attrs(_chosen)
        _cost = sum(c["price"] for c in _chosen)
        _eoffer, _edem = _tot.get("EnergyOffer", 0), _tot.get("EnergyDemand", 0)
        _bpcap, _bpused = _tot.get("MaxBuildPoints", 0), _tot.get("BuildPointsCost", 0)
        _m = st.columns(4)
        _m[0].metric(T("bb_energy_net"), f"{_eoffer - _edem:.0f}", delta=f"{_eoffer:.0f} / {_edem:.0f}", delta_color="off")
        _m[1].metric(T("bb_buildpts"), f"{_bpcap - _bpused:.0f}", delta=f"{_bpcap:.0f} / {_bpused:.0f}", delta_color="off")
        _m[2].metric(T("bb_storage_t"), f"{_tot.get('SolidStorage', 0):.0f}")
        _m[3].metric(T("bb_buildcost"), f"{_cost:.0f}")
        if _eoffer - _edem < 0:
            st.warning(T("bb_bad_energy"))
        if _bpcap - _bpused < 0:
            st.warning(T("bb_bad_buildpts"))
        _am = build_data.attr_meta(sheets)
        _rows = [{T("sb_stat"): _am.get(k, (k, ""))[0] + (f" [{_am.get(k, ('', ''))[1]}]" if _am.get(k, ("", ""))[1] else ""),
                  T("sb_total"): round(v, 2)} for k, v in sorted(_tot.items()) if k in build_data.BASE_KEYS]
        if _rows:
            st.dataframe(pd.DataFrame(_rows), hide_index=True, width="stretch")

# --- Onglet PERMIS / TECH : 2 sous-vues (déblocage d'un item / arbre complet) ---
if _sel == "tab_permits":
    _ptr = sheet_translations(lang, "permit")
    _pnodes, _pedges, _item2p = permit_data.build_tree(sheets, items, _ptr)
    _pview = st.radio("permitview", ["permit_view_unlock", "permit_fam_tech", "permit_fam_corpo"],
                      format_func=T, horizontal=True, label_visibility="collapsed", key="permit_view")
    if _pview == "permit_view_unlock":
        st.caption(T("permit_help"))
        _unlockable = sorted(_item2p.keys(), key=lambda i: items.get(i, {}).get("name", i))
        _q = st.selectbox(T("permit_search"), ["—"] + _unlockable,
                          format_func=lambda i: "—" if i == "—" else items.get(i, {}).get("name", i), key="permit_q")
        if _q != "—":
            _r = permit_data.unlock_cost(_pnodes, _item2p, _q)
            if _r:
                st.success(T("permit_found").format(item=items.get(_q, {}).get("name", _q),
                                                    permit=_pnodes[_r["permit"]]["name"], total=_r["total"], n=len(_r["chain"])))
                st.dataframe(pd.DataFrame([{
                    T("permit_c_name"): _pnodes[p]["name"], T("permit_c_cost"): _pnodes[p]["cost"],
                    T("permit_c_unlocks"): ", ".join(_pnodes[p]["unlocks"][:6]) + (" …" if len(_pnodes[p]["unlocks"]) > 6 else "")}
                    for p in _r["chain"]]), hide_index=True, width="stretch",
                    column_config={T("permit_c_cost"): st.column_config.NumberColumn(format="%d")})
                components.html(permit_data.permit_html(_pnodes, _pedges, set(_r["chain"])), height=600)
            else:
                st.info(T("permit_none"))
    else:
        _want = "corpo" if _pview == "permit_fam_corpo" else "tech"
        _fnodes = {pid: d for pid, d in _pnodes.items() if d["family"] == _want}
        _fedges = [(a, b) for a, b in _pedges if a in _fnodes and b in _fnodes]
        components.html(permit_data.permit_html(_fnodes, _fedges, set()), height=720)

# --- Onglet CONTRATS / ÉCONOMIE : profit net = crédits − coût de production ---
if _sel == "tab_contracts":
    st.caption(T("contract_help"))
    _uc = graph_data.unit_costs(sheets, items)
    _all_ct = contract_data.contracts(sheets, items, _uc, sheet_translations(lang, "contract"))
    _clients = sorted({c["client"] for c in _all_ct if c["client"]})
    _fc = st.multiselect(T("ct_client"), _clients, key="ct_clientf")
    _maxlvl = max((c["level"] for c in _all_ct), default=1)
    _lvl = st.slider(T("ct_filter_lvl"), 1, int(_maxlvl), int(_maxlvl), key="ct_lvlf")
    _ct = [c for c in _all_ct if (not _fc or c["client"] in _fc) and c["level"] <= _lvl]
    st.dataframe(pd.DataFrame([{
        T("ct_name"): c["name"], T("ct_client"): c["client"], T("ct_level"): c["level"],
        T("ct_demand"): c["demand"], T("ct_credits"): c["credits"], T("ct_lp"): c["lp"],
        T("ct_cost"): c["cost"], T("ct_net"): c["net"]} for c in _ct]),
        hide_index=True, width="stretch", height=600,
        column_config={T("ct_credits"): st.column_config.NumberColumn(format="%d"),
                       T("ct_cost"): st.column_config.NumberColumn(format="%d"),
                       T("ct_net"): st.column_config.NumberColumn(format="%d")})

# --- Onglet ADMIN (visible uniquement par l'admin) : contributeurs + bannissements ---
if admin:
    if _sel == "tab_admin":
        st.caption(T("adm_help"))
        try:
            allrows = fetch_shared()
        except Exception:
            allrows = []

        # agrégation par contributeur (SteamID si dispo, sinon pseudo)
        agg = {}
        for r in allrows:
            aid = r.get("author_id") or ""
            key = aid or ("name:" + (r.get("author") or "anon"))
            a = agg.setdefault(key, {"id": aid, "name": r.get("author") or "?", "n": 0, "first": None, "last": None})
            a["n"] += 1
            ts = r.get("created_at")
            if ts:
                a["first"] = ts if not a["first"] else min(a["first"], ts)
                a["last"] = ts if not a["last"] else max(a["last"], ts)
        contribs = sorted(agg.values(), key=lambda x: -x["n"])

        st.subheader(T("adm_contributors"))
        if contribs:
            st.dataframe(pd.DataFrame([{T("adm_name"): c["name"], T("adm_id"): c["id"] or "—",
                                        T("adm_count"): c["n"], T("adm_first"): c["first"], T("adm_last"): c["last"]}
                                       for c in contribs]), hide_index=True, width="stretch")
            withid = [c for c in contribs if c["id"]]
            if withid:
                csel = st.selectbox(T("adm_pick"), range(len(withid)),
                                    format_func=lambda i: f'{withid[i]["name"]} ({withid[i]["id"]}) · {withid[i]["n"]}',
                                    key="adm_csel")
                tgt = withid[csel]
                b1, b2 = st.columns(2)
                if b1.button("🚫 " + T("adm_ban"), key="adm_ban_b"):
                    try:
                        cloud_store.ban(tgt["id"], tgt["name"]); fetch_bans_cached.clear()
                        st.success(T("adm_banned")); st.rerun()
                    except Exception as e:
                        st.error(f'{T("fail")} {e}')
                if b2.button("🗑️ " + T("adm_delall"), key="adm_delall_b"):
                    try:
                        cloud_store.delete_by_author(tgt["id"]); fetch_shared.clear()
                        st.success(T("mm_deleted")); st.rerun()
                    except Exception as e:
                        st.error(f'{T("fail")} {e}')
            else:
                st.caption(T("adm_noid"))
        else:
            st.info(T("adm_no_contrib"))

        st.divider()
        st.subheader(T("adm_bans"))
        bans = fetch_bans_cached()
        if bans:
            st.dataframe(pd.DataFrame([{T("adm_name"): b.get("name"), T("adm_id"): b.get("author_id"),
                                        T("adm_since"): b.get("created_at")} for b in bans]),
                         hide_index=True, width="stretch")
            bsel = st.selectbox(T("adm_pick_ban"), range(len(bans)),
                                format_func=lambda i: f'{bans[i].get("name")} ({bans[i].get("author_id")})', key="adm_bsel")
            if st.button("✅ " + T("adm_unban"), key="adm_unban_b"):
                try:
                    cloud_store.unban(bans[bsel].get("author_id")); fetch_bans_cached.clear()
                    st.success(T("adm_unbanned")); st.rerun()
                except Exception as e:
                    st.error(f'{T("fail")} {e}')
        else:
            st.caption(T("adm_no_ban"))
