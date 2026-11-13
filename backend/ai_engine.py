"""
================================================================================
 OMBAR FL-AI Studio  -  AI Engine  (natural-language -> MCP tool-calls)
================================================================================
Turns a dashboard prompt such as:

    "buat beat hip-hop 90 bpm di A minor, kasih 808 dan hi-hat"
    "pasang vocal chain di insert 6 dengan auto-tune, eq, kompresor, reverb"
    "atur struktur lagu: intro, verse, chorus, drop, outro"

into a structured plan of MCP tool-calls that mcp_bridge.py forwards to FL
Studio on TCP 9787.

The engine is rule-based + keyword-driven so it works fully offline.
Three command groups are supported, matching the user's spec:

  GROUP 1  Beat & Instrument creation
           - set_bpm, set_key, create_drum_pattern, load_instrument,
             add_track, set_genre
  GROUP 2  Mixing & Vocal effects
           - route_track_to_mixer, load_effect, set_effect_param,
             enable_vocal_chain
  GROUP 3  Remix & Arrangement
           - duplicate_pattern, set_song_structure, automate_param,
             split_clip, move_clip

Every MCP tool name here is intentionally generic; the flstudio-mcp project
exposes tools with these (or very similar) names.  If a tool is missing the
bridge simply returns an error per-call without crashing the whole plan.

OPTIONAL LLM upgrade:
  Set env  OMBAR_LLM=1  and provide an OpenAI-compatible endpoint to let an
  LLM refine the plan when the rule-matcher confidence is low.
================================================================================
"""

from __future__ import annotations

import logging
import os
import re
from dataclasses import dataclass, field
from typing import Any, Callable, Dict, List, Optional

log = logging.getLogger("ombar.ai")


# --------------------------------------------------------------------------- #
#  Data classes
# --------------------------------------------------------------------------- #
@dataclass
class Step:
    group: str                 # "beat" | "mix" | "arrange" | "system"
    tool: str                  # MCP tool name
    args: Dict[str, Any] = field(default_factory=dict)
    note: str = ""             # human-readable explanation for the dashboard
    wave: int = 0              # dependency wave: 0 setup, 1 create, 2 configure, 3 finalize


@dataclass
class Plan:
    prompt: str
    steps: List[Step] = field(default_factory=list)
    confidence: float = 0.0
    tags: List[str] = field(default_factory=list)


# --------------------------------------------------------------------------- #
#  Genre presets (drum patterns per style)
# --------------------------------------------------------------------------- #
GENRE_PATTERNS: Dict[str, Dict[str, Any]] = {
    "hip-hop": {
        "bpm": 90, "bpm_range": (80, 100),
        "pattern": {
            "kick":   [1, 0, 0, 0, 0, 0, 0, 0, 1, 0, 0, 0, 0, 0, 0, 0],
            "snare":  [0, 0, 0, 0, 1, 0, 0, 0, 0, 0, 0, 0, 1, 0, 0, 0],
            "hihat":  [1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1],
            "808":    [1, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 1],
        },
        "instruments": ["FL Keys", "FPC"],
    },
    "papua-pop": {
        "bpm": 95, "bpm_range": (88, 105),
        "pattern": {
            "kick":   [1, 0, 0, 0, 0, 0, 0, 0, 1, 0, 0, 1, 0, 0, 0, 0],
            "snare":  [0, 0, 0, 0, 1, 0, 0, 0, 0, 0, 0, 0, 1, 0, 0, 0],
            "hihat":  [1, 0, 1, 0, 1, 0, 1, 0, 1, 0, 1, 0, 1, 0, 1, 0],
            "808":    [1, 0, 0, 0, 0, 0, 1, 0, 0, 0, 0, 0, 0, 0, 1, 0],
        },
        "instruments": ["FL Keys", "Sytrus"],
    },
    "edm": {
        "bpm": 128, "bpm_range": (120, 140),
        "pattern": {
            "kick":   [1, 0, 0, 0, 1, 0, 0, 0, 1, 0, 0, 0, 1, 0, 0, 0],
            "snare":  [0, 0, 0, 0, 1, 0, 0, 0, 0, 0, 0, 0, 1, 0, 0, 0],
            "hihat":  [0, 0, 1, 0, 0, 0, 1, 0, 0, 0, 1, 0, 0, 0, 1, 0],
            "808":    [0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0],
        },
        "instruments": ["Sytrus", "Harmor"],
    },
    "trap": {
        "bpm": 140, "bpm_range": (130, 160),
        "pattern": {
            "kick":   [1, 0, 0, 0, 0, 0, 0, 0, 1, 0, 0, 1, 0, 0, 0, 0],
            "snare":  [0, 0, 0, 0, 1, 0, 0, 0, 0, 0, 0, 0, 1, 0, 0, 0],
            "hihat":  [1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1],
            "808":    [1, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 1, 0],
        },
        "instruments": ["FPC", "Sytrus"],
    },
    "pop": {
        "bpm": 110, "bpm_range": (100, 120),
        "pattern": {
            "kick":   [1, 0, 0, 0, 0, 0, 0, 0, 1, 0, 0, 0, 0, 0, 0, 0],
            "snare":  [0, 0, 0, 0, 1, 0, 0, 0, 0, 0, 0, 0, 1, 0, 0, 0],
            "hihat":  [1, 0, 1, 0, 1, 0, 1, 0, 1, 0, 1, 0, 1, 0, 1, 0],
            "808":    [0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0],
        },
        "instruments": ["FL Keys", "Sytrus"],
    },
}

