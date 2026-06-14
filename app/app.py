# -*- coding: utf-8 -*-
import os, sys
import pandas as pd
import streamlit as st

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import streamlit.components.v1 as components
import cdb_model
import extract_cdb
import i18n
import graph_data
import world_data

st.set_page_config(page_title="SpaceCraft - Rentabilite", page_icon="🚀", layout="wide")


@st.cache_data(show_spinner=False)
def load_sheets():
    return cdb_model.load_cdb()


@st.cache_data(show_spinner=False)
def load_world():
    return world_data.build_world(cdb_model.load_cdb())


@st.cache_data(show_spinner=False)
def load(overrides_key, lang):
    sheets = cdb_model.load_cdb()
    tr = i18n.load_translations(lang)
    items, recipes = cdb_model.build(sheets, price_overrides=dict(overrides_key), tr=tr)
    return items, recipes


# --- langue d'abord (la sidebar est evaluee avant le corps) ---
with st.sidebar:
    langs = i18n.available_langs()
    lang = st.selectbox(i18n.t("language", "en"), langs, format_func=lambda c: i18n.LANGS.get(c, c))
T = lambda k: i18n.t(k, lang)

st.title(T("title"))
st.caption(T("caption"))

# --- reste de la sidebar ---
with st.sidebar:
    st.header(T("settings"))
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

tab1, tab2, tab3, tab4, tab5 = st.tabs([T("tab_recipes"), T("tab_items"), T("tab_craftmap"), T("tab_universe"), T("tab_where")])

with tab1:
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

with tab2:
    qi = st.text_input(T("search_item"))
    di = pd.DataFrame([{T("col_itemname"): v["name"], T("col_price"): v["price"],
                        T("col_type"): v["type"], T("col_loot"): v["lootLevel"]} for v in items.values()])
    if qi:
        di = di[di[T("col_itemname")].str.lower().str.contains(qi.lower())]
    di = di.sort_values(T("col_price"), ascending=False)
    st.write(f'**{len(di)} {T("n_items")}**')
    st.dataframe(di, width="stretch", height=600, hide_index=True,
                 column_config={T("col_price"): st.column_config.NumberColumn(format="%.2f")})

with tab3:
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
        rows = graph_data.craft_tree_rows(sheets, items, sel_prod, max_depth=depth)
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

with tab4:
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
        components.html(graph_data.to_html(nodes, edges, height="640px", hierarchical=True, direction="UD"), height=660)

with tab5:
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
