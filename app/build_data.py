# -*- coding: utf-8 -*-
"""Donnees pour le Ship Builder et le Base Builder.

Composants de vaisseau (itemType Ship*) et batiments de base (itemType BaseBuilding_*),
groupes par categorie, avec leurs attributs (stats) extraits du cdb (champ `attributes` =
liste de {attr, value}). Les noms/prix viennent du dict `items` deja traduit (cdb_model.build).
"""
import cdb_model

# --- categories (itemType -> cle de libelle i18n) ---
SHIP_CATS = [
    ("ShipCockpit", "sb_cockpit"),
    ("ShipEngine", "sb_engine"),
    ("ShipFTLModules", "sb_ftl"),
    ("ShipPowerGenerators", "sb_gen"),
    ("ShipBattery", "sb_battery"),
    ("ShipInventoryModules", "sb_cargo"),
    ("ShipShields", "sb_shield"),
    ("ShipWeapon", "sb_weapon"),
    ("ShipRadars", "sb_radar"),
    ("ShipBooster", "sb_booster"),
]

BASE_CATS = [
    ("BaseBuilding_Power", "bb_power"),
    ("BaseBuilding_Crafting", "bb_craft"),
    ("BaseBuilding_Gathering", "bb_gather"),
    ("BaseBuilding_Storage", "bb_storage"),
    ("BaseBuilding_Logistic", "bb_logi"),
    ("BaseBuilding_Command", "bb_command"),
]

# attributs resumes (ship) : id cdb -> on les somme et on calcule des bilans
SHIP_KEYS = ["SystemSupport", "SystemRequirement", "PowerProduction", "EngineConsumption",
             "EngineForce", "ShipWeight", "StorageUnits", "PowerStorage", "Hull", "Frame"]
BASE_KEYS = ["EnergyOffer", "FuelConsumption", "BuildPointsCost", "SolidStorage",
             "EnergyStockCapacity", "StorageUnits"]


def attr_meta(sheets):
    """id attribut -> (nom EN, unite)."""
    return {l["id"]: (l.get("name") or l["id"], l.get("unit") or "")
            for l in cdb_model._lines(sheets, "attribute")}


def _attrs(line):
    return {x["attr"]: x["value"] for x in (line.get("attributes") or []) if x.get("attr")}


def item_attributes(sheets, item_id):
    """{attr_id: value} d'un item (stats brutes), ou {} si aucune."""
    for l in cdb_model._lines(sheets, "item"):
        if l.get("id") == item_id:
            return _attrs(l)
    return {}


def grouped(sheets, items, cats):
    """-> [{'cat', 'key', 'list':[{id,name,price,attrs}]}] (chaque liste triee par nom)."""
    by_type = {}
    for l in cdb_model._lines(sheets, "item"):
        by_type.setdefault(l.get("type"), []).append(l)
    out = []
    for t, key in cats:
        lst = []
        for l in by_type.get(t, []):
            iid = l.get("id")
            lst.append({"id": iid,
                        "name": items.get(iid, {}).get("name", iid),
                        "price": items.get(iid, {}).get("price", 0) or 0,
                        "attrs": _attrs(l)})
        lst.sort(key=lambda x: x["name"])
        if lst:
            out.append({"cat": t, "key": key, "list": lst})
    return out


def sum_attrs(components):
    """Somme les attributs d'une liste de composants choisis (multiplicite incluse)."""
    tot = {}
    for c in components:
        for k, v in c["attrs"].items():
            tot[k] = tot.get(k, 0) + (v or 0)
    return tot