# Recognised musical keys
KEY_ALIASES = {
    "a minor": "A minor", "am": "A minor", "a moll": "A minor",
    "c major": "C major", "cmaj": "C major", "c": "C major",
    "g major": "G major", "gmaj": "G major", "g": "G major",
    "d minor": "D minor", "dm": "D minor",
    "e minor": "E minor", "em": "E minor",
    "f major": "F major", "f": "F major",
}

# Genre keyword aliases (lowercased substrings)
GENRE_ALIASES: Dict[str, List[str]] = {
    "hip-hop": ["hip hop", "hip-hop", "hiphop", "rap", "boom bap"],
    "papua-pop": ["papua", "papua pop", "papuan"],
    "edm": ["edm", "electronic", "house", "techno", "electro"],
    "trap": ["trap", "drill"],
    "pop": ["pop", "pop ballad"],
}

EFFECT_CHAIN = {
    "auto-tune":   {"plugin": "Auto-Tune",  "slot": 0, "params": {"retune": 30, "key": "auto"}},
    "eq":          {"plugin": "Fruity Parametric EQ 2", "slot": 1, "params": {}},
    "compressor":  {"plugin": "Maximus",    "slot": 2, "params": {"threshold": -18, "ratio": 4}},
    "reverb":      {"plugin": "Fruity Reeverb 2", "slot": 3, "params": {"decay": 60, "wet": 35}},
    "deesser":     {"plugin": "Fruity DeEsser", "slot": 4, "params": {}},
    "delay":       {"plugin": "Fruity Delay 3", "slot": 5, "params": {"feedback": 30}},
}

# Instrument loading
INSTRUMENT_ALIASES: Dict[str, str] = {
    "fl keys": "FL Keys",
    "flkey": "FL Keys",
    "piano": "FL Keys",
    "sytrus": "Sytrus",
    "harmor": "Harmor",
    "fpc": "FPC",
    "slicer": "Slicex",
    "sawer": "Sawer",
    "sakura": "Sakura",
    "toxic": "Toxic Biohazard",
    "3xosc": "3xOsc",
}

# Dependency waves for parallel execution.
#   wave 0 = setup    (independent: tempo, key, genre, routing, structure)
#   wave 1 = create   (needs setup: drum patterns, instruments, effects, remix dup)
#   wave 2 = configure (needs create: effect params, automation)
#   wave 3 = finalize  (needs configure: enable vocal chain)
# Steps in the SAME wave fire concurrently on the pipelined MCP connection.
WAVE_FOR: Dict[str, int] = {
    "set_bpm":              0,
    "set_key":              0,
    "set_genre":            0,
    "route_track_to_mixer": 0,
    "set_song_structure":   0,
    "ai_prompt":            0,
    "add_track":            0,
    "create_drum_pattern":  1,
    "load_instrument":      1,
    "load_effect":          1,
    "duplicate_pattern":    1,
    "split_clip":           1,
    "move_clip":            1,
    "set_effect_param":     2,
    "automate_param":       2,
    "enable_vocal_chain":   3,
}


