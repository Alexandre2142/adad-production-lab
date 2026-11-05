# SUNO — ADAD Production Lab v0.1

Local Python pipeline for **TMiPvLE + RI**: Tension → Montée instrumentale → Proclamation vocale → Libération émotionnelle → Résonance intime.

## Install (Windows PowerShell, inside your existing SUNO folder)

1. Extract this archive into a subfolder named `adad-lab` inside `SUNO`.
2. Open the `SUNO/adad-lab` folder in VS Code or Codex.
3. In PowerShell:

```powershell
py -3 -m venv .venv
.venv\Scripts\Activate.ps1
python -m pip install -e .
```

If PowerShell blocks activation, run `.venv\Scripts\python.exe -m pip install -e .` and use that Python executable for subsequent commands.

## Import your audio

Place the two WAV files in `audio/prototypes/` with these names:
- `THE SIGNAL (ASCENSION).wav`
- `THE SIGNAL (FRACTURE).wav`

The archive does not include recordings; keep WAVs local.

## First command

```powershell
suno-lab compare "audio/prototypes/THE SIGNAL (ASCENSION).wav" "audio/prototypes/THE SIGNAL (FRACTURE).wav" --annotations annotations/the_signal.json
```

Outputs: `reports/report.md`, `reports/analysis.json`, `reports/rms_comparison.png`.

## Codex starter task

Open this folder with Codex and give it:

> Read AGENTS.md and README.md. Run the tests and validate the compare command on available local WAV files. Then implement aligned 60-second analysis windows around manually annotated proclamation timestamps, including RMS and spectral centroid plots. Keep all audio local, preserve originals, and distinguish measurable results from artistic hypotheses. Show the diff and test results before changing anything else.

## Limits

The script measures basic audio features only. It does **not** detect lyrics, distinguish vocal/instrumental stems, estimate BPM, or assign emotional impact scores. Those require later validated modules or listening annotations. Suno generation remains manual.

## Annotation assistée TMiPvLE + RI

Les cinq phases sont des annotations humaines, pas des classes prédites par le DSP.
Les horodatages des prototypes ne sont pas encore validés. Les indications de paroles
fournies par l’utilisateur sont conservées comme notes, sans position inventée.

Sous Windows, lancer l’écoute locale du WAV et saisir les repères :

```powershell
.venv\Scripts\suno-lab.exe annotate "audio/prototypes/THE SIGNAL (ASCENSION).wav" --annotations annotations/the_signal.json --play
.venv\Scripts\suno-lab.exe annotate "audio/prototypes/THE SIGNAL (FRACTURE).wav" --annotations annotations/the_signal.json --play
```

`--play` lance le WAV entier en arrière-plan avec le lecteur audio Windows intégré
(`winsound`) ; il s’arrête à la fin de la saisie. Pour disposer d’une barre de lecture,
ouvrir le WAV dans son lecteur habituel et omettre `--play`. La CLI ne mesure pas la
position de lecture : relever les positions dans le lecteur, puis les saisir en secondes
ou `mm:ss`. Début/fin sont en temps absolu depuis le début du WAV. Entrée conserve
une valeur ; `-` efface une position. Confirmer avec `y` uniquement après écoute ;
`n` conserve une phase comme `unverified`. Entrée conserve son statut.

Une phase `validated` exige un début et une fin dans la durée du WAV, avec fin > début.
Une phase absente reste `unverified`, début/fin à `null`. L’ordre, les chevauchements
et les lacunes restent sous le contrôle de l’auditeur : aucune segmentation exhaustive
n’est imposée. Les phases peuvent se chevaucher. La sauvegarde a lieu après validation
de toutes les saisies ; une erreur de saisie ne réécrit pas le JSON existant.

Chaque piste est identifiée par son nom de fichier exact. Format d’une phase :

```json
{
  "phases": {
    "tension": {"start_s": null, "end_s": null, "status": "unverified", "notes": ""},
    "montee_instrumentale": {"start_s": null, "end_s": null, "status": "unverified", "notes": ""},
    "proclamation_vocale": {"start_s": null, "end_s": null, "status": "unverified", "notes": ""},
    "liberation_emotionnelle": {"start_s": null, "end_s": null, "status": "unverified", "notes": ""},
    "resonance_intime": {"start_s": null, "end_s": null, "status": "unverified", "notes": ""}
  }
}
```

