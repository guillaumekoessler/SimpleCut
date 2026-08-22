# tests/donnees.py
"""Jeux de données partagés par plusieurs fichiers de tests.

Pourquoi un module et pas conftest.py : `@pytest.mark.parametrize` est évalué
à la collecte et ne sait pas consommer une fixture. Tout jeu de données
paramétré doit donc vivre dans un module importable.
"""

import math

import pytest

# ---------------------------------------------------------------------------
# Calage de l'aperçu média
# ---------------------------------------------------------------------------
# Les deux réglages « à dire d'expert » du modèle de utils.Layout. Ils sont
# éprouvés à trois niveaux — fonction pure (test_layout), composant
# (test_media_layout) et page (test_pages_smoke) — donc écrits UNE seule fois.
# Forme : (largeur, hauteur, poids des 3 colonnes). La fraction média attendue
# EST le poids central.
CALAGES_REFERENCE = [
    pytest.param(640, 360, (0.1, 0.8, 0.1), id="paysage-16-9"),
    pytest.param(720, 1280, (2 / 7, 3 / 7, 2 / 7), id="portrait-9-16"),
]

# ---------------------------------------------------------------------------
# Dimensions rejetées
# ---------------------------------------------------------------------------
# Forme : (largeur, hauteur, dimension fautive attendue dans le message).
# La colonne fautive est déterministe : utils.Layout valide la largeur AVANT
# la hauteur, donc (0, 0) et (-1, -1) échouent sur la largeur.
DIMENSIONS_INVALIDES = [
    (0, 100, "largeur"),
    (100, 0, "hauteur"),
    (0, 0, "largeur"),
    (-1, 10, "largeur"),
    (10, -1, "hauteur"),
    (-1, -1, "largeur"),
    (-5, 100, "largeur"),
    (math.nan, 10, "largeur"),
    (10, math.nan, "hauteur"),
    (math.inf, 10, "largeur"),
    (10, math.inf, "hauteur"),
]

# ---------------------------------------------------------------------------
# Domaines numériques rejetés
# ---------------------------------------------------------------------------
# Une seule écriture pour le non-fini : math.nan, jamais float("nan").
NON_FINIS = (math.nan, math.inf, -math.inf)

# Ce que _valider_positive_finite refuse : durée, fps, pas…
POSITIFS_INVALIDES = (0.0, -1.0, -30.0, *NON_FINIS)

# ---------------------------------------------------------------------------
# Clips de test
# ---------------------------------------------------------------------------
# Couleurs unies : après encodage H.264 le canal dominant reste franc, ce qui
# permet d'affirmer QUEL clip a été décodé sans comparer pixel à pixel.
ROUGE = (200, 30, 30)
VERT = (30, 200, 30)

# ---------------------------------------------------------------------------
# Cadences GIF
# ---------------------------------------------------------------------------
# Forme : (fps de la source, vitesses attendues, vitesse présélectionnée).
# Les deux derniers cas éprouvent le REPLI : une source plus lente que la
# vitesse « Lent » ne peut plus offrir le catalogue, on lui laisse le meilleur
# diviseur de 100 encore atteignable.
VITESSES_PAR_SOURCE = [
    pytest.param(30.0, {"Lent": 5, "Moyen": 10, "Rapide": 20}, "Moyen", id="source-30"),
    pytest.param(20.0, {"Lent": 5, "Moyen": 10, "Rapide": 20}, "Moyen", id="source-20"),
    pytest.param(10.0, {"Lent": 5, "Moyen": 10}, "Moyen", id="source-10"),
    pytest.param(8.0, {"Lent": 5}, "Lent", id="source-8-lent-seul"),
    pytest.param(4.0, {"Lent": 4}, "Lent", id="repli-4"),
    pytest.param(0.5, {"Lent": 1}, "Lent", id="repli-sous-1-image-par-seconde"),
]

# Cadences sources balayées par l'invariant « aucune vitesse ne dérive ».
# 24 est la cadence cinéma (aucun de ses diviseurs utiles ne divise 100, c'est
# le cas qui coince), 29.97 le NTSC, seul fps source non entier du jeu.
FPS_SOURCES = (0.5, 8.0, 10.0, 24.0, 29.97, 60.0)

# ---------------------------------------------------------------------------
# Noms de téléchargement
# ---------------------------------------------------------------------------
# Le nom d'un upload part tel quel dans un en-tête Content-Disposition.
# Forme : (nom du fichier source, nom de téléchargement attendu).
# Les trois vecteurs à neutraliser : traversée de chemin (POSIX et Windows),
# guillemet, retour ligne.
NOMS_A_ASSAINIR = [
    ("vacances.mov", "vacances.gif"),
    ("../../etc/passwd.mov", "passwd.gif"),
    ('photo"; drop.mov', "photo_drop.gif"),
    ("ligne\nsuivante.mov", "ligne_suivante.gif"),
    ("sans-extension", "sans-extension.gif"),
    ("...", "animation.gif"),
    ("", "animation.gif"),
    ("é" * 200 + ".mov", "é" * 60 + ".gif"),
]
