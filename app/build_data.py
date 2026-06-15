# -*- coding: utf-8 -*-
"""Donnees pour le Ship Builder et le Base Builder.

Composants de vaisseau (itemType Ship*) et batiments de base (itemType BaseBuilding_*),
groupes par categorie, avec leurs attributs (stats) extraits du cdb (champ `attributes` =
liste de {attr, value}). Les noms/prix viennent du dict `items` deja traduit (cdb_model.build).
"""
import cdb_model

# Cockpit = catégorie spéciale (obligatoire, fournit SystemSupport). Les autres = modules.
COCKPIT_TYPE = "ShipCockpit"
# Modules de vaisseau dans l'ordre du jeu. Le LIBELLÉ d'une catégorie = le nom de l'itemType
# traduit du cdb (= exactement le nom affiché en jeu : Propulseur, Module SL, Panneau solaire,
# Éclairage, Outils spécialisés, Module énergétique, Bouclier, Module interne, Aile, etc.).
SHIP_MODULE_TYPES = ["ShipEngine", "ShipFTLModules", "ShipPowerGenerators", "ShipPowerTools",
                     "ShipBattery", "ShipInventoryModules", "MiningTool", "ShipRadars",
                     "ShipToolSpecial", "ShipLight", "ShipShields", "ShipModule", "ShipWeapon",
                     "ShipAmmunition", "ShipBooster", "ShipWing", "ShipHeatTools", "ShipHeatModule",
                     "ShipControlModule"]
# types structurels/cosmétiques à NE PAS proposer comme modules
_SHIP_EXCLUDE = {"ShipCockpit", "ShipDecorative", "ShipElement", "ShipPart", "ShipTool", "ShipGatheringTools"}

BASE_TYPES = ["BaseBuilding_Power", "BaseBuilding_Crafting", "BaseBuilding_Gathering",
              "BaseBuilding_Storage", "BaseBuilding_Logistic", "BaseBuilding_Command"]


def ship_module_types(sheets):
    """Liste ordonnée des itemType de modules de vaisseau ayant ≥1 item. Auto-complète tout
    Ship* présent dans le jeu mais oublié de SHIP_MODULE_TYPES (hors coque/déco/structure)."""
    have = {l.get("type") for l in cdb_model._lines(sheets, "item") if l.get("type")}
    types = [t for t in SHIP_MODULE_TYPES if t in have]
    for t in sorted(have):
        if t.startswith("Ship") and t not in types and t not in _SHIP_EXCLUDE and not t.startswith("ShipHull"):
            types.append(t)
    return types

# attributs resumes (ship) : id cdb -> on les somme et on calcule des bilans
SHIP_KEYS = ["SystemSupport", "SystemRequirement", "PowerProduction", "EngineConsumption",
             "EngineForce", "ShipWeight", "StorageUnits", "PowerStorage", "Hull", "Frame",
             "HeatCapacity", "BoosterHeatGeneration"]
BASE_KEYS = ["EnergyOffer", "EnergyDemand", "FuelConsumption", "MaxBuildPoints", "BuildPointsCost",
             "SolidStorage", "FluidStorage", "EnergyStockCapacity", "DroneRouteCount"]


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


def grouped(sheets, items, types):
    """types = liste d'itemType. -> [{'cat', 'list':[{id,name,price,attrs}]}] (liste triée par nom,
    catégories vides ignorées)."""
    by_type = {}
    for l in cdb_model._lines(sheets, "item"):
        by_type.setdefault(l.get("type"), []).append(l)
    out = []
    for t in types:
        lst = []
        for l in by_type.get(t, []):
            iid = l.get("id")
            lst.append({"id": iid,
                        "name": items.get(iid, {}).get("name", iid),
                        "price": items.get(iid, {}).get("price", 0) or 0,
                        "attrs": _attrs(l)})
        lst.sort(key=lambda x: x["name"])
        if lst:
            out.append({"cat": t, "list": lst})
    return out


def sum_attrs(components):
    """Somme les attributs d'une liste de composants choisis (multiplicite incluse)."""
    tot = {}
    for c in components:
        for k, v in c["attrs"].items():
            tot[k] = tot.get(k, 0) + (v or 0)
    return tot
