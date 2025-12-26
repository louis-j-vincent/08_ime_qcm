import time
from qcmgen.pictos.resolve import resolve_term_to_picto

# Un petit set utile IME (tu étendras après)
TERMS = [
    # animaux
    "chat", "chien", "cheval", "lion", "éléphant", "oiseau", "poisson",
    "vache", "mouton", "cochon", "lapin", "souris",

    # objets / école
    "livre", "crayon", "cahier", "stylo", "table", "chaise", "école",

    # actions fréquentes
    "manger", "boire", "dormir", "marcher", "courir", "jouer", "regarder",

    # couleurs
    "rouge", "bleu", "vert", "jaune", "noir", "blanc", "gris",
]

def main():
    ok = 0
    for t in TERMS:
        r = resolve_term_to_picto(t, lang="fr")
        if r is None:
            print(f"MISS: {t}")
        else:
            ok += 1
            print(f"OK  : {t:10s} -> id={r.picto_id} tags={('animal' in r.tags)}")
        time.sleep(0.25)  # throttle simple (évite de spammer)
    print(f"\nDone. Resolved {ok}/{len(TERMS)} terms.")

if __name__ == "__main__":
    main()