Placer cet objet sous `tracks["nom exact.wav"]`. Les anciennes clés `proclamation_s`
et `resonance_intime_s` restent lisibles en l’absence d’une phase structurée ; leur
statut reste `unverified`, même lorsqu’un horodatage est fourni.

## Mesures et comparaison

```powershell
.venv\Scripts\suno-lab.exe compare "audio/prototypes/THE SIGNAL (ASCENSION).wav" "audio/prototypes/THE SIGNAL (FRACTURE).wav" --annotations annotations/the_signal.json --window 5 --event-radius 30
```

Les sorties initiales sont conservées : `report.md`, `analysis.json` et
`rms_comparison.png`. S’ajoutent `spectral_comparison.png` et, pour chaque phase
avec un début renseigné, `aligned_<phase>.png`. Les graphiques alignent le début
annoté à zéro, avec un rayon identique de ±30 s et un pas identique de 5 s par défaut.
Les annotations non validées peuvent produire une analyse exploratoire clairement
étiquetée. Sans repère, aucune courbe événementielle n’est créée et le rapport le dit.

Le JSON conserve les anciens champs et ajoute les phases, événements et empreintes
SHA-256. Chaque événement contient les bornes absolues et relatives des fenêtres,
leurs mesures, les durées avant/après disponibles et les mesures de l’intervalle
annoté lorsqu’une fin existe. Une seule occurrence par phase et piste est prise en
charge dans cette version.

Méthode déterministe : moyenne des canaux, rééchantillonnage polyphasé à 22 050 Hz,
sans normalisation ; RMS et crête en dBFS (plancher −240), facteur de crête en dB.
Contraste local = RMS après moins RMS avant l’ancrage, sur les échantillons des deux
demi-fenêtres. Étendue globale = max moins min des RMS des fenêtres. Ces indicateurs
ne sont ni LUFS ni LRA, et ne constituent pas une mesure d’émotion ou de sonie perceptive.
Le spectre utilise une FFT avec fenêtre de Hann : centroïde, largeur spectrale
(écart type pondéré par amplitude) et rolloff à 85 % de l’amplitude cumulée, en Hz.
Les valeurs spectrales du silence sont nulles. La moyenne mono peut annuler des
composantes en opposition de phase ; la bande est limitée par le rééchantillonnage.

Les fenêtres aux limites sont tronquées, sans ajout de silence. Si un côté est vide,
le contraste est `null`. Comparer aussi les durées disponibles : des fenêtres
tronquées ne sont pas strictement équivalentes. Le rapport présente l’écart de durée
entre variantes. Aucun lien causal ni classement artistique n’est tiré de cette
comparaison de variantes générées, qui n’est pas une expérience contrôlée.

Les mesures acoustiques, annotations d’écoute et interprétations artistiques ont des
sections distinctes. Un changement acoustique n’identifie aucune parole avec certitude.
La localisation de « I AM THE SIGNAL! » et de l’échange final demande une écoute humaine.
Le pipeline ne prétend pas détecter automatiquement les émotions.

## Tests et préservation des sources

```powershell
.venv\Scripts\python.exe -m pytest -q
```

Installer `pytest` dans l’environnement si nécessaire (`python -m pip install pytest`).
Les tests utilisent des WAV synthétiques temporaires : sinus, silence, saut de niveau,
stéréo en opposition de phase, rééchantillonnage et événements aux limites. Ils vérifient
les formules, le schéma, les entrées invalides, l’annotation interactive et les rapports
CLI avec et sans repères. L’intégrité binaire et le SHA-256 d’une source synthétique
sont contrôlés après analyse.

Aucune écriture audio n’est réalisée par le pipeline. Les SHA-256 des WAV réels sont
consignés dans le rapport pour comparaison avant/après. Les tests écrivent uniquement
leurs propres fichiers temporaires. Aucun service externe n’est appelé.

## Interface locale Streamlit

Depuis le dossier `SUNO/adad-lab`, installer les dépendances optionnelles puis lancer :

```powershell
.venv\Scripts\python.exe -m pip install -e ".[ui,test]"
.venv\Scripts\python.exe -m streamlit run streamlit_app.py
```

