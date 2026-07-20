"""Registry of configured DiffSinger voicebanks.

Each entry's `experiment` value must match the folder name under
DIFFSINGER_HOME/checkpoints/ once the voicebank is installed — see
docs/INSTALLATION.md for the exact setup steps.
"""
from dataclasses import dataclass


@dataclass(frozen=True)
class VoicebankInfo:
    name: str
    experiment: str
    language: str
    min_midi_note: int
    max_midi_note: int
    license_summary: str


# v1 default: a LUNAI Project character. LUNAI's terms (verified 2026-07-21
# against github.com/lunaiproject/lunai_singers's terms-of-use file) permit
# non-commercial use with attribution ("<Character> from LUNAI Project");
# commercial use needs written per-character permission from the LUNAI team
# first (email request, ~7 business day turnaround per their terms). Their
# terms also prohibit porting/modifying models for other engines — this
# server invokes the same underlying DiffSinger checkpoint directly via
# subprocess rather than through OpenUtau's GUI; user's explicit call was
# to proceed and evaluate quality now, revisit if this specific point
# becomes a blocker before any commercial release.
#
# Character picked arbitrarily from LUNAI's roster — per-character
# language/vocal-character metadata wasn't available from documentation
# alone. Confirm this is actually a fit (language, tone, range) by ear
# during Task 14's manual verification, and swap this entry (or add more)
# for a different LUNAI character or a different voicebank entirely if it
# isn't a fit ("if the voicebank sucks we scrap it, find another").
VOICEBANK_REGISTRY: dict[str, VoicebankInfo] = {
    "lunai-katyusha": VoicebankInfo(
        name="Katyusha (LUNAI Project)",
        experiment="lunai_katyusha",
        language="unconfirmed",
        min_midi_note=48,   # C3 — conservative default until confirmed by ear
        max_midi_note=72,   # C5 — conservative default until confirmed by ear
        license_summary=(
            "Non-commercial use permitted with attribution "
            "('Katyusha from LUNAI Project'). Commercial use requires "
            "written per-character permission from the LUNAI team first."
        ),
    ),
}
