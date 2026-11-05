import json
from pathlib import Path
from .annotations import PHASES, timestamp


def write_report(data, annotations, out):
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    out = Path(out)
    out.mkdir(parents=True, exist_ok=True)
    (out / "analysis.json").write_text(json.dumps({"tracks": data, "annotations": annotations}, indent=2, ensure_ascii=False, allow_nan=False), encoding="utf-8")
    fig, ax = plt.subplots(figsize=(11, 5))
    for item in data:
        ax.plot([w["start_s"] for w in item["windows"]], [w["rms_dbfs"] for w in item["windows"]], label=item["file"])
    ax.set(xlabel="Time (s)", ylabel="RMS (dBFS)", title="ADAD — RMS comparison")
    ax.legend()
    fig.tight_layout()
    fig.savefig(out / "rms_comparison.png", dpi=160)
    plt.close(fig)
    metrics = [("centroid_hz", "Centroid (Hz)"), ("bandwidth_hz", "Bandwidth (Hz)"), ("rolloff85_hz", "Rolloff 85% (Hz)")]
    fig, axes = plt.subplots(3, 1, figsize=(11, 9), sharex=True)
    for ax, (key, label) in zip(axes, metrics):
        for item in data:
            ax.plot([w["start_s"] for w in item["windows"]], [w[key] for w in item["windows"]], label=item["file"])
        ax.set(ylabel=label)
    axes[0].legend()
    axes[-1].set_xlabel("Time (s)")
    fig.tight_layout()
    fig.savefig(out / "spectral_comparison.png", dpi=160)
    plt.close(fig)
    lines = ["# ADAD · TMiPvLE + RI — ASCENSION / FRACTURE", "", "## Mesures acoustiques", "",
             "Calculs déterministes sur moyenne mono, rééchantillonnée à 22 050 Hz, sans normalisation. Les WAV sources sont ouverts en lecture seule.", "",
             "| Fichier | Durée | Fréquence source (Hz) | Canaux | Étendue RMS (dB) |", "|---|---:|---:|---:|---:|"]
    for item in data:
        lines.append(f'| {item["file"]} | {timestamp(item["duration_s"])} | {item["sample_rate_hz"]} | {item["channels"]} | {item["rms_window_range_db"]:.3f} |')
    difference = max(d["duration_s"] for d in data) - min(d["duration_s"] for d in data)
    lines += ["", f"Écart de durée maximal : {difference:.3f} s. Fenêtres globales : {data[0]['window_seconds']:g} s ; dernière fenêtre éventuellement partielle.",
              "Les variantes générées ne constituent pas une expérience contrôlée. Un même temps absolu ne garantit pas un passage équivalent.", "",
              "![RMS](rms_comparison.png)", "", "![Caractéristiques spectrales](spectral_comparison.png)", "",
              "RMS : 20 log10 de la racine de la moyenne des carrés ; crête : amplitude absolue maximale. Plancher numérique : −240 dBFS.",
              "Facteur de crête : crête moins RMS. Étendue RMS : maximum moins minimum des RMS des fenêtres ; ce n’est pas une mesure LRA ou LUFS.",
              "FFT avec fenêtre de Hann : centroïde et largeur spectrale pondérés par amplitude ; rolloff à 85 % de la somme des amplitudes. Silence : valeurs spectrales nulles.",
              "La moyenne mono peut annuler des composantes en opposition de phase. Le rééchantillonnage limite la bande analysée. Les mesures ne décrivent pas les stems séparés.", "",
              "## Annotations humaines — cinq phases", "", "Les positions et validations proviennent uniquement d’une écoute humaine. `unverified` signifie à vérifier, y compris lorsqu’une phase manque.", "",
              "| Fichier | Phase | Début | Fin | Statut | Notes d’écoute |", "|---|---|---|---|---|---|"]
    for item in data:
        for phase in item["phases"]:
            note = str(phase["notes"]).replace("|", "\\|").replace("\n", " ")
            lines.append(f'| {item["file"]} | {phase["label"]} | {timestamp(phase["start_s"])} | {timestamp(phase["end_s"])} | {phase["status"]} | {note} |')
    lines += ["", "## Fenêtres autour des événements annotés", "",
              "Ancrage au début saisi par l’auditeur ; même rayon et même pas pour chaque piste. Les bornes sont tronquées aux limites du WAV, sans remplissage. Les repères non validés restent exploratoires.",
              "Contraste dynamique local : RMS après moins RMS avant, calculé sur les échantillons de chaque demi-fenêtre. Les durées réellement disponibles sont indiquées ; une demi-fenêtre vide donne une valeur indisponible.", "",
              "| Fichier | Phase | Ancrage | Avant (s) | Après (s) | Contraste (dB) |", "|---|---|---|---:|---:|---:|"]
    count = 0
    for item in data:
        for event in item["events"]:
            count += 1
            contrast = event["after_minus_before_rms_db"]
            lines.append(f'| {item["file"]} | {event["label"]} ({event["status"]}) | {timestamp(event["anchor_s"])} | {event["before_duration_s"]} | {event["after_duration_s"]} | {contrast if contrast is not None else "indisponible"} |')
    if not count:
        lines += ["", "Aucun horodatage fourni : aucune fenêtre événementielle ni comparaison alignée calculée. Les cinq phases restent à localiser, sans détection automatique."]
    for phase_key, label in PHASES.items():
        selected = [(item, e) for item in data for e in item["events"] if e["phase"] == phase_key]
        if not selected:
            continue
        fig, axes = plt.subplots(4, 1, figsize=(11, 10), sharex=True)
        for ax, (key, ylabel) in zip(axes, [("rms_dbfs", "RMS (dBFS)"), *metrics]):
            for item, event in selected:
                ax.plot([(w["relative_start_s"] + w["relative_end_s"])/2 for w in event["windows"]],
                        [w[key] for w in event["windows"]], marker=".",
                        label=f'{item["file"]} @ {timestamp(event["anchor_s"])} ({event["status"]})')
            ax.axvline(0, color="gray", linestyle="--")
            ax.set(ylabel=ylabel, xlim=(-selected[0][1]["requested_radius_s"], selected[0][1]["requested_radius_s"]))
        axes[0].set_title(label + " — human annotation")
        axes[0].legend(fontsize=8)
        axes[-1].set_xlabel("Seconds relative to annotated start")
        fig.tight_layout()
        name = f"aligned_{phase_key}.png"
        fig.savefig(out / name, dpi=160)
        plt.close(fig)
        lines += ["", f"![{label}]({name})"]
        if len(selected) != len(data):
            lines += ["", f"{label} : annotation absente pour certaines pistes ; comparaison alignée incomplète."]
    lines += ["", "## Interprétations artistiques — écoute humaine requise", "",
              "Tension, Montée instrumentale, Proclamation vocale, Libération émotionnelle et Résonance intime sont des catégories artistiques annotées par l’auditeur. Le pipeline ne détecte pas automatiquement les émotions.",
              "Un changement de RMS ou de spectre ne prouve ni une parole, ni un instrument, ni une émotion, ni une qualité artistique. Aucun classement artistique n’est déduit des courbes.",
              "Les paroles candidates consignées dans les notes sont des indications humaines, sans reconnaissance vocale ni confirmation acoustique de leur position.", "",
              "## Traçabilité", "", "Empreintes SHA-256 des sources au moment de l’analyse :", ""]
    for item in data:
        lines.append(f'- {item["file"]} : `{item["sha256"]}`')
    (out / "report.md").write_text("\n".join(lines) + "\n", encoding="utf-8")
