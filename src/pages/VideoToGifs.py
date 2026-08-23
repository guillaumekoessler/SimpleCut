import streamlit as st

from components.FramePreview import afficher_vignettes_bornes
from components.GifPanel import panneau_gif
from components.MediaLayout import colonne_media
from components.VideoStatus import afficher_statut_video
from utils.GifClasses import ConversionParams, largeurs_disponibles
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

    colonne_vitesse, colonne_largeur = st.columns(2)
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
    # Les largeurs sont CALCULÉES depuis celle de la vidéo, comme les vitesses
    # le sont depuis sa cadence : on ne propose jamais d'agrandir.
    largeurs = largeurs_disponibles(current.width)
    with colonne_largeur:
        largeur_gif = st.select_slider(
            "Largeur",
            options=largeurs,
            value=largeurs[-1],
            format_func=lambda px: f"{px} px",
            help=(
                "Largeur du GIF ; la hauteur suit le format de la vidéo. "
                "C'est le réglage qui pèse le plus : diviser la largeur par "
                "deux divise le poids par quatre, sans altérer les couleurs."
            ),
        )

    fps = vitesses[nom_vitesse]
    duree_segment = fin - debut

    st.divider()
    # Dimensions calculées par ConversionParams et non ici : la page annonce
    # exactement ce que l'export produira, jamais une estimation parallèle.
    largeur_sortie, hauteur_sortie = ConversionParams(
        start_time=0.0, end_time=1.0, fps=fps, largeur_cible=largeur_gif
    ).dimensions_sortie(current.width, current.height)
    st.caption(
        f"Segment : {duree_segment:.1f} s · {nom_vitesse} ({fps} i/s) · "
        f"{largeur_sortie} × {hauteur_sortie} px · "
        f"≈ {int(duree_segment * fps)} images"
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
    ConversionParams(
        start_time=debut, end_time=fin, fps=fps, largeur_cible=largeur_gif
    )
    if fin > debut
    else None
)

panneau_gif(current, params)