def _norm(text: str) -> str:
    return re.sub(r"\s+", " ", text.lower()).strip()


# --------------------------------------------------------------------------- #
#  The engine
# --------------------------------------------------------------------------- #
class AIEngine:
    def __init__(self, bridge) -> None:
        self.bridge = bridge
        self._emit: Optional[Callable[[str, Dict[str, Any]], None]] = None

    def set_emitter(self, fn: Callable[[str, Dict[str, Any]], None]) -> None:
        self._emit = fn

    def _emit(self, event: str, payload: Dict[str, Any]) -> None:
        if self._emit:
            try:
                self._emit(event, payload)
            except Exception:
                pass

    # ----------------------------------------------------------------------- #
    #  Planning
    # ----------------------------------------------------------------------- #
    def plan(self, prompt: str, context: Optional[Dict[str, Any]] = None) -> Plan:
        text = _norm(prompt)
        p = Plan(prompt=prompt)
        ctx = context or {}
        matched = 0

        # --- GROUP 1: Beat & instruments ------------------------------------
        bpm = self._extract_bpm(text)
        if bpm:
            p.steps.append(Step("beat", "set_bpm", {"bpm": bpm},
                                f"Set BPM to {bpm}"))
            matched += 1

        key = self._extract_key(text)
        if key:
            p.steps.append(Step("beat", "set_key", {"key": key},
                                f"Set musical key to {key}"))
            matched += 1

        genre = self._extract_genre(text)
        if genre:
            preset = GENRE_PATTERNS[genre]
            p.tags.append(genre)
            # If the user did not state a BPM, fall back to the genre default.
            if not bpm:
                p.steps.append(Step("beat", "set_bpm", {"bpm": preset["bpm"]},
                                    f"Set BPM to {preset['bpm']} ({genre})"))
            p.steps.append(Step("beat", "set_genre", {"genre": genre},
                                f"Apply {genre} genre preset"))
            for drum, hits in preset["pattern"].items():
                p.steps.append(Step("beat", "create_drum_pattern",
                                    {"drum": drum, "pattern": hits,
                                     "genre": genre},
                                    f"Program {drum} pattern ({genre})"))
            for inst in preset["instruments"]:
                p.steps.append(Step("beat", "load_instrument",
                                    {"name": inst},
                                    f"Load instrument: {inst}"))
            matched += 1

        # explicit instrument request
        for alias, real in INSTRUMENT_ALIASES.items():
            if alias in text:
                p.steps.append(Step("beat", "load_instrument", {"name": real},
                                    f"Load instrument: {real}"))
                matched += 1

        # 808 / kick / snare / hihat explicit mentions
        for drum in ("808", "kick", "snare", "hi-hat", "hihat", "clap",
                     "tom", "rim"):
            if drum.replace("-", "") in text.replace("-", ""):
                p.steps.append(Step("beat", "create_drum_pattern",
                                    {"drum": drum.replace("hi-hat", "hihat"),
                                     "pattern": None},
                                    f"Add {drum} track (default pattern)"))
                matched += 1

        # --- GROUP 2: Mixing & vocal chain ----------------------------------
        if self._mentions_vocal_chain(text):
            insert = self._extract_insert(text, default=6)
            chain = self._extract_effect_chain(text)
            p.steps.append(Step("mix", "route_track_to_mixer",
                                {"track": "vocal", "insert": insert},
                                f"Route vocal track -> Mixer Insert {insert}"))
            for fx_name in chain:
                fx = EFFECT_CHAIN.get(fx_name, {"plugin": fx_name.title(),
                                                "slot": 0, "params": {}})
                p.steps.append(Step("mix", "load_effect",
                                    {"insert": insert,
                                     "plugin": fx["plugin"],
                                     "slot": fx["slot"]},
                                    f"Load {fx['plugin']} on Insert {insert}"))
                if fx["params"]:
                    p.steps.append(Step("mix", "set_effect_param",
                                        {"insert": insert,
                                         "plugin": fx["plugin"],
                                         "params": fx["params"]},
                                        f"Tune {fx['plugin']} params"))
            p.steps.append(Step("mix", "enable_vocal_chain",
                                {"insert": insert, "chain": chain},
                                f"Enable vocal chain on Insert {insert}"))
            p.tags.append("vocal-chain")
            matched += 1
        else:
            # standalone effect mentions
            for fx_name in EFFECT_CHAIN:
                if fx_name in text or fx_name.replace("-", "") in text:
                    insert = self._extract_insert(text, default=0)
                    fx = EFFECT_CHAIN[fx_name]
                    p.steps.append(Step("mix", "load_effect",
                                        {"insert": insert,
                                         "plugin": fx["plugin"],
                                         "slot": fx["slot"]},
                                        f"Load {fx['plugin']} on Insert {insert}"))
                    matched += 1

        # --- GROUP 3: Remix & arrangement -----------------------------------
        structure = self._extract_song_structure(text)
        if structure:
            p.steps.append(Step("arrange", "set_song_structure",
                                {"sections": structure},
                                f"Arrange song: {' -> '.join(structure)}"))
            p.tags.append("arrangement")
            matched += 1

        if "remix" in text:
            p.steps.append(Step("arrange", "duplicate_pattern",
                                {"source": "verse", "target": "drop",
                                 "transpose": 0},
                                "Duplicate verse -> drop section (remix)"))
            p.tags.append("remix")
            matched += 1

        if "automate" in text or "automation" in text:
            param = self._extract_automation_target(text)
            p.steps.append(Step("arrange", "automate_param",
                                {"param": param, "start": 0, "end": 100,
                                 "bars": 8},
                                f"Automate {param} over 8 bars"))
            matched += 1

        # --- system / fallback ----------------------------------------------
        if matched == 0:
            # Nothing recognised - send the raw prompt as a generic tool call
            # so the FL Studio side still receives something to act on.
            p.steps.append(Step("system", "ai_prompt", {"text": prompt},
                                "Forward raw prompt to FL Studio MCP"))
            p.confidence = 0.2
        else:
            p.confidence = min(1.0, matched / 4.0 + 0.3)

        self._emit("ai.plan", {"steps": len(p.steps),
                               "confidence": p.confidence,
                               "tags": p.tags})
        return p

    # ----------------------------------------------------------------------- #
    #  Execution  -  parallel waves (instant)
    # ----------------------------------------------------------------------- #
    async def execute(self, plan: Plan) -> List[Dict[str, Any]]:
        """Execute steps grouped into dependency waves.

        Steps within the SAME wave run concurrently (asyncio.gather) - this is
        what makes the dashboard feel instant: a 12-step plan with 4 drums +
        2 instruments all in wave 1 fires all 6 MCP calls at once on the
        pipelined connection instead of one-by-one.
        Waves run in order (0 -> 1 -> 2 -> 3) so dependencies hold.
        """
        import asyncio
        # assign wave numbers based on tool name
        for s in plan.steps:
            s.wave = WAVE_FOR.get(s.tool, 0)
        # bucket by wave preserving original order
        total = len(plan.steps)
        results: List[Dict[str, Any]] = [{}] * total
        waves: Dict[int, List[tuple]] = {}
        for i, step in enumerate(plan.steps):
            waves.setdefault(step.wave, []).append((i, step))

        async def _do(idx: int, step: Step) -> Dict[str, Any]:
            self._emit("step.start",
                       {"index": idx + 1, "total": total,
                        "tool": step.tool, "args": step.args, "note": step.note,
                        "wave": step.wave})
            res = await self.bridge.call_tool_safe(step.tool, step.args)
            if not isinstance(res, dict):
                res = {"raw": res}
            res["_index"] = idx + 1
            res["_group"] = step.group
            res["_tool"] = step.tool
            res["_note"] = step.note
            ok = res.get("ok", True)
            self._emit("step.done",
                       {"index": idx + 1, "ok": ok, "result": res, "wave": step.wave})
            return res

        for wave_num in sorted(waves.keys()):
            bucket = waves[wave_num]
            self._emit("wave.start",
                       {"wave": wave_num, "count": len(bucket),
                        "tools": [s.tool for _, s in bucket]})
            # fire all steps in this wave concurrently
            wave_results = await asyncio.gather(
                *[asyncio.ensure_future(_do(i, s)) for i, s in bucket],
                return_exceptions=False,
            )
            for (i, _s), res in zip(bucket, wave_results):
                results[i] = res
            self._emit("wave.done",
                       {"wave": wave_num, "count": len(bucket)})
        return results

    # ----------------------------------------------------------------------- #
    #  Extractors
    # ----------------------------------------------------------------------- #
    @staticmethod
    def _extract_bpm(text: str) -> Optional[int]:
        m = re.search(r"(\d{2,3})\s*(?:bpm|beat\s*per\s*minute)", text)
        if m:
            return int(m.group(1))
        m = re.search(r"(?:tempo|speed)\s*(\d{2,3})", text)
        if m:
            return int(m.group(1))
        return None

    @staticmethod
    def _extract_key(text: str) -> Optional[str]:
        for alias, real in KEY_ALIASES.items():
            if alias in text:
                return real
        m = re.search(r"\bkey\s+([a-g])(?:\s*(major|minor|maj|min))?\b", text)
        if m:
            note = m.group(1).upper()
            quality = m.group(2) or "major"
            if quality.startswith("min"):
                quality = "minor"
            else:
                quality = "major"
            return f"{note} {quality}"
        return None

    @staticmethod
    def _extract_genre(text: str) -> Optional[str]:
        best, best_len = None, 0
        for genre, aliases in GENRE_ALIASES.items():
            for alias in aliases:
                if alias in text and len(alias) > best_len:
                    best, best_len = genre, len(alias)
        return best

    @staticmethod
    def _mentions_vocal_chain(text: str) -> bool:
        triggers = ["vocal chain", "vokal chain", "rantai vokal",
                    "chain vokal", "vocal fx", "mixing vokal", "mixing vocal",
                    "vokal mixing"]
        return any(t in text for t in triggers)

    @staticmethod
    def _extract_insert(text: str, default: int = 0) -> int:
        m = re.search(r"insert\s*(\d+)", text)
        if m:
            return int(m.group(1))
        m = re.search(r"mixer\s*(\d+)", text)
        if m:
            return int(m.group(1))
        m = re.search(r"channel\s*(\d+)", text)
        if m:
            return int(m.group(1))
        return default

    @staticmethod
    def _extract_effect_chain(text: str) -> List[str]:
        # Normalize Indonesian / brand aliases so "kompresor maximus" matches
        # the canonical "compressor" effect used by EFFECT_CHAIN.
        alias_map = {
            "kompresor": "compressor",
            "maximus": "compressor",
            "autotune": "auto-tune",
            "auto tune": "auto-tune",
            "equalizer": "eq",
            "ekualiser": "eq",
            "equaliser": "eq",
            "gema": "reverb",
            "penunda": "delay",
        }
        normalized = text
        for alias, canonical in alias_map.items():
            normalized = normalized.replace(alias, canonical)
        order = ["auto-tune", "eq", "compressor", "deesser", "reverb", "delay"]
        chain: List[str] = []
        for fx in order:
            if fx in normalized or fx.replace("-", "") in normalized:
                chain.append(fx)
        # If none specified but a vocal chain is requested, use the default.
        if not chain:
            chain = ["auto-tune", "eq", "compressor", "reverb"]
        return chain

    @staticmethod
    def _extract_song_structure(text: str) -> List[str]:
        known = ["intro", "verse", "chorus", "bridge", "drop",
                 "hook", "outro", "pre-chorus", "breakdown", "build", "drop"]
        found: List[str] = []
        # detect hyphen / comma / arrow separated lists too
        cleaned = text.replace("->", ",").replace(">", ",")
        for token in re.split(r"[,\s]+", cleaned):
            t = token.strip().lower()
            if t in known and t not in found:
                found.append(t)
        return found

    @staticmethod
    def _extract_automation_target(text: str) -> str:
        for cand in ("volume", "pan", "pitch", "cutoff", "reverb", "delay",
                     "bpm", "filter"):
            if cand in text:
                return cand
        return "volume"
