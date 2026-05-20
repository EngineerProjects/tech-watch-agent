"""WatchContext — builds the prompt context block from a WatchProfile.

Injected into PLANNER and SYNTHESIZER prompts so the agent adapts
its plan and output to exactly what the user configured.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from typing import Optional


_MONTH_FR = {
    1: "janvier", 2: "février", 3: "mars", 4: "avril",
    5: "mai", 6: "juin", 7: "juillet", 8: "août",
    9: "septembre", 10: "octobre", 11: "novembre", 12: "décembre",
}

_MONTH_EN = {
    1: "January", 2: "February", 3: "March", 4: "April",
    5: "May", 6: "June", 7: "July", 8: "August",
    9: "September", 10: "October", 11: "November", 12: "December",
}

# How many plan steps each depth level implies
_DEPTH_STEPS = {"brief": 2, "standard": 4, "deep": 7}

# Which tools map to which source types
_SOURCE_TOOLS = {
    "web": ["searxng", "web_search"],
    "arxiv": ["arxiv", "semantic_scholar"],
    "reddit": ["reddit"],
    "github": ["github"],
    "youtube": ["youtube"],
    "pdf": ["research_paper", "jina_reader"],
}


@dataclass
class WatchContext:
    topics: list[str] = field(default_factory=list)
    depth: str = "standard"         # brief | standard | deep
    format: str = "report"          # digest | report | newsletter
    angle: str = "both"             # technical | business | both
    sources: list[str] = field(default_factory=list)
    language: str = "fr"
    audience: str = "solo developer"
    focus: str = ""
    profile_name: str = ""

    # Auto-populated from system clock
    current_year: int = field(default_factory=lambda: datetime.now().year)
    current_month: int = field(default_factory=lambda: datetime.now().month)

    @classmethod
    def default(cls) -> "WatchContext":
        return cls()

    @classmethod
    def from_profile(cls, profile: object) -> "WatchContext":
        now = datetime.now()
        return cls(
            topics=list(getattr(profile, "topics", []) or []),
            depth=getattr(profile, "depth", "standard"),
            format=getattr(profile, "format", "report"),
            angle=getattr(profile, "angle", "both"),
            sources=list(getattr(profile, "sources", []) or []),
            language=getattr(profile, "language", "fr"),
            audience=getattr(profile, "audience", "solo developer"),
            focus=getattr(profile, "focus", "") or "",
            profile_name=getattr(profile, "name", ""),
            current_year=now.year,
            current_month=now.month,
        )

    @property
    def month_name(self) -> str:
        if self.language == "fr":
            return _MONTH_FR.get(self.current_month, str(self.current_month))
        return _MONTH_EN.get(self.current_month, str(self.current_month))

    @property
    def date_label(self) -> str:
        return f"{self.month_name} {self.current_year}"

    @property
    def allowed_tools(self) -> list[str]:
        """Return the subset of tools the planner should use based on sources."""
        if not self.sources:
            # Default: web + arxiv
            return ["searxng", "web_search", "arxiv", "semantic_scholar", "deep_research"]
        tools: list[str] = []
        for src in self.sources:
            tools.extend(_SOURCE_TOOLS.get(src, []))
        tools.append("deep_research")  # always available
        # dedupe while preserving order
        seen: set[str] = set()
        out: list[str] = []
        for t in tools:
            if t not in seen:
                seen.add(t)
                out.append(t)
        return out

    @property
    def suggested_steps(self) -> int:
        return _DEPTH_STEPS.get(self.depth, 4)

    def to_prompt_block(self) -> str:
        """Formatted block injected into PLANNER and SYNTHESIZER system prompts."""
        sources_str = ", ".join(self.sources) if self.sources else "web, arxiv (default)"
        tools_str = ", ".join(self.allowed_tools)
        focus_line = f"\n- Focus spécifique : {self.focus}" if self.focus else ""
        profile_line = f"\n- Profil : {self.profile_name}" if self.profile_name else ""

        return f"""
## CONTEXTE DE VEILLE UTILISATEUR
- Date actuelle : {self.month_name} {self.current_year} (TOUJOURS chercher du contenu de {self.current_year}, pas avant)
- Topics : {', '.join(self.topics) if self.topics else 'selon la tâche'}
- Profondeur : {self.depth} ({self.suggested_steps} étapes de recherche)
- Format de sortie : {self.format}
- Angle : {self.angle}
- Sources préférées : {sources_str}
- Outils autorisés : {tools_str}
- Audience : {self.audience}
- Langue de sortie : {self.language}{profile_line}{focus_line}

RÈGLE ABSOLUE SUR LES DATES :
- Nous sommes en {self.month_name} {self.current_year}
- Toutes les recherches DOIVENT cibler {self.current_year}
- Si une source date de 2024 ou avant, elle est considérée ancienne — à mentionner comme contexte uniquement
- Inclure l'année {self.current_year} dans toutes les requêtes de recherche
""".strip()

    def to_synthesizer_block(self) -> str:
        """Context block for SYNTHESIZER — shapes the report format."""
        format_instructions = {
            "digest": (
                "Format DIGEST : 1 page max. Résumé exécutif (5 lignes), "
                "5-8 points clés numérotés, 1 section tendances. Pas de sous-sections longues."
            ),
            "report": (
                "Format RAPPORT COMPLET : résumé exécutif (3-5 phrases), points clés numérotés, "
                "sections thématiques avec paragraphes, citations [N], recommandations, références."
            ),
            "newsletter": (
                "Format NEWSLETTER : accroche engageante, sections 'À la une', 'Tendances', "
                "'Liens utiles', ton conversationnel mais professionnel, call-to-action final."
            ),
        }.get(self.format, "Format rapport complet standard.")

        angle_instructions = {
            "technical": "Angle TECHNIQUE : privilégier les détails d'implémentation, benchmarks, APIs, code.",
            "business": "Angle BUSINESS : privilégier l'impact marché, financement, adoption, concurrence.",
            "both": "Angle MIXTE : équilibrer analyse technique et impact business.",
        }.get(self.angle, "Angle mixte.")

        return f"""
## FORMAT DE SORTIE DEMANDÉ
- {format_instructions}
- {angle_instructions}
- Audience cible : {self.audience}
- Langue : {'français' if self.language == 'fr' else 'anglais'}
- Date du rapport : {self.month_name} {self.current_year}
""".strip()