Ouvrir [l’interface locale](http://127.0.0.1:8501). Arrêter le serveur avec Ctrl+C.
Le fichier `.streamlit/config.toml` limite l’écoute à `127.0.0.1` et désactive les
statistiques d’utilisation Streamlit. Aucun service de transcription, d’analyse distante
ou d’hébergement n’est utilisé. La CLI reste disponible sans installer l’extra `ui`.
L’interface utilise le [lecteur audio Streamlit](https://docs.streamlit.io/develop/api-reference/media/st.audio).

1. Choisir un WAV de `audio/prototypes/` et l’écouter avec le lecteur intégré.
2. Consulter la forme d’onde : enveloppe min/max par canal, au plus 2 000 points,
   qui conserve les crêtes brèves. Les positions sont en secondes absolues.
3. Saisir les débuts/fins en secondes (`62.5`) ou `mm:ss` (`01:02.5`) ; point ou
   virgule décimale acceptés. Laisser vide pour une position inconnue. Aucune valeur
   n’est calculée automatiquement depuis la lecture ou la forme d’onde.
4. Annoter les cinq phases, leurs notes d’écoute et leur statut. Choisir `validated`
   uniquement après écoute. Une phase manquante reste `unverified`, positions vides.
5. Cliquer **Sauvegarder les annotations**. Les repères de la forme d’onde représentent
   les valeurs sauvegardées. Les brouillons sont conservés quand on change de piste,
   mais restent en mémoire de session : les sauvegarder avant de fermer le navigateur.
6. Sélectionner les WAV à comparer puis **Générer le rapport comparatif**. Le bouton
   devient disponible avec au moins deux pistes, au moins une phase validée par piste,
   tous les repères saisis validés et aucun brouillon non sauvegardé. Les phases absentes,
   dont la Résonance intime facultative, peuvent rester `unverified`. Le rapport signale
   les annotations manquantes. La CLI conserve son mode exploratoire avec repères non validés.

Les bornes utilisent la fonction existante `phases_for` : positions finies comprises
entre zéro et la durée, fin strictement après début, et début/fin obligatoires pour
`validated`. Pas de contrainte nouvelle sur l’ordre ou le chevauchement des phases.
Les paroles et les émotions ne sont jamais identifiées à partir de la forme d’onde.

Le fichier reste **`annotations/the_signal.json` avec le même schéma**, sans migration.
Les métadonnées, autres pistes, champs supplémentaires et anciennes clés sont préservés.
Le JSON réel n’est modifié que lors d’une sauvegarde explicite. Une position existante
n’est pas arrondie à l’affichage des champs. Sauvegarde atomique : temporaire dans le même
dossier, flush/fsync, puis remplacement. La version chargée est vérifiée avant écriture ;
un autre enregistrement provoque un message invitant à recharger plutôt qu’un écrasement.
La CLI `annotate` utilise aussi cette sauvegarde. **Recharger les annotations** abandonne
les brouillons et relit le disque. Le verrou `.json.lock` coordonne les sauvegardes CLI/UI ;
si un processus est brutalement interrompu, supprimer uniquement ce verrou après s’être
assuré qu’aucune sauvegarde n’est en cours. Les éditeurs externes n’utilisent pas ce verrou :
éviter les écritures simultanées depuis un éditeur pendant une sauvegarde.

Le rapport est produit par les fonctions DSP/Markdown existantes, dans
`reports/interface/` : Markdown, JSON et PNG. Il peut être consulté dans l’interface et
le Markdown téléchargé ; les images restent dans ce dossier et doivent l’accompagner
lors d’un partage. Après une modification des annotations, relancer le rapport : l’aperçu
précédent ne se met pas à jour automatiquement. Les WAV sont toujours lus, jamais réécrits.

Tests de l’interface (en plus des tests DSP/CLI existants) : parsing des positions,
validation des bornes, préservation du schéma et des WAV synthétiques, enveloppe par canal,
conflits de sauvegarde, échec du remplacement atomique, puis scénarios Streamlit `AppTest`
de saisie, changement de piste, sauvegarde, rechargement et génération du rapport.
Sans Streamlit installé, seuls les deux tests AppTest sont ignorés.
