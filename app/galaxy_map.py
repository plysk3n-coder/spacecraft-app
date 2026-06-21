# -*- coding: utf-8 -*-
"""Carte galactique interactive (onglet 🗺️ Carte).

Positions x/y RÉELLES des systèmes (app/haronex_routes.json, même source que spacecraft.tools)
+ routes FTL + enveloppes de secteur. Le détail ressources/planète vient de la base communautaire
(servi par un selectbox côté app — Streamlit ne capte pas le clic natif sur un nœud Plotly).

Rendu Plotly : zoom/pan/hover natifs. Aucune dépendance scipy (enveloppe convexe maison).
"""

# palette stable (l'ordre alphabétique des secteurs fixe la couleur -> reproductible entre runs)
_PALETTE = [
    "#e6194B", "#3cb44b", "#ffe119", "#4363d8", "#f58231", "#911eb4", "#42d4f4",
    "#f032e6", "#bfef45", "#fabed4", "#469990", "#dcbeff", "#9A6324", "#1abc9c",
    "#800000", "#aaffc3", "#808000", "#ffd8b1", "#000075", "#a9a9a9", "#e6beff",
    "#27ae60", "#e67e22", "#2980b9",
]


def sector_colors(sectors):
    """Couleur stable par secteur (tri alphabétique -> reproductible)."""
    return {s: _PALETTE[i % len(_PALETTE)] for i, s in enumerate(sorted(sectors))}


def _hull(points):
    """Enveloppe convexe (Andrew monotone chain). points = list[(x, y)] -> polygone ordonné."""
    pts = sorted(set(points))
    if len(pts) <= 2:
        return pts

    def cross(o, a, b):
        return (a[0] - o[0]) * (b[1] - o[1]) - (a[1] - o[1]) * (b[0] - o[0])

    lower = []
    for p in pts:
        while len(lower) >= 2 and cross(lower[-2], lower[-1], p) <= 0:
            lower.pop()
        lower.append(p)
    upper = []
    for p in reversed(pts):
        while len(upper) >= 2 and cross(upper[-2], upper[-1], p) <= 0:
            upper.pop()
        upper.append(p)
    return lower[:-1] + upper[:-1]


def _rgba(hexc, a):
    h = hexc.lstrip("#")
    return f"rgba({int(h[0:2], 16)},{int(h[2:4], 16)},{int(h[4:6], 16)},{a})"


