"""Dimensions d'affichage des médias (en pixels)."""

# Vignettes
LARGEUR_VIGNETTE_SIDEBAR = 56

# --- Calage (mesuré à l'œil sur des rendus réels ; les deux boutons de réglage)
FRACTION_MAX = 0.80  # largeur max de la colonne centrale (calé sur du 16:9)
FRACTION_MIN = 3 / 7  # largeur min (calé sur du 9:16) ; doit rester > 1/3
RATIO_PLAFOND = 16 / 9  # ratio auquel FRACTION_MAX a été calé

# --- Dérivées : ne jamais coder ces valeurs en dur ---
# Hauteur d'affichage visée, EXPRIMÉE EN FRACTION DE LA LARGEUR DU CONTENEUR.
HAUTEUR_CIBLE = FRACTION_MAX / RATIO_PLAFOND
# En deçà de ce ratio, le plancher de largeur prend le relais.
RATIO_PLANCHER = FRACTION_MIN / HAUTEUR_CIBLE


PAS_INTERVALLE = 0.1
