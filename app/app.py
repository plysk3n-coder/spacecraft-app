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
def load(overrides_key, lang):
    sheets = cdb_model.load_cdb()
    tr = i18n.load_translations(lang)
    items, recipes = cdb_model.build(sheets, price_overrides=dict(overrides_key), tr=tr)
    return items, recipes


@st.cache_data(ttl=20, show_spinner=False)
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
# temps de craft auto par produit (recette de BASE en priorité) pour le plan d'usine
_product_time = {}
for _r in recipes:
    if _r.get("unlock") == "Permit":
        _product_time.setdefault(_r["product_id"], (_r.get("t_auto") or 0, _r.get("out_qty") or 1, _r.get("station") or "", _r.get("power") or 0))
for _r in recipes:  # fallback : produits sans recette de base
    _product_time.setdefault(_r["product_id"], (_r.get("t_auto") or 0, _r.get("out_qty") or 1, _r.get("station") or "", _r.get("power") or 0))

# --- données partagées entre onglets : gisements + carte de découvertes ---
_world0 = load_world()
deposits = _world0.get("deposits", {})
_rtr = res_translations(lang)
dep_name = lambda d: _rtr.get(d) or deposits.get(d, {}).get("name", d)
# nom d'affichage : ressource traduite (n'importe quel id de la table resource) ; sinon item (compat) ; sinon id brut
resname = lambda x: _rtr.get(x) or items.get(x, {}).get("name", x)
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
is_poi = lambda x: isinstance(x, str) and x.startswith("POI:")
poiname = lambda x: _poitr.get(x[4:], x[4:]) if is_poi(x) else (_poitr.get(x, x))
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
_keys = ["tab_where", "tab_deposits", "tab_mymap", "tab_poi", "tab_universe",
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

if _sel == "tab_craftmap":
    st.caption(T("craftmap_help"))
    sheets = load_sheets()
    prods = graph_data.craftable_products(sheets, items)
    plabel = {i: items.get(i, {}).get("name", i) for i in prods}
    cc = st.columns([3, 1, 1, 1.2])
    sel_prod = cc[0].selectbox(T("select_product"), prods, format_func=lambda i: plabel.get(i, i))
    depth = cc[1].slider(T("depth"), 1, 8, 4)
    qtymake = cc[2].number_input(T("make_qty"), min_value=1, value=1, step=1)
    cmode = cc[3].radio(T("view"), ["v_table", "v_graph"], format_func=T, key="cmode")

    if cmode == "v_table":
        rows = graph_data.craft_tree_rows(sheets, items, sel_prod, qty=qtymake, max_depth=depth)
        dft = pd.DataFrame([{
            T("col_comp"): (("　" * (r["depth"] - 1) + "└ ") if r["depth"] else "") + r["name"],
            T("col_qty2"): r["qty"], T("col_price"): r["price"], T("col_station"): r["station"]}
            for r in rows])
        st.dataframe(dft, hide_index=True, width="stretch", height=430,
                     column_config={T("col_price"): st.column_config.NumberColumn(format="%.2f")})
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
        T("fac_c_machines"): r["machines"] if r["machines"] is not None else "—",
        T("fac_c_mrate"): r["machine_rate"] if r["machine_rate"] is not None else "—",
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
    if umode == "v_table":
        urows = graph_data.universe_tree_rows(sheets, world=world, items=items)
        dfu = pd.DataFrame([{
            T("col_place"): ("　" * r["depth"] + ("└ " if r["depth"] else "")) + r["name"],
            T("col_type"): r["kind"], T("col_detail"): r["extra"]} for r in urows])
        st.dataframe(dfu, hide_index=True, width="stretch", height=600)
    else:
        nodes, edges = graph_data.universe_graph(sheets, world=world, items=items, res_label=T("u_resources"))
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
            st.dataframe(pd.DataFrame([{T("col_deposit"): s["name"], T("col_type"): s["type"],
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
        res_names = {s["res"]: s["name"] for s in srcs if s.get("res")}
        _abund = discoveries.abundance_map(fetch_shared()) if shared else {}
        found = []
        for rid, dname in res_names.items():
            for rg, sy, pl in discoveries.find_resource(map_data, rid):
                a = _abund.get((rg, sy, pl, rid), {})
                found.append({T("col_sector"): rg, T("col_system"): sy,
                              T("col_planet"): pl, T("col_deposit"): dname,
                              T("col_count"): a.get("count"), T("col_density"): a.get("density")})
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
        if _sel_names:
            _abund = discoveries.abundance_map(fetch_shared()) if shared else {}
            _rows = []
            for nm in _sel_names:
                rid = _lab[nm]
                for rg, sy, pl in discoveries.find_resource(map_data, rid):
                    if _secf and rg not in _secf:
                        continue
                    a = _abund.get((rg, sy, pl, rid), {})
                    _rows.append({T("col_deposit"): nm, T("col_sector"): rg, T("col_system"): sy,
                                  T("col_planet"): pl, T("col_count"): a.get("count"),
                                  T("col_density"): a.get("density")})
            if _rows:
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

if _sel == "tab_mymap":
    if shared:
        st.success(T("mm_shared_on"))
        if map_err:
            st.error(f'{T("mm_shared_err")} {map_err}')
    else:
        st.info(T("mm_local_note"))
    data, load_err = map_data, map_err

    # identité de l'auteur en mode partagé : login Steam (écriture gatée)
    author, author_id = "", ""
    if shared:
        if steam_auth.configured():
            user = steam_auth.current_user()
            if user:
                ci, co = st.columns([5, 1])
                _badge = f'🎮 {T("mm_steam_as")} **{user["name"]}**'
                _badge += "  ·  🛠️ admin" if steam_auth.is_admin(user) else f'  ·  SteamID `{user.get("id")}`'
                ci.success(_badge)
                if co.button(T("mm_logout"), key="mm_logout_b"):
                    steam_auth.logout()
                    try:
                        cookies.delete(AUTH_COOKIE)
                    except Exception:
                        pass
                    st.rerun()
                if user.get("id") in banned_ids:
                    st.error(T("mm_banned"))  # banni -> author reste vide -> écriture bloquée
                else:
                    author, author_id = user["name"], user.get("id")
            else:
                st.link_button("🎮 " + T("mm_steam_login"), steam_auth.login_url())
                st.caption(T("mm_need_login"))
        else:
            st.warning(T("mm_steam_required"))

    # --- Ajout d'une découverte ---
    st.subheader(T("mymap_add"))
    regions_known = sorted(data["regions"].keys())
    sectors_cdb = sorted(set(w["sector_name"].values()))
    region_opts = regions_known + [s for s in sectors_cdb if s not in regions_known]

    # région/système mémorisés dans l'URL (survivent au F5) -> index par défaut des listes
    _qp = st.query_params
    def _idx(opts, val):
        return opts.index(val) if val in opts else 0

    c1, c2, c3 = st.columns(3)
    with c1:
        ropts = ["—"] + region_opts
        rsel = st.selectbox(T("mm_region"), ropts, index=_idx(ropts, _qp.get("rg", "")), key="mm_region_sel")
        rnew = st.text_input(T("mm_region_new"), key="mm_region_new")
        region = rnew.strip() or ("" if rsel == "—" else rsel)
    _cdb_uni = _world0.get("named_universe", {})
    with c2:
        comm_sys = data["regions"].get(region, {}).get("systems", {}).keys() if region else []
        cdb_sys = _cdb_uni.get(region, {}).keys() if region else []
        sys_known = sorted(set(comm_sys) | set(cdb_sys))
        sopts = ["—"] + sys_known
        ssel = st.selectbox(T("mm_system"), sopts, index=_idx(sopts, _qp.get("sy", "")), key="mm_system_sel")
        snew = st.text_input(T("mm_system_new"), key="mm_system_new")
        system = snew.strip() or ("" if ssel == "—" else ssel)
    with c3:
        comm_pl = data["regions"].get(region, {}).get("systems", {}).get(system, {}).get("planets", {}).keys() if (region and system) else []
        cdb_pl = _cdb_uni.get(region, {}).get(system, []) if (region and system) else []
        pl_known = sorted(set(comm_pl) | set(cdb_pl))
        psel = st.selectbox(T("mm_planet"), ["—"] + pl_known, key="mm_planet_sel")
        pnew = st.text_input(T("mm_planet_new"), key="mm_planet_new")
        planet = pnew.strip() or ("" if psel == "—" else psel)

    # mémorise région/système choisis dans l'URL (sans forcer de rerun si inchangé)
    if region and _qp.get("rg") != region:
        _qp["rg"] = region
    if system and _qp.get("sy") != system:
        _qp["sy"] = system

    res_sel = st.multiselect(T("mm_resources"), dep_ids, format_func=dep_name, key="mm_res")
    poi_sel = st.multiselect(T("mm_pois"), poi_ids, format_func=poiname, key="mm_poi")
    _all_sel = res_sel + poi_sel
    if st.button(T("mm_addbtn"), type="primary"):
        if shared and not author:
            st.warning(T("mm_need_login") if steam_auth.configured() else T("mm_steam_required"))
        elif region and system and planet:
            try:
                if shared:
                    cloud_store.add(region, system, planet, _all_sel, author, author_id=author_id)
                    fetch_shared.clear()
                else:
                    discoveries.add_resources(data, region, system, planet, _all_sel)
                    discoveries.save(data)
                st.success(T("mm_added"))
                st.rerun()
            except Exception as e:
                st.error(f'{T("fail")} {e}')
        else:
            st.warning(T("mm_need"))

    # --- Journal (arbre) ---
    st.divider()
    st.subheader(T("mymap_log_shared") if shared else T("mymap_log"))
    rws = discoveries.rows(data)
    if not rws:
        if not load_err:
            st.info(T("mm_empty"))
    else:
        def _dep_disp(d):
            ys = dep_yield(d)
            return resname(d) + (f" → {', '.join(ys[:4])}{'…' if len(ys) > 4 else ''}" if ys else "")

        dfm = pd.DataFrame([{
            T("col_place"): ("　" * r["depth"] + ("└ " if r["depth"] else "")) + r["name"],
            T("mm_col_kind"): T("mm_k_" + r["kind"]),
            T("mm_col_res"): " · ".join(_dep_disp(x) for x in r["resources"] if not is_poi(x)) if r["kind"] == "planet" else "",
            T("mm_col_poi"): " · ".join(poiname(x) for x in r["resources"] if is_poi(x)) if r["kind"] == "planet" else "",
        } for r in rws])
        st.dataframe(dfm, hide_index=True, width="stretch", height=380)

        # --- Recherche "où ai-je trouvé X" ---
        st.subheader(T("mm_search"))
        found = sorted(discoveries.all_resource_ids(data), key=itemname)
        if found:
            q = st.selectbox(T("mm_search_res"), ["—"] + found,
                             format_func=lambda i: "—" if i == "—" else itemname(i), key="mm_qres")
            if q != "—":
                hits = discoveries.find_resource(data, q)
                st.dataframe(pd.DataFrame([{T("mm_region2"): rg, T("mm_system2"): sy, T("mm_planet2"): pl}
                                           for rg, sy, pl in hits]), hide_index=True, width="stretch")

        # --- Supprimer une planète (chacun ses entrées en mode partagé) ---
        with st.expander(T("mm_del")):
            triples = []
            for rg, rgd in data["regions"].items():
                for sy, syd in rgd.get("systems", {}).items():
                    for pl in syd.get("planets", {}):
                        triples.append((rg, sy, pl))
            if triples and shared and not author:
                st.caption(T("mm_need_login"))
            elif triples:
                if shared:
                    st.caption(T("mm_del_shared_note"))
                dsel = st.selectbox(" ", range(len(triples)), key="mm_delsel",
                                    format_func=lambda i: f"{triples[i][0]} › {triples[i][1]} › {triples[i][2]}")
                if st.button(T("mm_delbtn"), key="mm_delbtn_b"):
                    rg, sy, pl = triples[dsel]
                    try:
                        if shared:
                            cloud_store.delete_planet(rg, sy, pl, author or "anon")
                            fetch_shared.clear()
                        else:
                            discoveries.remove_planet(data, rg, sy, pl)
                            discoveries.save(data)
                        st.success(T("mm_deleted"))
                        st.rerun()
                    except Exception as e:
                        st.error(f'{T("fail")} {e}')

        # --- Menu ADMIN (visible uniquement par l'admin) : supprimer n'importe quoi ---
        if shared and steam_auth.is_admin(st.session_state.get("steam_user")):
            with st.expander("🛠️ " + T("mm_admin"), expanded=False):
                st.caption(T("mm_admin_note"))
                targets = []  # (libellé, filtres)
                for rg, rgd in data["regions"].items():
                    targets.append((f'[{T("mm_k_region")}] {rg}', {"region": rg}))
                    for sy, syd in rgd.get("systems", {}).items():
                        targets.append((f'[{T("mm_k_system")}] {rg} › {sy}', {"region": rg, "system": sy}))
                        for pl in syd.get("planets", {}):
                            targets.append((f'[{T("mm_k_planet")}] {rg} › {sy} › {pl}',
                                            {"region": rg, "system": sy, "planet": pl}))
                asel = st.selectbox(T("mm_admin_target"), range(len(targets)),
                                    format_func=lambda i: targets[i][0], key="mm_admin_sel")
                _filters = targets[asel][1]
                _level = "planet" if "planet" in _filters else ("system" if "system" in _filters else "region")

                ca, cb = st.columns(2)
                # Renommer (UPDATE sur le champ le plus profond du filtre)
                newname = ca.text_input(T("mm_admin_rename"), value=_filters[_level], key="mm_admin_newname")
                if ca.button("✏️ " + T("mm_admin_renamebtn"), key="mm_admin_ren_b"):
                    nn = newname.strip()
                    if nn and nn != _filters[_level]:
                        try:
                            n_upd = cloud_store.update_where(_filters, {_level: nn})
                            if n_upd:
                                fetch_shared.clear()
                                st.success(f'{T("mm_renamed")} ({n_upd})')
                                st.rerun()
                            else:
                                st.warning(T("mm_update_none"))
                        except Exception as e:
                            st.error(f'{T("fail")} {e}')
                # Supprimer
                if cb.button("🗑️ " + T("mm_admin_del"), key="mm_admin_del_b", type="primary"):
                    try:
                        cloud_store.delete_where(**_filters)
                        fetch_shared.clear()
                        st.success(T("mm_deleted"))
                        st.rerun()
                    except Exception as e:
                        st.error(f'{T("fail")} {e}')

    # --- Export (sauvegarde) + Import (local seulement) ---
    st.divider()
    ce, ci = st.columns(2)
    ce.download_button(T("mm_export"), data=json.dumps(data, ensure_ascii=False, indent=2),
                       file_name="my_discoveries.json", mime="application/json")
    if not shared:
        up = ci.file_uploader(T("mm_import"), type="json", key="mm_up")
        if up is not None:
            try:
                newd = json.load(up)
                discoveries.save(newd)
                st.success(T("mm_imported"))
                st.rerun()
            except Exception as e:
                st.error(f'{T("fail")} {e}')


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
