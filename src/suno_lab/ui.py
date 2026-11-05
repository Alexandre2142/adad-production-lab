from copy import deepcopy
import os
from pathlib import Path
import re
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import soundfile as sf
import streamlit as st
from suno_lab.annotations import PHASES, phases_for, timestamp
from suno_lab.annotation_ui import track_from_fields, waveform, report_readiness, generate_report
from suno_lab.storage import read_annotations, save_annotations


@st.cache_data(show_spinner=False)
def load_waveform(path, modified_ns, size):
    return waveform(path)


def remember_field(key):
    st.session_state.setdefault("draft_values", {})[key] = st.session_state[key]


def main():
    st.set_page_config(page_title="ADAD · Annotation audio", layout="wide")
    root = Path(os.environ.get("SUNO_LAB_ROOT", Path(__file__).resolve().parents[2])).resolve()
    annotation_path = root / "annotations" / "the_signal.json"
    files = sorted((root / "audio" / "prototypes").glob("*.wav"))
    st.title("ADAD · TMiPvLE + RI")
    st.caption("Annotation d’écoute locale · Tension → Montée instrumentale → Proclamation vocale → Libération émotionnelle → Résonance intime")
    st.info("Les phases sont des choix humains. Le signal ne détecte ni paroles ni émotions. Aucun horodatage n’est proposé automatiquement.")
    if not files:
        st.warning("Ajouter des WAV dans audio/prototypes/ pour commencer.")
        return
    if st.button("Recharger les annotations (abandonner les saisies)"):
        for key in list(st.session_state):
            if key in ("annotation_snapshot", "draft_values") or key.startswith("phase:"):
                del st.session_state[key]
    try:
        if "annotation_snapshot" not in st.session_state:
            st.session_state.annotation_snapshot = read_annotations(annotation_path)
        doc, revision = st.session_state.annotation_snapshot
        name = st.selectbox("WAV à annoter", [p.name for p in files])
        path = next(p for p in files if p.name == name)
        info = sf.info(path)
        track = doc.get("tracks", {}).get(name, {})
        phases = phases_for(track, info.duration)
        st.caption(f"{timestamp(info.duration)} · {info.samplerate} Hz · {info.channels} canaux · {path}")
        st.audio(str(path), format="audio/wav")
        st.caption("Utiliser le lecteur pour écouter et relever les positions. La lecture ne remplit pas les champs.")
        stat = path.stat()
        times, low, high = load_waveform(str(path), stat.st_mtime_ns, stat.st_size)
        fig, axes = plt.subplots(info.channels, 1, figsize=(12, 2 * info.channels), sharex=True, squeeze=False)
        for channel, ax in enumerate(axes[:, 0]):
            ax.fill_between(times, low[:, channel], high[:, channel], color="#357b91", alpha=.8)
            ax.set(ylabel=f"Canal {channel+1}", xlim=(0, info.duration))
            for phase in phases:
                if phase["start_s"] is not None:
                    ax.axvline(phase["start_s"], color="#b85e30", alpha=.6)
                    if phase["end_s"] is not None:
                        ax.axvspan(phase["start_s"], phase["end_s"], color="#b85e30", alpha=.08)
        axes[-1, 0].set_xlabel("Temps absolu (s)")
        fig.tight_layout()
        st.pyplot(fig)
        plt.close(fig)
        st.caption("Enveloppe min/max par canal ; traits et zones = annotations sauvegardées. Amplitude acoustique, sans interprétation artistique.")
        st.subheader("Repères d’écoute")
        st.caption("Secondes ou mm:ss (décimales admises). Vide = phase absente, à laisser unverified. validated exige début < fin dans le WAV.")
        drafts = st.session_state.setdefault("draft_values", {})
        fields = {}
        for phase in phases:
            key = phase["phase"]
            prefix = f"phase:{name}:{key}:"
            st.markdown(f"**{PHASES[key]}**")
            columns = st.columns([1, 1, 1])
            start = columns[0].text_input("Début", value=drafts.get(prefix+"start", "" if phase["start_s"] is None else str(phase["start_s"])), key=prefix+"start", on_change=remember_field, args=(prefix+"start",))
            end = columns[1].text_input("Fin", value=drafts.get(prefix+"end", "" if phase["end_s"] is None else str(phase["end_s"])), key=prefix+"end", on_change=remember_field, args=(prefix+"end",))
            status = columns[2].selectbox("Statut", ["unverified", "validated"], index=int(drafts.get(prefix+"status", phase["status"]) == "validated"), key=prefix+"status", on_change=remember_field, args=(prefix+"status",))
            notes = st.text_area("Notes d’écoute", value=drafts.get(prefix+"notes", phase["notes"]), key=prefix+"notes", height=75, on_change=remember_field, args=(prefix+"notes",))
            fields[key] = {"start": start, "end": end, "status": status, "notes": notes}
        updated = None
        try:
            updated = track_from_fields(track, fields, info.duration)
        except ValueError as exc:
            st.error(str(exc))
        if st.button("Sauvegarder les annotations", disabled=updated is None, type="primary"):
            changed = deepcopy(doc)
            changed.setdefault("tracks", {})[name] = updated
            revision = save_annotations(annotation_path, changed, revision)
            doc = changed
            st.session_state.annotation_snapshot = (doc, revision)
            st.success("Annotations sauvegardées. Les WAV sont inchangés.")
        st.subheader("Rapport comparatif")
        st.caption("Le rapport utilise uniquement les annotations sauvegardées. Chaque piste doit avoir au moins une phase validated ; tous les repères saisis doivent être validés. Les phases absentes peuvent rester unverified.")
        chosen = st.multiselect("WAV à comparer", [p.name for p in files], default=[p.name for p in files])
        selected = [p for p in files if p.name in chosen]
        # Include drafts on other tracks: switching files must not silently lose unsaved edits.
        dirty = False
        for other in files:
            saved_track = doc.get("tracks", {}).get(other.name, {})
            saved_phases = phases_for(saved_track, sf.info(other).duration)
            other_fields = {}
            for phase in saved_phases:
                prefix = f"phase:{other.name}:{phase['phase']}:"
                other_fields[phase["phase"]] = {
                    "start": drafts.get(prefix+"start", "" if phase["start_s"] is None else str(phase["start_s"])),
                    "end": drafts.get(prefix+"end", "" if phase["end_s"] is None else str(phase["end_s"])),
                    "status": drafts.get(prefix+"status", phase["status"]),
                    "notes": drafts.get(prefix+"notes", phase["notes"]),
                }
            try:
                candidate = track_from_fields(saved_track, other_fields, sf.info(other).duration)
                dirty |= phases_for(candidate, sf.info(other).duration) != saved_phases
            except ValueError:
                dirty = True
        reasons = report_readiness(selected, doc)
        if dirty:
            reasons.append("Sauvegarder ou recharger les saisies avant de lancer le rapport.")
        if reasons:
            st.warning("\n\n".join(reasons))
        if st.button("Générer le rapport comparatif", disabled=bool(reasons)):
            current_doc, current_revision = read_annotations(annotation_path)
            if current_revision != revision:
                raise ValueError("Annotations modifiées sur disque : recharger avant de générer le rapport.")
            with st.spinner("Analyse acoustique locale…"):
                report = generate_report(selected, current_doc, root / "reports" / "interface")
            st.session_state.generated_report = str(report)
            st.success("Rapport comparatif généré.")
        if "generated_report" in st.session_state:
            report = Path(st.session_state.generated_report)
            if report.exists():
                text = report.read_text(encoding="utf-8")
                st.caption(f"Dernier rapport généré : {report}. Relancer après toute modification des annotations.")
                st.download_button("Télécharger le Markdown", text, file_name="report.md", mime="text/markdown")
                with st.expander("Afficher le rapport et les graphiques"):
                    st.markdown(re.sub(r"!\[[^\]]*\]\([^)]+\)", "", text))
                    for image in re.findall(r"!\[[^\]]*\]\(([^)]+)\)", text):
                        st.image(str(report.parent / image))
    except (ValueError, OSError, TypeError) as exc:
        st.error(str(exc))


if __name__ == "__main__":
    main()
