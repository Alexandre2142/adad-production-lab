from copy import deepcopy
import io
import json
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import soundfile as sf
import streamlit as st
from suno_lab.annotations import PHASES, phases_for
from suno_lab.annotation_ui import track_from_fields, waveform
from suno_lab.cloud import validate_uploads, import_annotations, report_bundle


def main():
    st.set_page_config(page_title="ADAD · Session cloud", layout="wide")
    st.title("ADAD Production Lab · Session cloud")
    st.warning("Session temporaire : télécharger les annotations avant de fermer ou recharger la page. Ce service ne garantit pas la confidentialité entre utilisateurs au niveau du serveur. Utiliser le mode local pour les données sensibles.")
    st.caption("Annotation humaine TMiPvLE + RI. Aucune détection automatique des paroles ou émotions. Aucun accès aux fichiers du mode local.")
    uploads = st.file_uploader("WAV · 2 maximum, 50 Mio chacun, 100 Mio au total", type=["wav"], accept_multiple_files=True)
    st.caption("Mono/stéréo, 8–48 kHz, 5 minutes et 24 millions d’échantillons de canaux maximum par fichier.")
    if st.button("Charger les WAV (remplace la session)"):
        try:
            audio = validate_uploads([(f.name, f.getvalue()) for f in uploads])
            for key in list(st.session_state):
                if key.startswith("cloud:"):
                    del st.session_state[key]
            st.session_state.cloud_audio = audio
            st.session_state.cloud_doc = {"tracks": {}}
            st.session_state.pop("cloud_report", None)
        except (ValueError, OSError) as exc:
            st.error(str(exc))
    if st.button("Effacer cette session"):
        st.session_state.clear()
        st.rerun()
    audio = st.session_state.get("cloud_audio", {})
    if not audio:
        st.info("Charger des WAV pour commencer. Aucun enregistrement personnel n’est inclus dans le déploiement.")
        return
    imported = st.file_uploader("Reprendre un JSON d’annotations (1 Mio maximum)", type=["json"])
    if st.button("Importer les annotations", disabled=imported is None):
        try:
            doc = import_annotations(imported.getvalue(), audio)
            st.session_state.cloud_doc = doc
            for key in list(st.session_state):
                if key.startswith("cloud:"):
                    del st.session_state[key]
            st.session_state.pop("cloud_report", None)
        except (ValueError, OSError, TypeError) as exc:
            st.error(str(exc))
    doc = st.session_state.cloud_doc
    name = st.selectbox("WAV à annoter", list(audio))
    duration = sf.info(io.BytesIO(audio[name])).duration
    st.audio(audio[name], format="audio/wav")
    times, low, high = waveform(io.BytesIO(audio[name]))
    fig, axes = plt.subplots(low.shape[1], 1, figsize=(12, 4), sharex=True, squeeze=False)
    for channel, ax in enumerate(axes[:, 0]):
        ax.fill_between(times, low[:, channel], high[:, channel], alpha=.7)
        ax.set(ylabel=f"Canal {channel+1}", xlim=(0, duration))
    axes[-1, 0].set_xlabel("Temps absolu (s)")
    fig.tight_layout()
    st.pyplot(fig)
    plt.close(fig)
    st.caption("Enveloppe acoustique min/max ; elle ne localise pas une parole avec certitude.")
    track = doc["tracks"].get(name, {})
    fields = {}
    # One submitted form commits all five phases to this session's JSON together.
    with st.form(f"cloud:form:{name}"):
        for phase in phases_for(track, duration):
            key = phase["phase"]
            prefix = f"cloud:{name}:{key}:"
            st.markdown(f"**{PHASES[key]}**")
            cols = st.columns(3)
            fields[key] = {
                "start": cols[0].text_input("Début (secondes ou mm:ss)", value="" if phase["start_s"] is None else str(phase["start_s"]), key=prefix+"start"),
                "end": cols[1].text_input("Fin (secondes ou mm:ss)", value="" if phase["end_s"] is None else str(phase["end_s"]), key=prefix+"end"),
                "status": cols[2].selectbox("Statut", ["unverified", "validated"], index=int(phase["status"] == "validated"), key=prefix+"status"),
                "notes": st.text_area("Notes d’écoute", value=phase["notes"], key=prefix+"notes"),
            }
        if st.form_submit_button("Appliquer les annotations à cette session"):
            try:
                updated = track_from_fields(track, fields, duration)
                changed = deepcopy(doc)
                changed["tracks"][name] = updated
                import_annotations(json.dumps(changed, ensure_ascii=False).encode("utf-8"), audio)
                st.session_state.cloud_doc = doc = changed
                st.session_state.pop("cloud_report", None)
                st.success("Annotations appliquées en mémoire ; télécharger le JSON pour les conserver.")
            except ValueError as exc:
                st.error(str(exc))
    st.caption("Appliquer avant de changer de piste : les modifications non appliquées du formulaire peuvent être perdues. Positions inconnues : champs vides et unverified.")
    st.download_button("Télécharger les annotations JSON", json.dumps(doc, indent=2, ensure_ascii=False, allow_nan=False), file_name="annotations.json", mime="application/json")
    reasons = []
    if len(audio) < 2:
        reasons.append("Charger deux WAV pour comparer.")
    for filename, content in audio.items():
        phases = phases_for(doc["tracks"].get(filename, {}), sf.info(io.BytesIO(content)).duration)
        if not any(p["status"] == "validated" for p in phases):
            reasons.append(f"{filename} : valider au moins une phase.")
        if any(p["start_s"] is not None and p["status"] != "validated" for p in phases):
            reasons.append(f"{filename} : des repères restent unverified.")
    if reasons:
        st.info("\n\n".join(reasons))
    st.caption("Le rapport utilise uniquement les annotations appliquées, pas les champs non soumis du formulaire.")
    if st.button("Générer le rapport comparatif", disabled=bool(reasons)):
        try:
            with st.spinner("Calcul acoustique temporaire…"):
                st.session_state.cloud_report = report_bundle(audio, doc)
        except (ValueError, OSError) as exc:
            st.error(str(exc))
    if "cloud_report" in st.session_state:
        assets, archive = st.session_state.cloud_report
        st.download_button("Télécharger le rapport complet (ZIP)", archive, file_name="adad-report.zip", mime="application/zip")
        for filename, content in assets.items():
            if filename.endswith(".png"):
                st.image(content, caption=filename)
