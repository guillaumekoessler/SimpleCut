import streamlit as st

from components.FramePreview import afficher_vignettes_bornes
from components.GifPanel import panneau_gif
from components.MediaLayout import colonne_media
from components.VideoStatus import afficher_statut_video
from utils.GifClasses import ConversionParams
from utils.GifQuality import vitesse_par_defaut, vitesses_disponibles
from utils.PreviewGif import PAS_INTERVALLE, bornes_boucle_video
from utils.VideoClasses import UploadedVideo

afficher_statut_video()

current: UploadedVideo | None = st.session_state.get("uploaded_video")

if current is None:
    st.info("Importez une vidéo pour commencer.", icon="🎬")
    st.stop()  # si aucune vidéo, rien ne s'exécute : plus de crash


# Aperçu vidéo : conteneur déclaré ici (haut de page) mais rempli plus bas,
# une fois les bornes du slider connues — st.container permet ce différé.
apercu = st.container()

# Sélection des paramètres du GIF.
with st.container(border=True):
    st.caption("PARAMÈTRES")

    # Même différé que l'aperçu : les vignettes s'affichent AU-DESSUS du
    # slider mais dépendent de sa valeur.
    zone_vignettes = st.container()

    debut, fin = st.slider(
        "Intervalle",
        min_value=0.0,
        max_value=float(current.duration),
        value=(0.0, min(5.0, float(current.duration))),
        step=PAS_INTERVALLE,
        format="%.1fs",
    )

    with zone_vignettes:
        afficher_vignettes_bornes(current, debut, fin)

    # Les vitesses sont CALCULÉES depuis la cadence de la vidéo : on ne propose
    # jamais de fabriquer des images que la source n'a pas, et toutes celles
    # qu'on propose jouent à la bonne vitesse (cf. utils.GifQuality).
    vitesses = vitesses_disponibles(current.fps)

    colonne_vitesse, colonne_echelle = st.columns(2)
    with colonne_vitesse:
        nom_vitesse = st.segmented_control(
            "Vitesse",
            options=list(vitesses),
            default=vitesse_par_defaut(vitesses),
            # required : sans ça, recliquer l'option active la désélectionne et
            # le widget renvoie None.
            required=True,
            help=(
                "Nombre d'images par seconde. Le GIF dure toujours aussi "
                "longtemps que le segment : « Rapide » ne l'accélère pas, il "
                "le rend plus fluide — et plus lourd."
            ),
        )
    with colonne_echelle:
        echelle = st.slider("Échelle", 0.1, 1.0, 1.0, step=0.1)

    fps = vitesses[nom_vitesse]
    duree_segment = fin - debut

    st.divider()
    st.caption(
        f"Segment : {duree_segment:.1f} s · {nom_vitesse} ({fps} i/s) · "
        f"Échelle : {echelle:.0%} · ≈ {int(duree_segment * fps)} images"
    )

# Remplissage différé de l'aperçu : la vidéo boucle sur la sélection.
# floor/ceil car st.video tronque les bornes à la seconde entière — la boucle
# englobe la sélection ; les vignettes ci-dessus portent la précision au 1/10e.
debut_boucle, fin_boucle = bornes_boucle_video(debut, fin, float(current.duration))
with apercu, colonne_media(largeur=current.width, hauteur=current.height):
    st.video(
        str(current.path),
        autoplay=True,
        muted=True,
        loop=True,
        start_time=debut_boucle,
        end_time=fin_boucle,
    )

# Un segment vide ne peut pas produire de GIF : ConversionParams le refuserait,
# et le panneau sait dire pourquoi il n'y a rien à créer.
params = (
    ConversionParams(start_time=debut, end_time=fin, fps=fps, resize_factor=echelle)
    if fin > debut
    else None
)

panneau_gif(current, params)
