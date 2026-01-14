from pathlib import Path
import sys

project_root = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(project_root / "src"))

import json

CATEGORIES = {
    "animal": [
        "chat", "chien", "cheval", "vache", "mouton", "cochon",
        "lapin", "souris", "oiseau", "poisson", "lion", "elephant"
    ],
    "food": [
        "pomme", "banane", "poire", "pain", "fromage", "gâteau",
        "riz", "pâtes", "soupe", "chocolat", "yaourt"
    ],
    "drink": [
        "eau", "lait", "jus", "café", "thé", "chocolat chaud"
    ],
    "furniture": [
        "table", "chaise", "lit", "canapé", "armoire", "bureau", "étagère"
    ],
    "clothing": [
        "pantalon", "tee-shirt", "robe", "pull", "manteau",
        "chaussures", "chaussettes", "chapeau"
    ],
    "profession": [
        "médecin", "infirmier", "enseignant", "policier",
        "pompier", "boulanger", "cuisinier", "chauffeur"
    ],
    "sport": [
        "football", "basket", "tennis", "natation",
        "vélo", "course", "judo", "gymnastique"
    ],
    "musical_instrument": [
        "piano", "guitare", "violon", "tambour", "trompette", "flûte"
    ],
    "color": [
        "rouge", "bleu", "vert", "jaune", "rose",
        "noir", "blanc", "gris", "orange"
    ],
    "shape": [
        "rond", "carré", "triangle", "rectangle", "étoile", "cœur"
    ],
    "weather": [
        "soleil", "pluie", "neige", "vent", "nuage", "orage"
    ],
    "emotion": [
        "content", "triste", "en colère", "peur", "surpris", "fatigué"
    ],
    "body_part": [
        "tête", "main", "pied", "bras", "jambe", "œil", "bouche", "nez"
    ],
    "vehicle": [
        "voiture", "vélo", "bus", "camion", "train", "moto", "avion"
    ],
    "place": [
        "maison", "école", "parc", "hôpital", "magasin", "piscine", "rue"
    ],
}

from qcmgen.pictos.resolve import resolve_term_to_picto_strict
from tqdm import tqdm
import json

arasaac_cache_path = project_root / "data" / "arasaac_cache_fr.json"

with open(arasaac_cache_path) as f:
    cached_pictos = json.load(f)

print('Caching pictograms for distractor categories...')
for category in tqdm(CATEGORIES):
    for word in CATEGORIES[category]:
        # check if picto is in cache, if not fetch from arasaac and store in cache
        if not word in cached_pictos:
            resolved_picto = resolve_term_to_picto_strict(word, expected_type=category)