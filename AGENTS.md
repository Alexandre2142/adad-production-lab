# Codex instructions — SUNO / ADAD

You are implementing a **local, reproducible** analysis workflow for DJoDA's ADAD music project.

## Artistic architecture
TMiPvLE + RI = Tension → Montée instrumentale → Proclamation vocale → Libération émotionnelle → Résonance intime (optional).
Reference prototype: THE SIGNAL (FRACTURE), final exchange: “Can you hear me now?” / “Loud and clear.”

## Engineering rules
- Preserve all source WAVs; never modify or overwrite audio originals.
- Distinguish measured acoustic facts, human listening annotations, and artistic hypotheses in all outputs.
- Do not infer vocal words, instruments, emotions, or BPM directly from RMS/spectral centroid.
- Prefer deterministic, documented DSP and add tests for every feature.
- Do not call Suno or other external services without verified authorized API access and user approval.
- Do not commit audio recordings by default. No credentials in code.
- Keep the MVP simple: Python CLI, JSON, Markdown and PNG; no dashboard or cloud infrastructure until requested.
- Preserve A/B comparability: identical analysis windows, report duration differences, do not equate generated variants with controlled experiments.

## First improvement tasks
1. Add optional per-track timestamp annotations for the five phases.
2. Generate aligned ±30 s plots around manually tagged proclamations.
3. Add onset/novelty and loudness metrics with validation tests.
4. Design an explicit listener scoring form; never label subjective scores as objective.
