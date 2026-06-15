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
def load_world(_schema_v=3):  # _schema_v : bump pour invalider le cache quand world_data change
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
                    extract_cdb.extract_all(langs=("fr",))
                    st.cache_data.clear()
                    st.success(T("reextracted"))
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
    if _nm not in _by_nm or _better(_d, _by_nm[_nm]):
        _by_nm[_nm] = _d
dep_ids = sorted(_by_nm.values(), key=dep_name)
# ce que produit un gisement (noms d'items traduits)
dep_yield = lambda d: [items.get(i, {}).get("name", i) for i in deposits.get(d, {}).get("items", [])]

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
_keys = ["tab_recipes", "tab_items", "tab_craftmap", "tab_universe", "tab_where", "tab_mymap"]
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
        d = d[d["product"].str.lower().str.contains(ql) | d["inputs_str"].str.lower().str.contains(ql)]
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
    st.dataframe(di, width="stretch", height=600, hide_index=True,
                 column_config={T("col_price"): st.column_config.NumberColumn(format="%.2f")})

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
                    ttl = pl + ((" — " + ", ".join(dep_name(d) for d in deps)) if deps else "")
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
    if not srcs and not secs:
        st.info(T("where_none"))
    else:
        ca, cb = st.columns(2)
        with ca:
            st.subheader(T("where_mined"))
            st.dataframe(pd.DataFrame([{T("col_deposit"): s["name"], T("col_type"): s["type"],
                                        T("col_tier"): s["tier"], T("col_proba"): s["proba"]} for s in srcs]),
                         hide_index=True, width="stretch")
        with cb:
            st.subheader(T("where_sectors"))
            def _req(sid):
                r = w["sector_req"].get(sid) or []
                return ", ".join(f'{x.get("attribute")} {x.get("level")}' for x in r) or "-"
            st.dataframe(pd.DataFrame([{T("col_sector"): w["sector_name"].get(s, s),
                                        T("col_reslevel"): w["sector_reslevel"].get(s), T("col_req"): _req(s)}
                                       for s in secs]), hide_index=True, width="stretch")

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
    if st.button(T("mm_addbtn"), type="primary"):
        if shared and not author:
            st.warning(T("mm_need_login") if steam_auth.configured() else T("mm_steam_required"))
        elif region and system and planet:
            try:
                if shared:
                    cloud_store.add(region, system, planet, res_sel, author, author_id=author_id)
                    fetch_shared.clear()
                else:
                    discoveries.add_resources(data, region, system, planet, res_sel)
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
            T("mm_col_res"): " · ".join(_dep_disp(x) for x in r["resources"]) if r["kind"] == "planet" else "",
        } for r in rws])
        st.dataframe(dfm, hide_index=True, width="stretch", height=380)

        # --- Recherche "où ai-je trouvé X" ---
        st.subheader(T("mm_search"))
        found = sorted(discoveries.all_resource_ids(data), key=resname)
        if found:
            q = st.selectbox(T("mm_search_res"), ["—"] + found,
                             format_func=lambda i: "—" if i == "—" else resname(i), key="mm_qres")
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
