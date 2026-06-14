# -*- coding: utf-8 -*-
"""Traductions depuis export_<code>.xml (extrait du pak). EN = langue de base (cdb).

Structure XML : <cdb><sheet name="item"><IronOre><name>Minerai de fer</name></IronOre>...
Pour chaque sheet, on construit {id_ligne: texte_traduit} en prenant <name> sinon <title>.
"""
import os
import xml.etree.ElementTree as ET

LANG_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "extracted")

LANGS = {"en": "English", "fr": "Français"}  # EN = base (pas de XML), FR = export_fr.xml


def available_langs():
    out = ["en"]
    for code in LANGS:
        if code != "en" and os.path.exists(os.path.join(LANG_DIR, f"export_{code}.xml")):
            out.append(code)
    return out


# --- Textes de l'interface (menus, titres, colonnes) ---
UI = {
    "title":        {"fr": "🚀 SpaceCraft — Rentabilité du craft", "en": "🚀 SpaceCraft — Craft profitability"},
    "caption":      {"fr": "Données extraites du jeu (data.cdb). VA = prix de vente des sorties − prix des entrées. Le temps de craft (et VA/h) est une estimation à confirmer in-game.",
                     "en": "Data extracted from the game (data.cdb). VA = sell value of outputs − value of inputs. Craft time (and VA/h) is an estimate to confirm in-game."},
    "settings":     {"fr": "⚙️ Paramètres", "en": "⚙️ Settings"},
    "language":     {"fr": "🌐 Langue / Language", "en": "🌐 Language / Langue"},
    "reextract":    {"fr": "🔄 Ré-extraire depuis le jeu", "en": "🔄 Re-extract from game"},
    "reextract_help": {"fr": "Relance l'extraction des données + traductions (après un patch)", "en": "Re-run data + translation extraction (after a patch)"},
    "reextracted":  {"fr": "Ré-extrait (données + traductions).", "en": "Re-extracted (data + translations)."},
    "fail":         {"fr": "Échec :", "en": "Failed:"},
    "adjust_price": {"fr": "💰 Ajuster un prix", "en": "💰 Adjust a price"},
    "adjust_help":  {"fr": "Ex : prix réel d'achat d'un item (le Gel), pour recalculer la marge.", "en": "E.g. real buy price of an item (the Gel), to recompute the margin."},
    "item":         {"fr": "Item", "en": "Item"},
    "new_price":    {"fr": "Nouveau prix pour", "en": "New price for"},
    "apply":        {"fr": "Appliquer", "en": "Apply"},
    "reset_all":    {"fr": "Tout réinitialiser", "en": "Reset all"},
    "modified":     {"fr": "**Prix modifiés :**", "en": "**Modified prices:**"},
    "tab_recipes":  {"fr": "📈 Recettes (rentabilité)", "en": "📈 Recipes (profitability)"},
    "tab_items":    {"fr": "📦 Items & prix", "en": "📦 Items & prices"},
    "tab_craftmap": {"fr": "🕸️ Chaînes de craft", "en": "🕸️ Craft chains"},
    "tab_universe": {"fr": "🌌 Univers", "en": "🌌 Universe"},
    "tab_where":    {"fr": "🔍 Où trouver", "en": "🔍 Where to find"},
    "tab_mymap":    {"fr": "🗺️ Ma carte", "en": "🗺️ My map"},
    "mymap_help":   {"fr": "Ton carnet de découvertes (privé, enregistré localement sur ton PC). Le monde étant généré procéduralement, ces infos ne sont pas dans le jeu extrait : ajoute-les au fil de l'exploration. Région → Système → Planète → ressources.",
                     "en": "Your discovery log (private, saved locally on your PC). The world is procedurally generated so this isn't in the extracted data: add it as you explore. Region → System → Planet → resources."},
    "mymap_add":    {"fr": "➕ Ajouter une découverte", "en": "➕ Add a discovery"},
    "mymap_log":    {"fr": "📒 Mes découvertes", "en": "📒 My discoveries"},
    "mm_region":    {"fr": "Région (existante)", "en": "Region (existing)"},
    "mm_region_new":{"fr": "…ou nouvelle région", "en": "…or new region"},
    "mm_system":    {"fr": "Système (existant)", "en": "System (existing)"},
    "mm_system_new":{"fr": "…ou nouveau système", "en": "…or new system"},
    "mm_planet":    {"fr": "Planète (existante)", "en": "Planet (existing)"},
    "mm_planet_new":{"fr": "…ou nouvelle planète", "en": "…or new planet"},
    "mm_resources": {"fr": "Ressources trouvées sur cette planète", "en": "Resources found on this planet"},
    "mm_addbtn":    {"fr": "💾 Enregistrer", "en": "💾 Save"},
    "mm_added":     {"fr": "Découverte enregistrée.", "en": "Discovery saved."},
    "mm_need":      {"fr": "Renseigne au moins une région, un système et une planète.", "en": "Provide at least a region, a system and a planet."},
    "mm_empty":     {"fr": "Aucune découverte enregistrée pour l'instant.", "en": "No discoveries logged yet."},
    "mm_col_kind":  {"fr": "Type", "en": "Type"},
    "mm_col_res":   {"fr": "Ressources", "en": "Resources"},
    "mm_k_region":  {"fr": "🟣 Région", "en": "🟣 Region"},
    "mm_k_system":  {"fr": "🟢 Système", "en": "🟢 System"},
    "mm_k_planet":  {"fr": "🔵 Planète", "en": "🔵 Planet"},
    "mm_search":    {"fr": "🔎 Où ai-je trouvé…", "en": "🔎 Where did I find…"},
    "mm_search_res":{"fr": "Ressource", "en": "Resource"},
    "mm_region2":   {"fr": "Région", "en": "Region"},
    "mm_system2":   {"fr": "Système", "en": "System"},
    "mm_planet2":   {"fr": "Planète", "en": "Planet"},
    "mm_export":    {"fr": "⬇️ Exporter (sauvegarde)", "en": "⬇️ Export (backup)"},
    "mm_import":    {"fr": "⬆️ Importer un fichier", "en": "⬆️ Import a file"},
    "mm_imported":  {"fr": "Découvertes importées.", "en": "Discoveries imported."},
    "mm_del":       {"fr": "🗑️ Supprimer une planète", "en": "🗑️ Delete a planet"},
    "mm_delbtn":    {"fr": "Supprimer", "en": "Delete"},
    "mm_deleted":   {"fr": "Planète supprimée.", "en": "Planet deleted."},
    "mm_shared_on": {"fr": "🌍 Carte communautaire active — tes ajouts sont partagés avec tous les joueurs.",
                     "en": "🌍 Community map active — your entries are shared with all players."},
    "mm_shared_err":{"fr": "Impossible de joindre la base communautaire :", "en": "Could not reach the community database:"},
    "mm_local_note":{"fr": "Mode local (privé sur ton PC). La carte communautaire s'activera dès que Supabase sera configuré.",
                     "en": "Local mode (private on your PC). The community map activates once Supabase is configured."},
    "mm_pseudo":    {"fr": "Ton pseudo (pour signer tes découvertes)", "en": "Your nickname (to sign your discoveries)"},
    "mm_need_pseudo": {"fr": "Indique d'abord ton pseudo.", "en": "Enter your nickname first."},
    "mymap_log_shared": {"fr": "🌍 Découvertes de la communauté", "en": "🌍 Community discoveries"},
    "mm_del_shared_note": {"fr": "Tu ne peux supprimer que les planètes que TU as ajoutées (avec ce pseudo).",
                           "en": "You can only delete planets YOU added (with this nickname)."},
    "mm_steam_login": {"fr": "Se connecter avec Steam", "en": "Sign in through Steam"},
    "mm_steam_as":  {"fr": "Connecté en tant que", "en": "Signed in as"},
    "mm_logout":    {"fr": "Déconnexion", "en": "Sign out"},
    "mm_need_login":{"fr": "Connecte-toi avec Steam pour contribuer à la carte.", "en": "Sign in through Steam to contribute to the map."},
    "mm_steam_required": {"fr": "👀 Lecture libre pour tous. ✍️ L'écriture nécessite la connexion Steam (pas encore configurée).",
                          "en": "👀 Reading is open to all. ✍️ Writing requires Steam sign-in (not configured yet)."},
    "where_help":   {"fr": "Choisis un minerai/une ressource → les gisements qui le donnent et les secteurs où chercher.",
                     "en": "Pick an ore/resource → the deposits that drop it and the sectors to search."},
    "select_res":   {"fr": "Minerai / ressource", "en": "Ore / resource"},
    "where_mined":  {"fr": "⛏️ Extrait des gisements", "en": "⛏️ Mined from deposits"},
    "where_sectors":{"fr": "🌌 Secteurs où chercher", "en": "🌌 Sectors to search"},
    "where_none":   {"fr": "Pas de source de minage dans les données (item crafté, loot, ou procédural).",
                     "en": "No mining source in the data (crafted item, loot, or procedural)."},
    "col_deposit":  {"fr": "Gisement", "en": "Deposit"},
    "col_tier":     {"fr": "Tier", "en": "Tier"},
    "col_proba":    {"fr": "Proba %", "en": "Chance %"},
    "col_sector":   {"fr": "Secteur", "en": "Sector"},
    "col_reslevel": {"fr": "Niv. ressources", "en": "Res. level"},
    "col_req":      {"fr": "Exploration requise", "en": "Exploration req."},
    "u_resources":  {"fr": "Ressources", "en": "Resources"},
    "select_product": {"fr": "Produit à analyser", "en": "Product to analyze"},
    "depth":        {"fr": "Profondeur de la chaîne", "en": "Chain depth"},
    "tree_view":    {"fr": "🌲 Arborescence", "en": "🌲 Tree"},
    "view":         {"fr": "Affichage", "en": "Display"},
    "v_table":      {"fr": "📋 Tableau", "en": "📋 Table"},
    "v_graph":      {"fr": "🕸️ Graphe", "en": "🕸️ Graph"},
    "col_comp":     {"fr": "Composant", "en": "Component"},
    "col_qty2":     {"fr": "Qté", "en": "Qty"},
    "raw_title":    {"fr": "🧱 Total matières premières (voie la moins chère, hors recyclage)",
                     "en": "🧱 Total raw materials (cheapest path, recycling excluded)"},
    "make_qty":     {"fr": "Quantité à fabriquer", "en": "Quantity to make"},
    "total_cost":   {"fr": "Coût total des matières", "en": "Total materials cost"},
    "col_rawqty":   {"fr": "Qté totale", "en": "Total qty"},
    "col_cost":     {"fr": "Coût", "en": "Cost"},
    "col_place":    {"fr": "Lieu", "en": "Place"},
    "col_detail":   {"fr": "Détail", "en": "Detail"},
    "craftmap_help":{"fr": "Remonte la chaîne de production : ingrédients → sous-composants → matières brutes. 🔴 produit · 🔵 intermédiaire · 🟢 brut. Glisse les nœuds, zoome, survole pour le prix.",
                     "en": "Walks the production chain: ingredients → sub-components → raw materials. 🔴 product · 🔵 intermediate · 🟢 raw. Drag nodes, zoom, hover for price."},
    "universe_help":{"fr": "Structure du jeu : 🟣 Secteur → 🟢 Système → 🔵 Planète / 🟠 Station. (Positions non géographiques — le jeu génère la carte procéduralement.)",
                     "en": "Game structure: 🟣 Sector → 🟢 System → 🔵 Planet / 🟠 Station. (Not geographic — the game generates the map procedurally.)"},
    "search_recipe":{"fr": "🔎 Rechercher (produit ou ingrédient)", "en": "🔎 Search (product or ingredient)"},
    "search_item":  {"fr": "🔎 Rechercher un item", "en": "🔎 Search an item"},
    "station":      {"fr": "Station", "en": "Station"},
    "unlock":       {"fr": "Déblocage", "en": "Unlock"},
    "sort_by":      {"fr": "Trier par", "en": "Sort by"},
    "all_f":        {"fr": "(toutes)", "en": "(all)"},
    "all_m":        {"fr": "(tous)", "en": "(all)"},
    "only_pos":     {"fr": "Uniquement VA > 0", "en": "Only VA > 0"},
    "n_recipes":    {"fr": "recettes", "en": "recipes"},
    "n_items":      {"fr": "items", "en": "items"},
    "sort_va_desc": {"fr": "VA ↓", "en": "VA ↓"},
    "sort_va_asc":  {"fr": "VA ↑", "en": "VA ↑"},
    "sort_vah":     {"fr": "VA/heure ↓", "en": "VA/hour ↓"},
    "sort_az":      {"fr": "Produit A→Z", "en": "Product A→Z"},
    # colonnes
    "col_product":  {"fr": "Produit", "en": "Product"},
    "col_va":       {"fr": "VA", "en": "VA"},
    "col_qty":      {"fr": "×sortie", "en": "×output"},
    "col_vah":      {"fr": "VA/h (est.)", "en": "VA/h (est.)"},
    "col_power":    {"fr": "Énergie", "en": "Power"},
    "col_station":  {"fr": "Station", "en": "Station"},
    "col_unlock":   {"fr": "Déblocage", "en": "Unlock"},
    "col_inputs":   {"fr": "Ingrédients", "en": "Ingredients"},
    "col_outputs":  {"fr": "Sorties", "en": "Outputs"},
    "col_itemname": {"fr": "Item", "en": "Item"},
    "col_price":    {"fr": "Prix", "en": "Price"},
    "col_type":     {"fr": "Type", "en": "Type"},
    "col_loot":     {"fr": "Niv. loot", "en": "Loot lvl"},
}


def t(key, lang):
    e = UI.get(key, {})
    return e.get(lang) or e.get("en") or key


def load_translations(code):
    """Retourne {sheet_name: {row_id: texte}}. Vide pour 'en' (langue de base du cdb)."""
    if code == "en":
        return {}
    path = os.path.join(LANG_DIR, f"export_{code}.xml")
    if not os.path.exists(path):
        return {}
    root = ET.parse(path).getroot()
    out = {}
    for sheet in root.findall("sheet"):
        sname = sheet.attrib.get("name")
        d = {}
        for entry in list(sheet):
            kids = {c.tag: (c.text or "").strip() for c in list(entry) if (c.text or "").strip()}
            for field in ("name", "title", "props.label"):  # props.label = libelle des stations (itemTag)
                if kids.get(field):
                    d[entry.tag] = kids[field]
                    break
        if d:
            out[sname] = d
    return out