def build_figure(rd, node_meta, colors, focus_sector=None, highlight=None, route=None, height=720):
    """rd = haronex_routes.json (systems/edges). node_meta = {sid: {hover:str, disc:bool}}.
    colors = {sector: hex}. focus_sector = secteur à isoler (zoom) ou None.
    highlight = set de sids à mettre en avant (filtre ressource) ; les autres sont estompés.
    route = liste ordonnée de sids (chemin FTL à tracer) ou None.
    None = pas de filtre (rendu par secteur, cerclé si découvertes)."""
    import plotly.graph_objects as go

    systems = rd["systems"]
    show = {sid: s for sid, s in systems.items()
            if s.get("x") is not None
            and (not focus_sector or s.get("sector") == focus_sector)}
    # une route doit rester entièrement visible même si elle sort du secteur filtré
    for sid in (route or []):
        if sid in systems and systems[sid].get("x") is not None and sid not in show:
            show[sid] = systems[sid]
    fig = go.Figure()

    # 1) routes FTL (arêtes) — une seule trace, lignes grises fines
    ex, ey = [], []
    for s, d, _c in rd["edges"]:
        if s in show and d in show:
            ex += [show[s]["x"], show[d]["x"], None]
            ey += [show[s]["y"], show[d]["y"], None]
    if ex:
        fig.add_trace(go.Scatter(x=ex, y=ey, mode="lines", hoverinfo="skip",
                                 line=dict(color="rgba(140,140,160,0.18)", width=1),
                                 showlegend=False))

    # 2) enveloppes de secteur (polygone rempli, faible opacité) + label au centroïde
    by_sec = {}
    for sid, s in show.items():
        by_sec.setdefault(s.get("sector") or "?", []).append((s["x"], s["y"]))
    lx, ly, lt = [], [], []
    for sec, pts in by_sec.items():
        col = colors.get(sec, "#888888")
        hull = _hull(pts)
        if len(hull) >= 3:
            hx = [p[0] for p in hull] + [hull[0][0]]
            hy = [p[1] for p in hull] + [hull[0][1]]
            fig.add_trace(go.Scatter(x=hx, y=hy, mode="lines", fill="toself",
                                     fillcolor=_rgba(col, 0.07),
                                     line=dict(color=_rgba(col, 0.55), width=1.5),
                                     hoverinfo="skip", showlegend=False))
        lx.append(sum(p[0] for p in pts) / len(pts))
        ly.append(sum(p[1] for p in pts) / len(pts))
        lt.append(sec)
    if lx:
        fig.add_trace(go.Scatter(x=lx, y=ly, mode="text", text=lt,
                                 textfont=dict(color="rgba(230,230,230,0.55)", size=12),
                                 hoverinfo="skip", showlegend=False))

    hl = highlight  # None = pas de filtre ; sinon set de sids à mettre en avant
    # 3a) systèmes ESTOMPÉS (hors filtre ressource) — une seule trace grise
    if hl is not None:
        dx, dy, dt = [], [], []
        for sid, s in show.items():
            if sid in hl:
                continue
            dx.append(s["x"]); dy.append(s["y"])
            dt.append(node_meta.get(sid, {}).get("hover") or s["name"])
        if dx:
            fig.add_trace(go.Scatter(x=dx, y=dy, mode="markers", showlegend=False,
                                     marker=dict(size=5, color="rgba(120,120,135,0.30)"),
                                     hovertext=dt, hovertemplate="%{hovertext}<extra></extra>"))
    # 3b) systèmes MIS EN AVANT (ou tous si pas de filtre) — une trace par secteur (légende).
    for sec in sorted(by_sec):
        col = colors.get(sec, "#888888")
        xs, ys, sizes, widths, texts = [], [], [], [], []
        for sid, s in show.items():
            if (s.get("sector") or "?") != sec:
                continue
            if hl is not None and sid not in hl:
                continue
            m = node_meta.get(sid, {})
            xs.append(s["x"]); ys.append(s["y"])
            if hl is not None:
                sizes.append(13); widths.append(2)              # correspond au filtre
            else:
                disc = m.get("disc")
                sizes.append(12 if disc else 6); widths.append(2 if disc else 0)
            texts.append(m.get("hover") or s["name"])
        if not xs:
            continue
        fig.add_trace(go.Scatter(
            x=xs, y=ys, mode="markers", name=sec,
            marker=dict(size=sizes, color=col,
                        line=dict(color="rgba(255,255,255,0.9)", width=widths)),
            hovertext=texts, hovertemplate="%{hovertext}<extra></extra>"))

    # 4) route FTL tracée par-dessus (chemin du planificateur) : ligne dorée + départ/arrivée
    rt = [sid for sid in (route or []) if sid in systems and systems[sid].get("x") is not None]
    if len(rt) >= 2:
        rx, ry = [], []
        for a, b in zip(rt, rt[1:]):
            rx += [systems[a]["x"], systems[b]["x"], None]
            ry += [systems[a]["y"], systems[b]["y"], None]
        fig.add_trace(go.Scatter(x=rx, y=ry, mode="lines", hoverinfo="skip", showlegend=False,
                                 line=dict(color="#ffd000", width=3)))
    if rt:
        nx = [systems[s]["x"] for s in rt]
        ny = [systems[s]["y"] for s in rt]
        nt = [systems[s]["name"] for s in rt]
        nc = ["#2ecc71" if i == 0 else ("#e74c3c" if i == len(rt) - 1 else "#ffd000")
              for i in range(len(rt))]
        fig.add_trace(go.Scatter(x=nx, y=ny, mode="markers", showlegend=False,
                                 marker=dict(size=15, color=nc, line=dict(color="#000", width=1.5)),
                                 hovertext=nt, hovertemplate="%{hovertext}<extra></extra>"))

    fig.update_layout(
        height=height, paper_bgcolor="#0e1117", plot_bgcolor="#0e1117",
        dragmode="pan",  # clic-gauche = déplacer (le zoom reste à la molette via scrollZoom)
        margin=dict(l=0, r=0, t=0, b=0),
        legend=dict(font=dict(color="#ddd", size=11), bgcolor="rgba(0,0,0,0)",
                    itemsizing="constant"),
        hoverlabel=dict(bgcolor="#1a1d27", font=dict(color="#eee"), align="left"))
    fig.update_xaxes(visible=False, showgrid=False, zeroline=False)
    # y inversé = orientation écran de spacecraft.tools ; ratio 1:1 = pas de distorsion
    fig.update_yaxes(visible=False, showgrid=False, zeroline=False,
                     autorange="reversed", scaleanchor="x", scaleratio=1)
    return fig
