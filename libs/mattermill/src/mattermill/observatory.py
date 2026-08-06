"""A coherent 1937 private-observatory evidence packet as modern scans.

This is a fictional-world packet calibrated against period structures: a
same-year David Dunlap observing-log facsimile, period sidereal-clock and
chronograph practice, a 1937 photographic timing paper, and the Lowell Pluto
Dome architectural record.  The words and institution are fictional; the
standard structures they inhabit are sourced in the operator experiment
``winter-observatory-evidence-1937``.

The decisive fault is explicit.  ``defect={"correction_sign": "reverse"}``
changes only the displayed sign of a measured -56.8 second correction.  The
raw regulator reading, chronograph contacts, plate field, radio-rate notebook,
and RA/HA/LST worksheet remain honest, so the wrong sign shifts a reader's
sidereal reduction by exactly 113.6 sidereal seconds without ambient
contradictions. Civil timestamps convert that interval to 113.3 mean-solar
seconds before applying it.
"""

from __future__ import annotations

import io
import hashlib
import random
import re
from typing import Any

from PIL import Image, ImageChops, ImageDraw, ImageFilter
from reportlab.lib.pagesizes import letter
from reportlab.lib.utils import ImageReader
from reportlab.pdfgen import canvas as rl_canvas

from . import assets, scan


PAGE_W, PAGE_H = letter
MARGIN = 44.0
CHRONOGRAPH_BEAT_COUNT = 90
SIDEREAL_SECONDS_PER_MEAN_SOLAR_SECOND = 1.002737909350795
GATEHOUSE_FORM_CLAIM = (
    "fictional local comparison card calibrated to sourced U.S. Naval "
    "Observatory and National Bureau of Standards time-service practice; "
    "not an exact historic form"
)
PAGE_MARKERS = (
    "FILE INVENTORY",
    "NIGHT OBSERVING LOG",
    "PLATE JACKET V-1937-0417",
    "CONTACT REPRODUCTION V-1937-0417",
    "CHRONOGRAPH STRIP V-1937-0417",
    "SIDEREAL STANDARD CORRECTION",
    "RADIO RATE NOTEBOOK",
    "RA - HA - LST REDUCTION",
    "DOME AND CLOCK MAINTENANCE",
    "CIRCULAR 37-1",
    "ENDOWMENT TRANSFER SCHEDULE",
    "CARBON LETTER - TRUSTEES",
    "PLATE VAULT APPOINTMENT",
    "SERVICE KEY REGISTER",
    "DOME GROUND-FLOOR PLAN",
    "STORM AND POWER LOG",
    "FINAL OBSERVING ORDER",
    "EARLY PLATE ENVELOPE V-1911-0086",
    "PLATE JACKET V-1937-0416 - RAKING-LIGHT COPY",
    "GATEHOUSE CHRONOMETER CARD L-2",
)

# The packet is a review composition.  These are the independently forgeable
# evidence objects a game should request, measure, version, and attest.  The
# zero-based page index points into the shared coherent compositor; it is not
# the public identity of the object.
ARTIFACT_SPECS = (
    ("night_observing_log", "observatory_night_log_1937", 1),
    ("plate_jacket", "observatory_plate_jacket_1937", 2),
    ("plate_contact", "observatory_plate_contact_1937", 3),
    ("chronograph_strip", "observatory_chronograph_1937", 4),
    ("clock_correction", "observatory_clock_correction_1937", 5),
    ("radio_rate_notebook", "observatory_radio_rate_1937", 6),
    ("reduction_worksheet", "observatory_reduction_worksheet_1937", 7),
    ("maintenance_log", "observatory_maintenance_log_1937", 8),
    ("public_circular", "observatory_circular_1937", 9),
    ("endowment_advice", "observatory_endowment_advice_1937", 10),
    ("trustee_carbon", "observatory_trustee_carbon_1937", 11),
    ("vault_appointment", "observatory_vault_appointment_1937", 12),
    ("service_key_register", "observatory_key_register_1937", 13),
    ("dome_plan", "observatory_dome_plan_1937", 14),
    ("storm_power_log", "observatory_storm_log_1937", 15),
    ("observing_order", "observatory_observing_order_1937", 16),
    ("early_plate_envelope", "observatory_early_plate_envelope_1937", 17),
    ("plate_raking_copy", "observatory_plate_raking_copy_1937", 18),
    ("gatehouse_time_card", "observatory_gatehouse_time_card_1937", 19),
)
_ARTIFACT_BY_ID = {item[0]: item for item in ARTIFACT_SPECS}
_ARTIFACT_BY_CLASS = {item[1]: item for item in ARTIFACT_SPECS}
_BOUND_LEDGER_ARTIFACTS = frozenset({
    "night_observing_log", "radio_rate_notebook", "maintenance_log",
    "service_key_register", "storm_power_log", "gatehouse_time_card",
})


def _artifact_capture_context(artifact_id: str) -> str:
    """Map represented object anatomy to a shared archival capture context."""
    return (scan.BOUND_LEFT if artifact_id in _BOUND_LEDGER_ARTIFACTS
            else scan.LOOSE_SHEET)


def _packet_capture_context(page_index: int) -> str:
    if page_index == 0:
        return scan.LOOSE_SHEET
    for artifact_id, _class_name, artifact_page in ARTIFACT_SPECS:
        if artifact_page == page_index:
            return _artifact_capture_context(artifact_id)
    raise IndexError(f"unknown observatory packet page: {page_index}")

_ARTIFACT_FACT_KEYS = {
    "night_observing_log": (
        "observatory", "represented_night", "final_plate_id", "object_name",
        "field_ra", "field_dec", "instrument", "plate_class",
        "raw_start_lst", "raw_stop_lst", "hour_angle", "curator",
        "weather_temp_f",
    ),
    "plate_jacket": (
        "observatory", "represented_night", "final_plate_id", "object_name",
        "instrument", "plate_class", "curator",
    ),
    "plate_contact": ("final_plate_id", "field_ra", "field_dec", "object_name"),
    "chronograph_strip": ("final_plate_id", "raw_start_lst", "raw_stop_lst"),
    "clock_correction": (
        "final_plate_id", "raw_midpoint_lst", "true_correction_seconds",
        "culprit_correction_seconds", "trustee", "engineer",
    ),
    "radio_rate_notebook": ("receiver", "true_correction_seconds"),
    "reduction_worksheet": (
        "final_plate_id", "field_ra", "hour_angle", "expected_lst",
        "raw_midpoint_lst", "true_correction_seconds",
        "true_plate_close_civil_time", "library_entry_time",
    ),
    "maintenance_log": ("engineer", "drive_chase"),
    "public_circular": ("observatory", "object_name", "donor_representative"),
    "endowment_advice": (
        "restricted_principal", "diverted_amount", "restricted_balance",
        "transfer_reference", "trustee",
    ),
    "trustee_carbon": ("founder", "early_plate_id", "curator"),
    "vault_appointment": ("founder", "trustee", "transfer_reference"),
    "service_key_register": (
        "trustee", "service_key_out", "service_key_in", "drive_chase",
    ),
    "dome_plan": ("drive_chase", "founder"),
    "storm_power_log": (
        "blackout_civil_time", "snow_depth_in", "generator_gallons",
    ),
    "observing_order": (
        "represented_night", "comparison_plate_id", "final_plate_id",
        "object_name", "founder",
    ),
    "early_plate_envelope": (
        "observatory", "early_plate_id", "curator",
    ),
    "plate_raking_copy": ("comparison_plate_id", "astronomer"),
    "gatehouse_time_card": (
        "observatory", "represented_night", "final_plate_id", "receiver",
        "mean_time_chronometer", "radio_comparison_civil_time",
        "raw_stop_lst", "true_correction_seconds", "correction_shift_seconds",
        "honest_plate_close_civil_time", "false_plate_close_civil_time",
        "civil_shift_seconds", "engineer",
    ),
}


DEFAULT_CANON = {
    "observatory": "Vale Observatory",
    "location": "North Notch, Adirondack Mountains, New York",
    "represented_night": "January 16-17, 1937",
    "founder": "Dr. Alistair Vale",
    "director": "Dr. Eleanor Vale",
    "trustee": "Felix Mercer",
    "curator": "Ruth Bell",
    "astronomer": "Dr. Samuel Wren",
    "engineer": "Thomas Rook",
    "donor_representative": "Lillian Hart",
    "object_name": "Bellweather Field B-17 (Vale local provisional)",
    "final_plate_id": "V-1937-0417",
    "comparison_plate_id": "V-1937-0416",
    "early_plate_id": "V-1911-0086",
    "plate_series": "V",
    "plate_class": "Agfa Astro, 13 x 18 cm",
    "instrument": "Vale 24-inch photographic reflector",
    "field_ra": "05 37 20.0",
    "field_dec": "+32 10 00",
    "raw_start_lst": "05 48 11.8",
    "raw_stop_lst": "05 49 41.8",
    "true_correction_seconds": -56.8,
    "culprit_correction_seconds": 56.8,
    "correction_shift_seconds": 113.6,
    "blackout_civil_time": "10:03:12 P.M. E.S.T.",
    "true_plate_close_civil_time": "10:02:14.0 P.M. E.S.T.",
    "library_entry_time": "10:04 P.M. E.S.T.",
    "mean_time_chronometer": "M-1",
    "radio_comparison_civil_time": "6:00 P.M. E.S.T.",
    "service_key_out": "9:52 P.M.",
    "service_key_in": "10:18 P.M.",
    "restricted_principal": 240000,
    "diverted_amount": 18500,
    "transfer_reference": "T-37-0116-M",
    "drive_chase": "disused clock-weight and drive chase C",
}
_CANON_KEYS = frozenset(DEFAULT_CANON)


def _hms_seconds(value: str) -> float:
    """Convert an unsigned ``HH MM SS.s`` clock value to seconds."""
    parts = str(value).strip().split()
    if len(parts) != 3:
        raise ValueError(f"time must be HH MM SS.s, got {value!r}")
    hour, minute, second = int(parts[0]), int(parts[1]), float(parts[2])
    if not (0 <= hour < 24 and 0 <= minute < 60 and 0 <= second < 60):
        raise ValueError(f"time components outside clock range: {value!r}")
    return hour * 3600 + minute * 60 + second


def _hms_display(seconds: float) -> str:
    seconds %= 24 * 3600
    hour = int(seconds // 3600)
    minute = int((seconds - hour * 3600) // 60)
    second = seconds - hour * 3600 - minute * 60
    return f"{hour:02d} {minute:02d} {second:04.1f}"


def _civil_seconds(value: str) -> float:
    """Convert a represented 12-hour E.S.T. value to seconds after midnight."""
    match = re.fullmatch(
        r"\s*(\d{1,2}):(\d{2})(?::(\d{2}(?:\.\d+)?))?\s+"
        r"([AP])\.M\.(?:\s+E\.S\.T\.)?\s*",
        str(value),
    )
    if match is None:
        raise ValueError(
            "civil time must be HH:MM[:SS[.s]] A.M./P.M. E.S.T., "
            f"got {value!r}"
        )
    hour, minute = int(match[1]), int(match[2])
    second = float(match[3] or 0)
    if not (1 <= hour <= 12 and 0 <= minute < 60 and 0 <= second < 60):
        raise ValueError(f"civil time components outside clock range: {value!r}")
    hour = hour % 12 + (12 if match[4] == "P" else 0)
    return hour * 3600 + minute * 60 + second


def _civil_display(seconds: float) -> str:
    seconds %= 24 * 3600
    hour24 = int(seconds // 3600)
    minute = int((seconds - hour24 * 3600) // 60)
    second = seconds - hour24 * 3600 - minute * 60
    suffix = "P.M." if hour24 >= 12 else "A.M."
    hour12 = hour24 % 12 or 12
    return f"{hour12}:{minute:02d}:{second:04.1f} {suffix} E.S.T."


def _civil_minute_display(seconds: float) -> str:
    """Display the containing civil minute without inventing second precision."""
    seconds %= 24 * 3600
    hour24 = int(seconds // 3600)
    minute = int((seconds - hour24 * 3600) // 60)
    suffix = "P.M." if hour24 >= 12 else "A.M."
    hour12 = hour24 % 12 or 12
    return f"{hour12}:{minute:02d} {suffix} E.S.T."


def _time_facts(model: dict) -> dict[str, str]:
    """Derive every exposure and sidereal result from raw contacts and one delta."""
    start = _hms_seconds(model["raw_start_lst"])
    stop = _hms_seconds(model["raw_stop_lst"])
    if stop < start:
        stop += 24 * 3600
    correction = float(model["true_correction_seconds"])
    midpoint = start + (stop - start) / 2
    corrected_midpoint = midpoint + correction
    hour_angle_seconds = corrected_midpoint - _hms_seconds(model["field_ra"])
    direction = "W" if hour_angle_seconds >= 0 else "E"
    return {
        "raw_midpoint_lst": _hms_display(midpoint),
        "corrected_start_lst": _hms_display(start + correction),
        "corrected_stop_lst": _hms_display(stop + correction),
        "expected_lst": _hms_display(corrected_midpoint),
        "hour_angle": f"+{_hms_display(abs(hour_angle_seconds))} {direction}",
    }


def _civil_facts(model: dict) -> dict[str, Any]:
    """Convert the sidereal sign delta before binding it to a civil minute."""
    honest = _civil_seconds(model["true_plate_close_civil_time"])
    sidereal_shift = float(model["correction_shift_seconds"])
    civil_shift = sidereal_shift / SIDEREAL_SECONDS_PER_MEAN_SOLAR_SECOND
    false = honest + civil_shift
    library = _civil_seconds(model["library_entry_time"])
    if int(false // 60) != int(library // 60):
        raise ValueError(
            "library entry minute must contain the sign-reversed plate close"
        )
    return {
        "honest_plate_close_civil_time": _civil_display(honest),
        "false_plate_close_civil_time": _civil_display(false),
        "library_entry_civil_time": _civil_minute_display(library),
        "sidereal_shift_seconds": round(sidereal_shift, 1),
        "civil_shift_seconds": round(civil_shift, 1),
    }


def sample_packet(rng: random.Random, *, canon: dict | None = None) -> dict:
    """Sample only texture around a caller-supplied canonical game world."""
    canon = dict(DEFAULT_CANON if canon is None else canon)
    missing = _CANON_KEYS - set(canon)
    if missing:
        raise ValueError(f"canon missing required keys: {sorted(missing)}")
    if not str(canon["represented_night"]).endswith("1937"):
        raise ValueError("observatory packet requires a represented night in 1937")
    true = float(canon["true_correction_seconds"])
    false = float(canon["culprit_correction_seconds"])
    if true >= 0 or false != abs(true):
        raise ValueError("correction canon must preserve one sign-reversed magnitude")
    if round(abs(false - true), 1) != float(canon["correction_shift_seconds"]):
        raise ValueError("correction shift must derive from the two signed values")
    principal = int(canon["restricted_principal"])
    diverted = int(canon["diverted_amount"])
    if not 0 < diverted < principal:
        raise ValueError("diverted amount must be inside the restricted principal")
    model = {
        **canon,
        "restricted_balance": principal - diverted,
        "scan_seed": rng.randrange(1 << 30),
        "folder_number": f"N-{rng.randint(310, 489)}",
        "weather_temp_f": rng.randint(3, 12),
        "snow_depth_in": rng.randint(18, 28),
        "receiver": rng.choice(["RCA AR-60", "National HRO"]),
        "generator_gallons": rng.randint(8, 14),
        "digitizer_box": f"BOX {rng.randint(14, 29)} / FOLDER {rng.randint(2, 8)}",
    }
    # Reject an impossible exposure before any record can be rendered.
    if round((_hms_seconds(model["raw_stop_lst"]) -
              _hms_seconds(model["raw_start_lst"])) % (24 * 3600), 1) != 90.0:
        raise ValueError("observatory exposure contacts must span exactly 90.0 seconds")
    _time_facts(model)
    _civil_facts(model)
    return model


def public_display_facts(model: dict, *, defect: dict | None = None) -> dict[str, Any]:
    """Facts a downstream accessible rendition may consume without scraping."""
    keys = (
        "observatory", "location", "represented_night", "founder", "director",
        "trustee", "curator", "astronomer", "engineer", "donor_representative",
        "object_name", "final_plate_id", "comparison_plate_id", "early_plate_id",
        "plate_series", "plate_class", "instrument", "field_ra", "field_dec",
        "raw_start_lst", "raw_stop_lst", "true_correction_seconds",
        "culprit_correction_seconds",
        "correction_shift_seconds", "blackout_civil_time", "library_entry_time",
        "true_plate_close_civil_time", "mean_time_chronometer",
        "radio_comparison_civil_time",
        "service_key_out", "service_key_in", "restricted_principal",
        "diverted_amount", "restricted_balance", "transfer_reference",
        "drive_chase",
    )
    result = {
        **{key: model[key] for key in keys},
        **_time_facts(model),
        **_civil_facts(model),
        "page_inventory": list(PAGE_MARKERS),
        "represented_object_count": len(PAGE_MARKERS),
        "capture_kind": "modern scan of fictional 1937 paper and plate-related objects",
    }
    # The packet inventory remains a convenience composition.  Every game-facing
    # object below exposes its own typed accessibility contract; no caller needs
    # to infer visible wording from a packet page or from an editorial page label.
    inventory = [
        "FILE INVENTORY",
        f"{model['folder_number']} / {model['represented_night']}",
        model["observatory"].upper(),
        model["location"].upper(),
        "SEPARATE OBJECTS - PRESERVE ORDER AND PLATE IDENTITIES",
        *(f"{index:02d}  {marker}"
          for index, marker in enumerate(PAGE_MARKERS[1:], 1)),
        model["digitizer_box"],
        "leaf 1",
    ]
    artifact_accessibility = [
        _accessibility_contract(model, artifact_id, defect=defect)
        for artifact_id, _class_name, _page_index in ARTIFACT_SPECS
    ]
    result["accessibility_schema_version"] = "1.0"
    result["accessibility_pages"] = [
        {
            "editorial_identification": {
                "page_marker": PAGE_MARKERS[0],
                "capture_kind": "review-binder inventory leaf",
            },
            "visible_content": [{"kind": "lines", "lines": inventory}],
            "visual_description": [],
            "interpretation": [],
        },
        *artifact_accessibility,
    ]
    result["reading_copy_pages"] = [
        inventory,
        *(_flatten_visible_content(item["visible_content"])
          for item in artifact_accessibility),
    ]
    result["visual_description_pages"] = [
        [], *(item["visual_description"] for item in artifact_accessibility)
    ]
    return result


def public_artifact_facts(model: dict, artifact_id: str, *,
                          defect: dict | None = None) -> dict[str, Any]:
    """Expose only the facts displayed by one independently forged object."""
    if artifact_id not in _ARTIFACT_BY_ID:
        raise KeyError(f"unknown observatory artifact {artifact_id!r}")
    _identifier, class_name, page_index = _ARTIFACT_BY_ID[artifact_id]
    facts = {**model, **_time_facts(model), **_civil_facts(model)}
    result = {
        **{key: facts[key] for key in _ARTIFACT_FACT_KEYS[artifact_id]},
        "artifact_id": artifact_id,
        "document_class": class_name,
        "page_marker": PAGE_MARKERS[page_index],
        "represented_object_count": 1,
        "capture_kind": "modern scan of one fictional 1937 observatory object",
    }
    if artifact_id == "gatehouse_time_card":
        result["source_claim"] = GATEHOUSE_FORM_CLAIM
    # Validate the same defect surface used by the compositor before publishing
    # a contract.  This prevents a manifest from describing bytes the emitter
    # could never produce.
    _validate_defect(defect)
    accessibility = _accessibility_contract(model, artifact_id, defect=defect)
    result["accessibility_schema_version"] = "1.0"
    result["accessibility"] = accessibility
    # Compatibility aliases remain for callers that have not yet adopted typed
    # content blocks.  The values are now literal text tokens, never summaries.
    result["reading_copy"] = _flatten_visible_content(
        accessibility["visible_content"]
    )
    result["visual_description"] = accessibility["visual_description"]
    return result


def _validate_defect(defect: dict | None) -> dict[str, Any]:
    """Validate and normalize the one explicit display delta."""
    normalized = dict(defect or {})
    unknown = set(normalized) - {"correction_sign"}
    if unknown:
        raise ValueError(f"unsupported observatory defect: {sorted(unknown)}")
    if normalized.get("correction_sign") not in {None, "reverse"}:
        raise ValueError("correction_sign defect must be 'reverse'")
    return normalized


def _displayed_correction(model: dict, defect: dict | None) -> str:
    normalized = _validate_defect(defect)
    displayed = (
        model["culprit_correction_seconds"]
        if normalized.get("correction_sign") == "reverse"
        else model["true_correction_seconds"]
    )
    sign = "+" if displayed >= 0 else "-"
    return f"{sign}{abs(displayed):04.1f} seconds"


def _lines(*values: str) -> dict[str, Any]:
    return {"kind": "lines", "lines": list(values)}


def _table(columns: tuple[str, ...], rows: tuple[tuple[str, ...], ...]) -> dict[str, Any]:
    if any(len(row) != len(columns) for row in rows):
        raise ValueError("accessibility table row does not match its columns")
    return {
        "kind": "table",
        "columns": list(columns),
        "rows": [list(row) for row in rows],
    }


def _flatten_visible_content(blocks: list[dict[str, Any]]) -> list[str]:
    """Compatibility flattening without inventing prose or interpretations."""
    result: list[str] = []
    for block in blocks:
        if block["kind"] == "lines":
            result.extend(block["lines"])
        elif block["kind"] == "table":
            result.append(" | ".join(block["columns"]))
            result.extend(" | ".join(row) for row in block["rows"])
        else:  # pragma: no cover - contracts are built locally
            raise ValueError(f"unknown visible content block: {block['kind']!r}")
    return result


def _accessibility_contract(
    model: dict, artifact_id: str, *, defect: dict | None = None
) -> dict[str, Any]:
    """Return exact text cells and objective visual evidence for one object.

    Editorial identity is deliberately outside ``visible_content``.  Table
    geometry is represented structurally, so pipes or prose never masquerade
    as marks printed on the artifact.  ``interpretation`` is intentionally
    empty: deductions belong to the game, not its accessibility rendition.
    """
    if artifact_id not in _ARTIFACT_BY_ID:
        raise KeyError(f"unknown observatory artifact {artifact_id!r}")
    _validate_defect(defect)
    tf = _time_facts(model)
    cf = _civil_facts(model)
    page_marker = PAGE_MARKERS[_ARTIFACT_BY_ID[artifact_id][2]]
    visible: dict[str, list[dict[str, Any]]] = {
        "night_observing_log": [
            _lines(
                "NIGHT OBSERVING LOG",
                model["observatory"],
                "BOOK IV", "LEAF 117",
                f"NIGHT {model['represented_night'].upper()}",
            ),
            _table(
                ("PLATE", "OBJECT", "R.A. 1900", "DEC. 1900", "TEL.",
                 "EMUL.", "LST START", "LST END", "H.A. MID", "EXP.", "OBS."),
                _night_log_rows(model, tf),
            ),
            _lines(
                f"Seeing 2; {model['weather_temp_f']} F; drive contact lost after exposure",
                f"{model['curator']} / plate {model['final_plate_id']} to vault 10:02 P.M.",
            ),
        ],
        "plate_jacket": [_lines(
            model["observatory"].upper(),
            "PHOTOGRAPHIC PLATE STORE",
            "LOCAL SERIES V / JACKET FORM P-4",
            f"SERIES / NUMBER:  {model['final_plate_id']}",
            f"DATE-NIGHT:       {model['represented_night']}",
            f"OBJECT:           {model['object_name']}",
            f"TELESCOPE:        {model['instrument']}",
            f"PLATE:            {model['plate_class']}",
            "EXPOSURE:         90 SEC. / S.W.",
            "ISSUED:           R. BELL",
            "RETURNED:         10:02 P.M.",
            "do not clean reverse notes",
        )],
        "plate_contact": [_lines(
            f"{model['observatory'].upper()} / LOCAL SERIES V / PLATE {model['final_plate_id']}",
            f"CENTRE {model['field_ra']}  {model['field_dec']}  SCALE 60\"/MM  CARD 17-A",
        )],
        "chronograph_strip": [_lines(
            "OPEN", "CLOSE",
            "MOUNTING CARD C-3 / 1 SECOND PER BEAT / 10 SECONDS PER LINE",
            "OP. T.R.",
            f"open {model['raw_start_lst']}",
            f"close {model['raw_stop_lst']}",
            "mains contact out; beats continue",
        )],
        "clock_correction": [_lines(
            "SIDEREAL STANDARD CORRECTION",
            f"{model['observatory']} / Time Service sheet S-2-1937-016",
            "Clock: Sidereal standard S-2     Date: 16 January 1937",
            "Comparison: U.S. Naval Observatory radio time / 18:00 E.S.T.",
            "Comparison prepared: T. ROOK",
            "Measured result: S-2 FAST 56.8 SEC.",
            f"Observation: local-series plate {model['final_plate_id']}",
            f"Mid-exposure clock reading ........ {tf['raw_midpoint_lst']}",
            f"CORRECTION ENTERED BY F. MERCER ... {_displayed_correction(model, defect)}",
            "Reduction destination: desk sheet R-17 / plate ledger IV-117",
            "Mercer signature:",
        )],
        "radio_rate_notebook": [
            _lines(
                "RADIO RATE NOTEBOOK",
                f"{model['observatory']} / Time Book II leaf 36 / receiver {model['receiver']}",
            ),
            _table(
                ("DATE / EST", "AUTHORITY", "CLOCK", "FAST", "RATE", "OP."),
                (("JAN 14 18:00", "U.S.N.O.", "S-2", "56.70 S", "+0.05 S/D", "T.R."),
                 ("JAN 15 18:00", "U.S.N.O.", "S-2", "56.75 S", "+0.05 S/D", "T.R."),
                 ("JAN 16 18:00", "U.S.N.O.", "S-2", "56.80 S", "+0.05 S/D", "T.R.")),
            ),
            _lines(
                "S-2 fast; subtract 56.8 s",
                "U.S.N.O. signal sets error; daily difference sets rate",
            ),
        ],
        "reduction_worksheet": [_lines(
            "RA - HA - LST REDUCTION",
            f"{model['observatory']} / Reduction desk sheet R-17 / 17 January 1937",
            f"PLATE {model['final_plate_id']}",
            f"R.A. {model['field_ra']} + H.A. {tf['hour_angle']} = L.S.T. {tf['expected_lst']}",
            f"Raw S-2 contacts: {model['raw_start_lst']} / {model['raw_stop_lst']}",
            f"Raw S-2 midpoint: {tf['raw_midpoint_lst']}",
            f"Clock correction used: {model['true_correction_seconds']:+04.1f} seconds / T.R.",
            f"Corrected contacts: {tf['corrected_start_lst']} / {tf['corrected_stop_lst']}",
            "Reduced: S. WREN / entered Night Book IV leaf 117",
        )],
        "maintenance_log": [
            _lines(
                "DOME AND CLOCK MAINTENANCE",
                f"{model['observatory']} / Plant Book III leaf 22 / January 1937",
            ),
            _table(
                ("DATE", "SYSTEM", "WORK", "INITIALS"),
                (("JAN 16", "S-2 contact", "Contact cleaned; unauthorized adjustment", "T.R."),
                 ("JAN 15", "rate check", "Change under one second for reunion interval", "T.R."),
                 ("JAN 16", "dome drive", "Motor circuit serviceable before storm", "T.R."),
                 ("JAN 16", "chase C", "Old weight removed; panel and lock retained", "T.R.")),
            ),
            _lines("12"),
        ],
        "public_circular": [_lines(
            "CIRCULAR 37-1", "Vale Observatory / January 1937",
            "TO THE PRESS AND SUBSCRIBING STATIONS",
            f"Internal field label: {model['object_name']}",
            "Elements provisional; positions are for finder use only.",
            "Jan. 16, 10 P.M. EST   R.A. 05h 37m   Decl. +32 10",
            "Estimated magnitude: 8.1", "5.8", "L.H.",
            "Copies to: North Notch Press, radio desk, subscriber circular list",
        )],
        "endowment_advice": [_lines(
            "ENDOWMENT TRANSFER SCHEDULE",
            f"{model['observatory']} / Treasurer copy / {model['transfer_reference']}",
            "RESTRICTED INSTRUMENT ENDOWMENT — CUSTODIAN ADVICE",
            "STATUS: POSTED 16 JANUARY 1937 / LEDGER 41, FOLIO 6",
            "Account ............ Instrument Reserve 41-6",
            f"Advice date ........ 16 January 1937    Voucher {model['transfer_reference']}",
            f"Opening principal ... {_fmt_money(model['restricted_principal'])}",
            f"Debit — collateral .. {_fmt_money(model['diverted_amount'])}",
            f"Balance forward ..... {_fmt_money(model['restricted_balance'])}",
            "Payee advice ........ North Notch Equipment Holding Co.",
            "Remittance .......... cashier's draft 0116-C",
            "Authorized .......... F. Mercer, Trustee",
            "Second trustee ....... [blank]",
        )],
        "trustee_carbon": [_lines(
            "CARBON LETTER - TRUSTEES",
            f"{model['observatory']} / retained desk carbon / draft 2 / 16 January 1937",
            f"From: {model['founder']}, Director", "Draft — not issued",
            "To the Trustees and the Astronomical Community:",
            f"The first identification on plate {model['early_plate_id']} was Ruth Bell's.",
            "I published the result under my name and permitted the record to stand.",
            "Tonight I intend to restore her credit and submit the endowment books",
            "to an independent audit.  The observatory cannot ask reality to remember",
            "only those facts that preserve its founder.",
        )],
        "vault_appointment": [_lines(
            "PLATE VAULT APPOINTMENT",
            f"{model['observatory']} / Director desk carbon / 16 January 1937",
            "FELIX -", "PLATE VAULT. TEN O'CLOCK.",
            f"BRING TRANSFER SCHEDULE {model['transfer_reference']}.", "A. VALE",
        )],
        "service_key_register": [
            _lines(
                "SERVICE KEY REGISTER",
                f"{model['observatory']} / Plant Book III leaf 23 / dome ground floor / key C",
            ),
            _table(
                ("DATE", "HOLDER", "OUT", "IN", "PURPOSE"),
                (("JAN 15", "T. ROOK", "3:20 P.M.", "4:05 P.M.", "drive oil"),
                 ("JAN 16", model["trustee"].upper(), model["service_key_out"],
                  model["service_key_in"], "trustee inspection")),
            ),
            _lines("C panel"),
        ],
        "dome_plan": [_lines(
            "DOME GROUND-FLOOR PLAN",
            f"{model['observatory']} / drawing D-4 / revision 1",
            "D-1 / 3'-6\" DOOR", "8'-0\" CONCRETE PIER",
            "2\" ISOLATION JOINT — NO WALL BEARING",
            "CHASE C — 14'-0\" WEIGHT TRAVEL", "P-3 LOCKED ACCESS",
            "2'-6\" SERVICE CLEAR", "S-1", "SWITCHBOARD",
            "UP / 8 RISERS @ 7 1/2\"", "N", "30'-0\" INSIDE DIAMETER",
            "8'-0\"", "0    2    4    6    8 FT", model["observatory"].upper(),
            "DOME GROUND-FLOOR SERVICE PLAN",
            "PROJECT: DRIVE & TIME-SERVICE ALTERATIONS", "SCALE: 1/4\" = 1'-0\"",
            "DRAWN: T.R.  12 JAN 1937", "CHECKED: A.V. 15 JAN 1937",
            "DWG. D-4", "REV. 1", "SHEET 4 OF 6",
            "SERVICE RECOVERY NOTE / PLANT BOOK III",
            "17 Jan 10:42 — panel P-3 opened.",
            "Body of Dr. Alistair Vale recovered from chase C. T.R.",
        )],
        "storm_power_log": [
            _lines(
                "STORM AND POWER LOG",
                f"{model['observatory']} / Plant Book III leaf 24 / private spur and dome circuits",
            ),
            _table(
                ("TIME E.S.T.", "SYSTEM", "OBSERVATION"),
                (("8:40 P.M.", "PRIVATE SPUR", f"drifted shut; {model['snow_depth_in']} in. at upper bend"),
                 ("9:31 P.M.", "TELEPHONE", "overhead pair lost beyond gatehouse"),
                 (model["blackout_civil_time"], "MAINS", "lights, dome motor, remote displays lost"),
                 ("10:03:14", "S-2 REGULATOR", "mechanical standard continued"),
                 ("10:05 P.M.", "GENERATOR", f"started; {model['generator_gallons']} gal.; lights only"),
                 ("ALL NIGHT", "PUBLIC ROAD", "reported open to valley gate")),
            ),
        ],
        "observing_order": [_lines(
            "FINAL OBSERVING ORDER",
            f"{model['observatory']} / Dome Order O-37-016 / issued 16 January 1937",
            "Night January 16–17",
            f"1  Plate {model['comparison_plate_id']} — comparison field",
            f"2  Plate {model['final_plate_id']} — {model['object_name']}",
            "3  Repeat plate 0417", "3  Repeat plate 0417", "5", "A. Vale",
        )],
        "early_plate_envelope": [_lines(
            model["observatory"].upper(), f"PLATE {model['early_plate_id']}",
            "DATE: 17 FEB 1911", "B-17 field precursor",
            "R. Bell — object identified and measured",
            "ARCHIVE CHARGE: R.B. / 16 JAN 1937",
        )],
        "plate_raking_copy": [_lines(
            f"{model['observatory'].upper()} / LOCAL SERIES V / PLATE {model['comparison_plate_id']}",
            "RAKING LIGHT FROM LEFT / 22.5 DEGREES", "probable minor planet",
            "S.W. candidate", "S.W.", "COPY RL-0416-1 / R. BELL / 17 JAN 1937",
        )],
        "gatehouse_time_card": [
            _lines(
                "GATEHOUSE CHRONOMETER CARD L-2",
                f"{model['observatory']} / Time Service file / 16-17 JAN 1937",
                "TIME AUTHORITY: U.S. NAVAL OBSERVATORY RADIO TIME",
                f"RADIO COMPARISON: 16 JANUARY 1937 / {model['radio_comparison_civil_time']}",
                f"MEAN-TIME CHRONOMETER: {model['mean_time_chronometer']}",
                "SIDEREAL STANDARD: S-2",
            ),
            _table(
                (f"{model['mean_time_chronometer']} E.S.T.",
                 "S-2 CORRECTED L.S.T.", "OP.", "REFERENCE"),
                ((cf["honest_plate_close_civil_time"], tf["corrected_stop_lst"],
                  "T.R.", f"PLATE {model['final_plate_id']} / CLOSE"),),
            ),
            _lines(
                "TIME-SERVICE CROSS-CHECK / 17 JAN 1937",
                "TIME BOOK II: S-2 FAST 56.8 SEC.",
                "SHEET S-2-1937-016: +56.8 SEC. / F. MERCER",
                f"S-2 SHEET CLOSE: {cf['false_plate_close_civil_time']}",
                f"LIBRARY REGISTER (MINUTE ENTRY): F. MERCER / {cf['library_entry_civil_time']}",
            ),
        ],
    }
    descriptions: dict[str, list[str]] = {
        "night_observing_log": [
            "A ruled bound-ledger table has four completed record rows beneath the eleven printed column headings; separate book, leaf, night, and observatory fields appear above it, and two handwritten notes appear below the grid."
        ],
        "plate_jacket": [
            "An off-white paper plate envelope is shown at a slight angle with a closed triangular flap, ruled handling marks along the lower edge, typed fields, and one handwritten note near the bottom."
        ],
        "plate_contact": [
            "A grayscale contact reproduction shows a dense stellar field of point-like sources inside a dark plate border.",
            "The individual point-like sources are not lettered on the reproduction.",
            "A large diffuse source is conspicuous near the central field and differs visibly from the surrounding point-like stars.",
            "Several faint vertical streaks or plate marks cross parts of the field; their cause is not identified by the artifact."
        ],
        "chronograph_strip": [
            "A continuous, evenly spaced mechanical beat trace runs across nine successive ten-second lines between distinct OPEN and CLOSE contact marks.",
            "The beat trace continues through the region associated with the handwritten mains-contact note."
        ],
        "clock_correction": [
            "A cursive ink signature mark appears beneath the printed field label 'Mercer signature:'; the artifact alone does not authenticate its writer."
        ],
        "maintenance_log": [
            "In the first table row, the written date 'JAN 16' is struck through and '12' is entered above it; the other row cells are not struck."
        ],
        "public_circular": [
            "The typed value '8.1' is struck through; '5.8' and the initials 'L.H.' are handwritten nearby."
        ],
        "endowment_advice": [
            "A cursive signature mark appears near the authorization area; the second-trustee field remains visibly blank."
        ],
        "vault_appointment": [
            "The four-line appointment is isolated inside a large rectangular memorandum border; no handwritten signature appears."
        ],
        "service_key_register": [
            "A ruled custody table has two completed rows followed by blank rows; the entry 'C panel' is handwritten below the grid."
        ],
        "dome_plan": [
            "The measured plan places locked access panel P-3 at chase C beside, not inside, the solid isolated telescope pier.",
            "From door D-1, the drawn floor route passes the isolated pier toward the P-3 service-clearance area; the stair and switchboard occupy the opposite side of the plan.",
            "A north arrow and a black-and-white scale bar labeled from 0 through 8 FT appear on the drawing.",
            "A boxed service-recovery note appears in the lower-left drawing margin."
        ],
        "observing_order": [
            "The handwritten sequence contains two entries numbered 3 and then an isolated 5, with no entry numbered 4."
        ],
        "early_plate_envelope": [
            "An off-white archive envelope is shown at a slight angle with a closed triangular flap; two identification notes are handwritten and the archive-charge line is typed."
        ],
        "plate_raking_copy": [
            "Illumination falls from left to right across the jacket surface.",
            "Indentation remains beneath 'probable minor planet'; that phrase is crossed by a dark strike, and localized surface abrasion surrounds it.",
            "The separate 'S.W. candidate' entry sits spatially above the abraded area; the image alone does not establish when either entry was made."
        ],
        "gatehouse_time_card": [
            "A ruled technical comparison card has one completed row beneath four printed column headings.",
            "The paired clock readings and operator initials are handwritten; the artifact itself does not authenticate the writer.",
            "The conversion rule and the minute-only library cross-reference are typed below the ruled row."
        ],
    }
    _identifier, class_name, _page_index = _ARTIFACT_BY_ID[artifact_id]
    return {
        "editorial_identification": {
            "artifact_id": artifact_id,
            "document_class": class_name,
            "page_marker": page_marker,
            "capture_kind": "modern scan of one fictional 1937 observatory object",
        },
        "visible_content": visible[artifact_id],
        "visual_description": list(descriptions.get(artifact_id, ())),
        "interpretation": [],
    }


def _fmt_money(value: int) -> str:
    return f"${value:,.2f}"


def _paper(c, gray: float, *, material: str = "sheet", key: str = "") -> None:
    """Lay down spatially coherent substrate behavior before scan capture."""
    c.setFillGray(gray)
    c.rect(0, 0, PAGE_W, PAGE_H, fill=1, stroke=0)
    digest = hashlib.sha256(f"paper:{material}:{key}".encode("utf-8")).digest()
    rng = random.Random(int.from_bytes(digest[:8], "big"))
    c.saveState()
    # Edge falloff belongs to the sheet boundary instead of appearing as
    # independent full-page noise.
    for band in range(10):
        tone = max(0.0, gray - 0.035 + band * 0.003)
        c.setFillGray(tone)
        c.setFillAlpha(0.10)
        inset = band * 1.6
        c.rect(inset, inset, PAGE_W - 2 * inset, 1.8, fill=1, stroke=0)
        c.rect(inset, PAGE_H - inset - 1.8, PAGE_W - 2 * inset, 1.8, fill=1, stroke=0)
        c.rect(inset, inset, 1.8, PAGE_H - 2 * inset, fill=1, stroke=0)
        c.rect(PAGE_W - inset - 1.8, inset, 1.8, PAGE_H - 2 * inset, fill=1, stroke=0)
    # Short edge-parallel abrasions follow handling contact.  Avoid generic
    # circular "age spots": they are not evidence of any represented cause.
    c.setStrokeGray(max(0.0, gray - 0.12)); c.setStrokeAlpha(0.055)
    for _ in range(3):
        side_x = rng.choice((rng.uniform(8, 24), rng.uniform(PAGE_W - 24, PAGE_W - 8)))
        side_y = rng.uniform(60, PAGE_H - 60)
        c.setLineWidth(rng.uniform(0.35, 0.8))
        c.line(side_x, side_y - rng.uniform(7, 16),
               side_x + rng.uniform(-1.2, 1.2), side_y + rng.uniform(7, 16))
    c.setStrokeAlpha(0.12)
    if material == "ledger":
        c.setStrokeGray(max(0.0, gray - 0.18)); c.setLineWidth(0.7)
        c.line(34, 42, 34, PAGE_H - 42)
        c.setStrokeAlpha(0.05); c.line(36, 42, 36, PAGE_H - 42)
    elif material == "carbon":
        fold_y = 372 + digest[8] % 36
        c.setStrokeGray(max(0.0, gray - 0.16)); c.setLineWidth(0.45)
        c.line(28, fold_y, PAGE_W - 26, fold_y + rng.uniform(-1.0, 1.0))
        c.setStrokeAlpha(0.04); c.line(28, fold_y + 2, PAGE_W - 26, fold_y + 2)
    elif material == "drawing":
        c.setStrokeGray(max(0.0, gray - 0.10)); c.setStrokeAlpha(0.05)
        c.line(PAGE_W / 2, 8, PAGE_W / 2, 22)
        c.line(PAGE_W / 2, PAGE_H - 8, PAGE_W / 2, PAGE_H - 22)
    c.restoreState()


def _header(c, title: str, subtitle: str = "", *, form: bool = False) -> list[str]:
    """Give each producing system its own period surface, not one house style."""
    ledger = {"NIGHT OBSERVING LOG", "RADIO RATE NOTEBOOK",
              "DOME AND CLOCK MAINTENANCE", "SERVICE KEY REGISTER",
              "STORM AND POWER LOG", "GATEHOUSE CHRONOMETER CARD L-2"}
    carbon = {"SIDEREAL STANDARD CORRECTION", "RA - HA - LST REDUCTION",
              "ENDOWMENT TRANSFER SCHEDULE", "CARBON LETTER - TRUSTEES",
              "PLATE VAULT APPOINTMENT", "FINAL OBSERVING ORDER"}
    if title == "FILE INVENTORY":
        _paper(c, 0.965, material="folder", key=title); font, size, y = "Helvetica-Bold", 12, PAGE_H - 44
    elif title in ledger:
        _paper(c, 0.905, material="ledger", key=title); font, size, y = "Times-Bold", 11, PAGE_H - 58
    elif title in carbon:
        _paper(c, 0.94, material="carbon", key=title); font, size, y = "Courier-Bold", 10.5, PAGE_H - 68
    else:
        material = "drawing" if title == "DOME GROUND-FLOOR PLAN" else "sheet"
        _paper(c, 0.925, material=material, key=title); font, size, y = "Times-Bold", 11.5, PAGE_H - 54
    c.setFillGray(0.13)
    c.setFont(font, size)
    c.drawString(MARGIN + (12 if title in carbon else 0), y, title)
    c.setFont("Courier" if form else "Times-Roman", 7.5)
    c.drawRightString(PAGE_W - MARGIN, y, subtitle)
    if title in ledger:
        c.setLineWidth(1.15); c.line(MARGIN, y - 8, PAGE_W - MARGIN, y - 8)
        c.setLineWidth(0.3); c.line(MARGIN, y - 11, PAGE_W - MARGIN, y - 11)
    elif title == "FILE INVENTORY":
        c.setLineWidth(0.6); c.line(MARGIN, y - 9, PAGE_W - MARGIN, y - 9)
    return [title, subtitle] if subtitle else [title]


def _footer(c, m: dict, page: int) -> None:
    c.setFont("Courier", 6.5)
    c.setFillGray(0.38)
    c.drawString(MARGIN, 24, m["digitizer_box"])
    c.drawRightString(PAGE_W - MARGIN, 24, f"leaf {page}")


def _hand(c, text: str, x: float, y: float, *, size: float = 10.5) -> None:
    c.setFont("Times-Italic", size)
    c.setFillGray(0.08)
    c.drawString(x, y, text)


def _ink(c, text: str, x: float, y: float, *, seed: int, writer: str,
         width: float = 125, height: float = 13.5,
         ink: tuple[int, int, int] | None = None) -> None:
    """Render legible working text in one stable, named physical hand."""
    png = assets.handwriting_png(seed, text=text, writer=writer, ink=ink)
    image = ImageReader(io.BytesIO(png))
    iw, ih = image.getSize()
    natural_h = width * ih / iw
    box_h = min(height, natural_h)
    box_w = min(width, box_h * iw / ih)
    c.drawImage(image, x, y, width=box_w, height=box_h,
                mask="auto", preserveAspectRatio=True)


def _plate_png(seed: int) -> bytes:
    """Seeded contact-print texture with falloff, grain, scratches and stars."""
    rng = random.Random(seed)
    size = 920
    image = Image.new("L", (size, size), 12)
    field = Image.new("L", image.size, 0)
    draw = ImageDraw.Draw(field)
    for _ in range(430):
        x, y = rng.randrange(24, size - 24), rng.randrange(24, size - 24)
        radius = rng.choice((1, 1, 1, 2, 2, 3, 5))
        brightness = rng.randrange(85, 235)
        draw.ellipse((x-radius, y-radius, x+radius, y+radius), fill=brightness)
    # The comet is an ordinary diffuse exposure, not a labelled diagram.
    comet = Image.new("L", image.size, 0)
    cd = ImageDraw.Draw(comet)
    cd.ellipse((444, 408, 478, 442), fill=215)
    cd.line((420, 434, 472, 421), fill=145, width=7)
    comet = comet.filter(ImageFilter.GaussianBlur(7.5))
    field = ImageChops.lighter(field.filter(ImageFilter.GaussianBlur(0.7)), comet)
    image = ImageChops.lighter(image, field)
    # Pillow performs the large pixel operations in native code.  Random
    # bytes still come from the caller-derived RNG, preserving cross-process
    # determinism without an 846,400-iteration Python render loop.
    falloff = Image.radial_gradient("L").resize(image.size, Image.Resampling.BICUBIC)
    falloff = falloff.point(lambda value: 255 - int(value * 0.32))
    image = ImageChops.multiply(image, falloff)
    noise = Image.frombytes("L", image.size, rng.randbytes(size * size))
    noise = noise.point(lambda value: 121 + int(value * 14 / 255))
    image = ImageChops.add(image, noise, scale=1.0, offset=-128)
    scratches = ImageDraw.Draw(image)
    for _ in range(6):
        x = rng.randrange(35, size - 35)
        scratches.line((x, 20, x + rng.randrange(-15, 16), size - 20),
                       fill=rng.randrange(22, 48), width=1)
    image = image.filter(ImageFilter.GaussianBlur(0.35))
    buf = io.BytesIO(); image.save(buf, "PNG")
    return buf.getvalue()


def _raking_jacket_png(seed: int, *, writer: str) -> bytes:
    """Directional-light record of an overwritten plate-jacket surface."""
    rng = random.Random(seed)
    width, height = 1000, 760
    base = Image.new("L", (width, height), 205)
    # Raking illumination falls left-to-right, with paper fibers and one
    # localized abraded correction patch instead of uniform digital speckle.
    gradient = Image.linear_gradient("L").rotate(90, expand=True).resize((width, height))
    gradient = gradient.point(lambda value: 210 + int(value * 30 / 255))
    base = ImageChops.multiply(base, gradient)
    noise = Image.frombytes("L", (width, height), rng.randbytes(width * height))
    noise = noise.point(lambda value: 124 + int(value * 10 / 255))
    base = ImageChops.add(base, noise, offset=-128)
    image = base.convert("RGBA")
    draw = ImageDraw.Draw(image)
    for _ in range(70):
        y = rng.randrange(25, height - 25)
        x = rng.randrange(10, width - 120)
        draw.line((x, y, x + rng.randrange(40, 180), y + rng.choice((-1, 0, 1))),
                  fill=(118, 110, 98, rng.randrange(12, 28)), width=1)

    def hand_layer(text: str, entry_seed: int, target_width: int) -> Image.Image:
        raw = Image.open(io.BytesIO(assets.handwriting_png(
            entry_seed, text=text, writer=writer))).convert("RGBA")
        target_height = max(28, int(raw.height * target_width / raw.width))
        return raw.resize((target_width, target_height), Image.Resampling.LANCZOS)

    old = hand_layer("probable minor planet", seed + 1, 430)
    new = hand_layer("S.W. candidate", seed + 2, 330)
    old_mask = old.getchannel("A")
    ox, oy = 130, 282

    # Indentation: a light lip on the illuminated side and a dark trough on
    # the lee side. The offsets make the left-hand light direction provable.
    highlight = Image.new("L", image.size, 0); highlight.paste(old_mask, (ox - 3, oy - 1))
    shadow = Image.new("L", image.size, 0); shadow.paste(old_mask, (ox + 4, oy + 2))
    image = Image.composite(Image.new("RGBA", image.size, (244, 240, 225, 255)),
                            image, highlight.point(lambda value: int(value * 0.34)))
    image = Image.composite(Image.new("RGBA", image.size, (88, 79, 69, 255)),
                            image, shadow.point(lambda value: int(value * 0.29)))

    # Local abrasion around the superseded phrase disturbs fibers only where
    # a rubber or blade worked the surface.
    abrasion = Image.new("L", image.size, 0)
    ad = ImageDraw.Draw(abrasion)
    ad.rounded_rectangle((112, 264, 590, 358), radius=28, fill=80)
    for _ in range(280):
        ad.point((rng.randrange(125, 575), rng.randrange(275, 347)),
                 fill=rng.randrange(35, 115))
    image = Image.composite(Image.new("RGBA", image.size, (226, 221, 207, 255)),
                            image, abrasion.filter(ImageFilter.GaussianBlur(1.3)))

    faded = old.copy()
    faded.putalpha(old_mask.point(lambda value: int(value * 0.42)))
    image.alpha_composite(faded, (ox, oy))
    draw = ImageDraw.Draw(image)
    draw.line((104, 344, 610, 286), fill=(54, 47, 43, 205), width=4)
    image.alpha_composite(new, (172, 414))
    initials = hand_layer("S.W.", seed + 3, 110)
    image.alpha_composite(initials, (720, 585))
    buf = io.BytesIO(); image.convert("RGB").save(buf, "PNG")
    return buf.getvalue()


def _type(c, lines: list[str], x: float, y: float, *, size: float = 10,
          leading: float = 14) -> None:
    c.setFillGray(0.1)
    c.setFont("Courier", size)
    for line in lines:
        c.drawString(x, y, line)
        y -= leading


def _grid(c, x: float, y: float, widths: list[float], rows: int,
          row_h: float, headers: list[str], *, period_ruling: bool = False) -> None:
    total = sum(widths)
    c.saveState()
    c.setLineWidth(0.55)
    if period_ruling:
        c.setStrokeColorRGB(0.23, 0.31, 0.49)
    else:
        c.setStrokeGray(0.45)
    for row in range(rows + 1):
        c.line(x, y - row * row_h, x + total, y - row * row_h)
    if period_ruling:
        c.setStrokeColorRGB(0.69, 0.25, 0.23)
    at = x
    for width in widths:
        c.line(at, y, at, y - rows * row_h)
        at += width
    c.line(at, y, at, y - rows * row_h)
    c.setFillGray(0.13)
    c.setFont("Times-Bold", 6.5)
    at = x
    for label, width in zip(headers, widths):
        c.drawCentredString(at + width / 2, y - 10, label)
        at += width
    c.restoreState()


def _night_log_rows(m: dict, tf: dict[str, str]) -> tuple[tuple[str, ...], ...]:
    """Ordinary surrounding work plus the canon-bearing final exposure.

    The earlier rows are texture from the same local series, not independent
    clue facts.  Shared field values come from the same model so a ledger row
    cannot drift from the plate and reduction records.
    """
    suffix = lambda value: str(value).rsplit("-", 1)[-1]
    return (
        ("0414", "FOCUS", "", "", "24-R", "AGFA",
         "05 31 08", "05 31 38", "", "30", "S.W."),
        ("0415", "B-17 TEST", m["field_ra"], m["field_dec"],
         "\"", "\"", "05 34 03", "05 35 03", "E 00 03", "60", "\""),
        (suffix(m["comparison_plate_id"]), "B-17 COMP", "\"", "\"",
         "\"", "\"", "05 40 22", "05 41 52", "W 00 04", "90", "\""),
        (suffix(m["final_plate_id"]), "B-17 LOCAL", m["field_ra"],
         m["field_dec"], "24-R", "AGFA", tf["corrected_start_lst"],
         tf["corrected_stop_lst"], tf["hour_angle"], "90", "S.W."),
    )


def _signature(c, seed: int, name: str, x: float, y: float, width: float = 115) -> None:
    png = assets.signature_png(seed, name=name, ink=(18, 24, 42))
    image = ImageReader(io.BytesIO(png))
    iw, ih = image.getSize()
    c.drawImage(image, x, y, width=width, height=width * ih / iw, mask="auto")


def _compose_vector(m: dict, defect: dict | None) -> tuple[bytes, list[list[str]]]:
    defect = dict(defect or {})
    unknown = set(defect) - {"correction_sign"}
    if unknown:
        raise ValueError(f"unsupported observatory defect: {sorted(unknown)}")
    if defect.get("correction_sign") not in {None, "reverse"}:
        raise ValueError("correction_sign defect must be 'reverse'")
    displayed = (m["culprit_correction_seconds"]
                 if defect.get("correction_sign") == "reverse"
                 else m["true_correction_seconds"])
    sign = "+" if displayed >= 0 else "-"
    correction_text = f"{sign}{abs(displayed):04.1f} seconds"
    tf = _time_facts(m)
    cf = _civil_facts(m)

    rng = random.Random(m["scan_seed"])
    buffer = io.BytesIO()
    c = rl_canvas.Canvas(buffer, pagesize=letter, invariant=1)
    c.setTitle("")
    pages: list[list[str]] = []

    def finish(lines: list[str], *, archive_leaf: bool = False) -> None:
        if archive_leaf:
            _footer(c, m, len(pages) + 1)
        pages.append(lines)
        c.showPage()

    # 1. Folder inventory
    lines = _header(c, "FILE INVENTORY", f"{m['folder_number']} / {m['represented_night']}", form=True)
    _type(c, [m["observatory"].upper(), m["location"].upper(), "",
              "SEPARATE OBJECTS - PRESERVE ORDER AND PLATE IDENTITIES"], MARGIN, 690)
    for index, marker in enumerate(PAGE_MARKERS[1:], 1):
        _type(c, [f"{index:02d}  {marker}"], 62, 628 - index * 25, size=8.4)
    finish(lines + list(PAGE_MARKERS[1:]), archive_leaf=True)

    # 2. Same-year observing-log form calibrated to the DDO excerpt.  Book,
    # leaf, date and institution remain ordinary ledger fields rather than a
    # modern slash-separated provenance breadcrumb.
    _paper(c, 0.905, material="ledger", key="NIGHT OBSERVING LOG")
    c.setFillGray(0.13)
    c.setFont("Times-Bold", 9.5)
    c.drawString(34, 748, m["observatory"])
    c.setFont("Times-Bold", 11)
    c.drawCentredString(PAGE_W / 2, 748, "NIGHT OBSERVING LOG")
    c.setFont("Courier", 7.5)
    c.drawString(34, 715, "BOOK IV")
    c.drawCentredString(PAGE_W / 2, 715, "LEAF 117")
    c.drawRightString(PAGE_W - 34, 715, f"NIGHT {m['represented_night'].upper()}")
    c.setLineWidth(0.5)
    c.line(34, 704, PAGE_W - 34, 704)
    lines = ["NIGHT OBSERVING LOG", m["observatory"],
             "BOOK IV", "LEAF 117", f"NIGHT {m['represented_night'].upper()}"]
    headers = ["PLATE", "OBJECT", "R.A. 1900", "DEC. 1900", "TEL.",
               "EMUL.", "LST START", "LST END", "H.A. MID", "EXP.", "OBS."]
    widths = [44, 62, 55, 55, 40, 40, 55, 55, 70, 42, 38]
    _grid(c, 28, 666, widths, 8, 48, headers, period_ruling=True)
    log_rows = _night_log_rows(m, tf)
    for row, values in enumerate(log_rows):
        x = 28
        row_y = 626 - row * 48
        for cell, (value, width) in enumerate(zip(values, widths)):
            if value:
                _ink(c, str(value), x + 2, row_y - 4,
                     seed=m["scan_seed"] + 200 + row * 20 + cell,
                     writer=m["astronomer"], width=max(28, width - 7), height=9.6)
            x += width
    _ink(c, f"Seeing 2; {m['weather_temp_f']} F; drive contact lost after exposure",
         36, 264, seed=m["scan_seed"] + 212, writer=m["astronomer"],
         width=330, height=10.5)
    _ink(c, f"{m['curator']} / plate {m['final_plate_id']} to vault 10:02 P.M.",
         36, 232, seed=m["scan_seed"] + 213, writer=m["curator"],
         width=265, height=10.5)
    lines += ["Night Book IV leaf 117 Plate Object R.A. 1900 Declination 1900 Telescope Emulsion Starting Time L.S.T. Ending Time L.S.T. Hour Angle Mid Exposure Observer",
              *(" ".join(row) for row in log_rows),
              f"{m['final_plate_id']} B-17 LOCAL RA {m['field_ra']} Dec {m['field_dec']} corrected LST {tf['corrected_start_lst']} to {tf['corrected_stop_lst']} HA {tf['hour_angle']} exposure 90 seconds observer S.W.",
              f"Seeing 2 Temperature {m['weather_temp_f']} F drive contact lost after exposure",
              f"{m['curator']} plate {m['final_plate_id']} to vault 10:02 P.M."]
    finish(lines)

    # 3. Plate jacket as a distinct object.
    lines = [f"PLATE JACKET {m['final_plate_id']}", "paper envelope recto"]
    _paper(c, 0.79, material="envelope", key="plate-jacket-1937")
    c.saveState(); c.translate(306, 395); c.rotate(-1.35); c.translate(-306, -395)
    c.setFillGray(0.61); c.setStrokeGray(0.61); c.roundRect(82, 150, 464, 470, 4, fill=1)
    c.setStrokeGray(0.33); c.setFillGray(0.84); c.roundRect(70, 164, 464, 470, 3, fill=1)
    c.setStrokeGray(0.48); c.setLineWidth(0.45)
    for offset in range(0, 450, 23):
        c.line(76 + offset, 168, 86 + offset, 171)
    c.line(70, 560, 302, 448); c.line(534, 560, 302, 448)
    _type(c, [m["observatory"].upper(), "PHOTOGRAPHIC PLATE STORE",
              "LOCAL SERIES V / JACKET FORM P-4",
              f"SERIES / NUMBER:  {m['final_plate_id']}",
              f"DATE-NIGHT:       {m['represented_night']}",
              f"OBJECT:           {m['object_name']}",
              f"TELESCOPE:        {m['instrument']}",
              f"PLATE:            {m['plate_class']}", "EXPOSURE:         90 SEC. / S.W.",
              f"ISSUED:           R. BELL", "RETURNED:         10:02 P.M."], 112, 408, size=9.4, leading=22)
    _ink(c, "do not clean reverse notes", 112, 174,
         seed=m["scan_seed"] + 301, writer=m["curator"], width=190, height=10)
    c.restoreState()
    lines += [m["observatory"], "PHOTOGRAPHIC PLATE STORE", "LOCAL SERIES V / JACKET FORM P-4",
              m["final_plate_id"], f"DATE-NIGHT {m['represented_night']}", m["object_name"],
              f"TELESCOPE {m['instrument']}", f"PLATE {m['plate_class']}",
              "EXPOSURE 90 SEC. / S.W.", "ISSUED R. BELL", "RETURNED 10:02 P.M.",
              "do not clean reverse notes"]
    finish(lines)

    # 4. Contact reproduction of a plate: field, not magical clock.
    lines = [f"CONTACT REPRODUCTION {m['final_plate_id']}", "glass plate emulsion side"]
    _paper(c, 0.76, material="photographic-copy", key="plate-contact-1937")
    c.setFillGray(0.58); c.rect(68, 134, 476, 506, fill=1, stroke=0)
    plate = ImageReader(io.BytesIO(_plate_png(m["scan_seed"] + 400)))
    c.drawImage(plate, 78, 144, width=456, height=486, mask="auto")
    c.setFillGray(0.91); c.setStrokeGray(0.35); c.rect(90, 65, 432, 54, fill=1)
    c.setFillGray(0.12); c.setFont("Courier", 7.5)
    c.drawString(104, 96, f"{m['observatory'].upper()} / LOCAL SERIES V / PLATE {m['final_plate_id']}")
    c.drawString(104, 79, f"CENTRE {m['field_ra']}  {m['field_dec']}  SCALE 60\"/MM  CARD 17-A")
    lines += [m["observatory"], "LOCAL SERIES V", f"PLATE {m['final_plate_id']}",
              f"CENTRE {m['field_ra']} {m['field_dec']}", "SCALE 60 arcseconds per millimetre",
              "CARD 17-A"]
    finish(lines)

    # 5. Chronograph: mechanical regulator beats and exposure contacts.
    lines = [f"CHRONOGRAPH STRIP {m['final_plate_id']}",
             f"{m['observatory']} time room / mounting card C-3 / drum 3 / sidereal standard S-2"]
    _paper(c, 0.76, material="chronograph", key="chronograph-strip-1937")
    c.setFillGray(0.55); c.rect(29, 128, 554, 520, fill=1, stroke=0)
    c.setFillGray(0.88); c.setStrokeGray(0.34); c.rect(43, 145, 526, 486, fill=1)
    c.setStrokeGray(0.18)
    # Nine ten-second lines instantiate the full 90-second exposure rather
    # than merely labelling an arbitrary decorative trace as ninety seconds.
    for band in range(CHRONOGRAPH_BEAT_COUNT // 10):
        baseline = 594 - band * 50
        path = c.beginPath(); path.moveTo(54, baseline)
        for step in range(1, 11):
            x = 54 + step * 50.0
            floor = baseline + rng.uniform(-0.55, 0.55)
            path.lineTo(x - 1.6, floor)
            path.lineTo(x, floor + rng.uniform(6.3, 8.1))
            path.lineTo(x + 1.4, floor)
        c.setLineWidth(rng.uniform(0.45, 0.85)); c.drawPath(path, stroke=1, fill=0)
    c.setLineWidth(1.15)
    c.line(54, 582, 54, 611)
    c.line(555, 182, 555, 211)
    c.setFont("Courier", 6.5); c.setFillGray(0.2)
    c.drawString(46, 618, "OPEN")
    c.drawRightString(563, 166, "CLOSE")
    c.drawCentredString(306, 139, "MOUNTING CARD C-3 / 1 SECOND PER BEAT / 10 SECONDS PER LINE")
    c.drawString(48, 139, "OP. T.R.")
    _ink(c, f"open {m['raw_start_lst']}", 70, 654,
         seed=m["scan_seed"] + 501, writer=m["engineer"], width=145)
    _ink(c, f"close {m['raw_stop_lst']}", 400, 652,
         seed=m["scan_seed"] + 502, writer=m["engineer"], width=150)
    _ink(c, "mains contact out; beats continue", 174, 95,
         seed=m["scan_seed"] + 503, writer=m["engineer"], width=270)
    lines += [m["observatory"], m["final_plate_id"], "MOUNTING CARD C-3", "DRUM 3 SIDEREAL STANDARD S-2",
              "1 SECOND PER BEAT / 10 SECONDS PER LINE", "OP. T.R.",
              f"open {m['raw_start_lst']}", f"close {m['raw_stop_lst']}",
              "mains contact out; beats continue"]
    finish(lines)

    # 6. Only defect-bearing page.
    lines = _header(c, "SIDEREAL STANDARD CORRECTION", f"{m['observatory']} / Time Service sheet S-2-1937-016", form=True)
    _type(c, ["Clock: Sidereal standard S-2     Date: 16 January 1937",
              "Comparison: U.S. Naval Observatory radio time / 18:00 E.S.T.",
              "Comparison prepared: T. ROOK",
              "Measured result: S-2 FAST 56.8 SEC.",
              f"Observation: local-series plate {m['final_plate_id']}",
              f"Mid-exposure clock reading ........ {tf['raw_midpoint_lst']}",
              "",
              f"CORRECTION ENTERED BY F. MERCER ... {correction_text}", "",
              "Reduction destination: desk sheet R-17 / plate ledger IV-117",
              "Mercer signature:"], 58, 646, size=9.1, leading=27)
    _signature(c, m["scan_seed"] + 601, m["trustee"], 178, 282, 108)
    lines += [m["observatory"], "Time Service sheet S-2-1937-016",
              "Clock Sidereal standard S-2 Date 16 January 1937",
              "Comparison U.S. Naval Observatory radio time 18:00 E.S.T.",
              "Comparison prepared T. ROOK", "Measured result S-2 FAST 56.8 SEC.",
              f"Observation local-series plate {m['final_plate_id']}",
              f"Mid-exposure clock reading {tf['raw_midpoint_lst']}",
              f"CORRECTION ENTERED BY F. MERCER {correction_text}",
              "Reduction destination desk sheet R-17 plate ledger IV-117", "Mercer signature"]
    finish(lines)

    # 7. Independent radio-rate notebook.
    lines = _header(c, "RADIO RATE NOTEBOOK", f"{m['observatory']} / Time Book II leaf 36 / receiver {m['receiver']}", form=True)
    _grid(c, 42, 650, [86, 106, 92, 92, 86, 60], 9, 43,
          ["DATE / EST", "AUTHORITY", "CLOCK", "FAST", "RATE", "OP."])
    entries = [
        ("JAN 14 18:00", "U.S.N.O.", "S-2", "56.70 S", "+0.05 S/D", "T.R."),
        ("JAN 15 18:00", "U.S.N.O.", "S-2", "56.75 S", "+0.05 S/D", "T.R."),
        ("JAN 16 18:00", "U.S.N.O.", "S-2", "56.80 S", "+0.05 S/D", "T.R."),
    ]
    for row, entry in enumerate(entries, 1):
        x = 42
        for cell, (value, width) in enumerate(zip(entry, [86, 106, 92, 92, 86, 60])):
            _ink(c, value, x + 4, 650 - row * 43 + 5, writer=m["engineer"],
                 seed=m["scan_seed"] + 700 + row * 10 + cell,
                 width=max(40, width - 10)); x += width
    _ink(c, "S-2 fast; subtract 56.8 s", 66, 225,
         seed=m["scan_seed"] + 741, writer=m["engineer"], width=190)
    _ink(c, "U.S.N.O. signal sets error; daily difference sets rate", 66, 194,
         seed=m["scan_seed"] + 742, writer=m["engineer"], width=300)
    lines += [m["observatory"], "Time Book II leaf 36", f"receiver {m['receiver']}",
              "JAN 14 18:00 U.S.N.O. S-2 FAST 56.70 SEC +0.05 S/D T.R.",
              "JAN 15 18:00 U.S.N.O. S-2 FAST 56.75 SEC +0.05 S/D T.R.",
              "JAN 16 18:00 U.S.N.O. S-2 FAST 56.80 SEC +0.05 S/D T.R.",
              "S-2 fast subtract 56.8 seconds",
              "U.S.N.O. signal sets error daily difference sets rate"]
    finish(lines)

    # 8. Ordinary completed reduction sheet; it records work, not its meaning.
    lines = _header(c, "RA - HA - LST REDUCTION", f"{m['observatory']} / Reduction desk sheet R-17 / 17 January 1937", form=True)
    _type(c, [f"PLATE {m['final_plate_id']}",
              f"R.A. {m['field_ra']} + H.A. {tf['hour_angle']} = L.S.T. {tf['expected_lst']}", "",
              f"Raw S-2 contacts: {m['raw_start_lst']} / {m['raw_stop_lst']}",
              f"Raw S-2 midpoint: {tf['raw_midpoint_lst']}",
              f"Clock correction used: {m['true_correction_seconds']:+04.1f} seconds / T.R.",
              f"Corrected contacts: {tf['corrected_start_lst']} / {tf['corrected_stop_lst']}",
              "Reduced: S. WREN / entered Night Book IV leaf 117"], 58, 658, size=8.8, leading=25)
    lines += [m["observatory"], "Reduction desk sheet R-17 17 January 1937",
              f"Plate {m['final_plate_id']} RA {m['field_ra']} HA {tf['hour_angle']} LST {tf['expected_lst']}",
              f"Raw S-2 contacts {m['raw_start_lst']} {m['raw_stop_lst']} midpoint {tf['raw_midpoint_lst']}",
              f"Clock correction used {m['true_correction_seconds']:+04.1f} seconds T.R.",
              f"Corrected contacts {tf['corrected_start_lst']} {tf['corrected_stop_lst']}",
              "Reduced S. Wren entered Night Book IV leaf 117"]
    finish(lines)

    # 9. Maintenance: a bounded real error, not the alibi-sized sign fault.
    lines = _header(c, "DOME AND CLOCK MAINTENANCE", f"{m['observatory']} / Plant Book III leaf 22 / January 1937", form=True)
    _grid(c, 50, 656, [82, 100, 220, 110], 10, 46, ["DATE", "SYSTEM", "WORK", "INITIALS"])
    records = [
        ("JAN 16", "S-2 contact", "Contact cleaned; unauthorized adjustment", "T.R."),
        ("JAN 15", "rate check", "Change under one second for reunion interval", "T.R."),
        ("JAN 16", "dome drive", "Motor circuit serviceable before storm", "T.R."),
        ("JAN 16", "chase C", "Old weight removed; panel and lock retained", "T.R."),
    ]
    for row, record in enumerate(records, 1):
        x = 50
        for cell, (value, width) in enumerate(zip(record, [82, 100, 220, 110])):
            _ink(c, value, x + 4, 656 - row * 46 + 4,
                 seed=m["scan_seed"] + 900 + row * 10 + cell,
                 writer=m["engineer"],
                 width=max(42, width - 12)); x += width
    c.setStrokeGray(0.22); c.setLineWidth(0.8); c.line(91, 621, 128, 619)
    _ink(c, "12", 96, 630, seed=m["scan_seed"] + 956,
         writer=m["engineer"], width=22, height=9)
    lines += [m["observatory"], "Plant Book III leaf 22 / January 1937",
              "JAN 16 struck through and JAN 12 entered / S-2 contact / Contact cleaned; unauthorized adjustment / T.R.",
              "JAN 15 / rate check / Change under one second for reunion interval / T.R.",
              "JAN 16 / dome drive / Motor circuit serviceable before storm / T.R.",
              "JAN 16 / chase C / Old weight removed; panel and lock retained / T.R."]
    finish(lines)

    # 10. Public circular, visibly amended brightness.
    lines = _header(c, "CIRCULAR 37-1", "Vale Observatory / January 1937")
    _type(c, ["TO THE PRESS AND SUBSCRIBING STATIONS", "",
              f"Internal field label: {m['object_name']}",
              "Elements provisional; positions are for finder use only.", "",
              "Jan. 16, 10 P.M. EST   R.A. 05h 37m   Decl. +32 10",
              "Estimated magnitude: 8.1", "",
              "Copies to: North Notch Press, radio desk, subscriber circular list"], 58, 650, size=9.5, leading=30)
    c.setStrokeGray(0.2); c.setLineWidth(1.2); c.line(176, 468, 198, 468)
    _ink(c, "5.8", 172, 452, seed=m["scan_seed"] + 1001, writer=m["donor_representative"], width=39)
    _ink(c, "L.H.", 420, 390, seed=m["scan_seed"] + 1002, writer=m["donor_representative"], width=52)
    lines += [m["observatory"], "CIRCULAR 37-1 / January 1937",
              "TO THE PRESS AND SUBSCRIBING STATIONS",
              f"Internal field label {m['object_name']}",
              "Elements provisional; positions are for finder use only",
              "Jan. 16, 10 P.M. EST / R.A. 05h 37m / Decl. +32 10",
              "Estimated magnitude 8.1 struck through and 5.8 entered", "L.H.",
              "Copies to North Notch Press, radio desk, subscriber circular list"]
    finish(lines)

    # 11. Finance schedule derived from one principal and diversion.
    lines = _header(c, "ENDOWMENT TRANSFER SCHEDULE", f"{m['observatory']} / Treasurer copy / {m['transfer_reference']}", form=True)
    _type(c, ["RESTRICTED INSTRUMENT ENDOWMENT — CUSTODIAN ADVICE", "STATUS: POSTED 16 JANUARY 1937 / LEDGER 41, FOLIO 6", "",
              "Account ............ Instrument Reserve 41-6",
              f"Advice date ........ 16 January 1937    Voucher {m['transfer_reference']}",
              f"Opening principal ... {_fmt_money(m['restricted_principal'])}",
              f"Debit — collateral .. {_fmt_money(m['diverted_amount'])}",
              f"Balance forward ..... {_fmt_money(m['restricted_balance'])}", "",
              "Payee advice ........ North Notch Equipment Holding Co.",
              "Remittance .......... cashier's draft 0116-C", "",
              "Authorized .......... F. Mercer, Trustee",
              "Second trustee ....... [blank]"], 58, 650, size=9.2, leading=27)
    _signature(c, m["scan_seed"] + 1101, m["trustee"], 324, 174, 118)
    lines += [m["observatory"], "ENDOWMENT TRANSFER SCHEDULE",
              "RESTRICTED INSTRUMENT ENDOWMENT — CUSTODIAN ADVICE",
              "STATUS POSTED 16 JANUARY 1937 / LEDGER 41, FOLIO 6",
              "Account Instrument Reserve 41-6",
              f"Advice date 16 January 1937 / Voucher {m['transfer_reference']}",
              f"Opening principal {_fmt_money(m['restricted_principal'])}",
              f"Debit — collateral {_fmt_money(m['diverted_amount'])}",
              f"Balance forward {_fmt_money(m['restricted_balance'])}",
              "Payee advice North Notch Equipment Holding Co.",
              "Remittance cashier's draft 0116-C", f"Authorized {m['trustee']}, Trustee",
              "Second trustee [blank]"]
    finish(lines)

    # 12. Vale's unfinished confession.
    lines = _header(c, "CARBON LETTER - TRUSTEES", f"{m['observatory']} / retained desk carbon / draft 2 / 16 January 1937", form=True)
    _type(c, [f"From: {m['founder']}, Director", "Draft — not issued", "",
              "To the Trustees and the Astronomical Community:", "",
              f"The first identification on plate {m['early_plate_id']} was Ruth Bell's.",
              "I published the result under my name and permitted the record to stand.",
              "Tonight I intend to restore her credit and submit the endowment books", "to an independent audit.  The observatory cannot ask reality to remember", "only those facts that preserve its founder."], 62, 652, size=9.5, leading=29)
    lines += [m["observatory"], "CARBON LETTER - TRUSTEES",
              "retained desk carbon / draft 2 / 16 January 1937",
              f"From {m['founder']}, Director", "Draft — not issued",
              "To the Trustees and the Astronomical Community",
              f"The first identification on plate {m['early_plate_id']} was Ruth Bell's",
              "I published the result under my name and permitted the record to stand",
              "Tonight I intend to restore her credit and submit the endowment books to an independent audit",
              "The observatory cannot ask reality to remember only those facts that preserve its founder"]
    finish(lines)

    # 13. Carbon appointment slip.
    lines = _header(c, "PLATE VAULT APPOINTMENT", f"{m['observatory']} / Director desk carbon / 16 January 1937", form=True)
    c.setStrokeGray(0.35); c.rect(96, 286, 420, 310, fill=0)
    _type(c, ["FELIX -", "", "PLATE VAULT. TEN O'CLOCK.", "BRING TRANSFER SCHEDULE T-37-0116-M.", "", "A. VALE"], 132, 542, size=12, leading=42)
    lines += [m["observatory"], "Director desk carbon 16 January 1937", "Felix", "Plate vault ten o'clock", f"Bring transfer schedule {m['transfer_reference']}", "A. Vale"]
    finish(lines)

    # 14. Key register.
    lines = _header(c, "SERVICE KEY REGISTER", f"{m['observatory']} / Plant Book III leaf 23 / dome ground floor / key C", form=True)
    _grid(c, 58, 646, [82, 140, 115, 115, 92], 9, 46,
          ["DATE", "HOLDER", "OUT", "IN", "PURPOSE"])
    records = [
        ("JAN 15", "T. ROOK", "3:20 P.M.", "4:05 P.M.", "drive oil"),
        ("JAN 16", m["trustee"].upper(), m["service_key_out"], m["service_key_in"], "trustee inspection"),
    ]
    for row, record in enumerate(records, 1):
        x = 58
        for cell, (value, width) in enumerate(zip(record, [82, 140, 115, 115, 92])):
            _ink(c, value, x + 4, 646 - row * 46 + 4,
                 seed=m["scan_seed"] + 1400 + row * 10 + cell,
                 writer=m["engineer"],
                 width=max(42, width - 12)); x += width
    _ink(c, "C panel", 72, 207, seed=m["scan_seed"] + 1451, writer=m["engineer"], width=65)
    lines += [m["observatory"], "Plant Book III leaf 23 / dome ground floor / key C",
              "JAN 15 / T. ROOK / 3:20 P.M. / 4:05 P.M. / drive oil",
              f"JAN 16 / {m['trustee'].upper()} / {m['service_key_out']} / {m['service_key_in']} / trustee inspection",
              "C panel"]
    finish(lines)

    # 15. Controlled facilities drawing: solid isolated pier and a separately
    # dimensioned service chase, calibrated to the sourced HABS sheet grammar.
    lines = _header(c, "DOME GROUND-FLOOR PLAN", f"{m['observatory']} / drawing D-4 / revision 1", form=True)
    c.setStrokeGray(0.16); c.setLineWidth(0.65)
    c.rect(38, 68, 536, 650, fill=0)
    c.rect(42, 72, 528, 642, fill=0)

    # Circular masonry wall, inner clear face, south door and swing.
    c.setLineWidth(2.0); c.circle(280, 408, 188, fill=0)
    c.setLineWidth(0.65); c.circle(280, 408, 180, fill=0)
    c.setFillGray(0.94); c.rect(248, 214, 64, 28, fill=1, stroke=0)
    c.setStrokeGray(0.16); c.line(248, 228, 248, 278); c.line(312, 228, 312, 278)
    c.line(248, 228, 302, 272); c.arc(248, 218, 362, 332, startAng=90, extent=-53)
    c.setFont("Courier", 6.5); c.setFillGray(0.12); c.drawCentredString(280, 206, "D-1 / 3'-6\" DOOR")

    # Pier isolation joint and telescope pier.
    c.setDash(2, 2); c.setLineWidth(0.5); c.rect(210, 338, 140, 140, fill=0); c.setDash()
    c.setFillGray(0.77); c.setStrokeGray(0.12); c.rect(220, 348, 120, 120, fill=1, stroke=1)
    c.setFillGray(0.10); c.setFont("Courier-Bold", 7.2)
    c.drawCentredString(280, 414, "8'-0\" CONCRETE PIER")
    c.setFont("Courier", 6.2); c.drawCentredString(280, 401, "2\" ISOLATION JOINT — NO WALL BEARING")

    # Clock-weight chase C: walls, access panel, travel and clearances.
    c.setFillGray(0.91); c.setStrokeGray(0.14); c.rect(367, 330, 60, 174, fill=1, stroke=1)
    c.setDash(4, 2); c.line(397, 344, 397, 489); c.setDash()
    c.line(367, 356, 342, 356); c.line(367, 389, 342, 389)
    c.setFont("Courier", 6.1); c.setFillGray(0.08)
    c.saveState(); c.translate(405, 346); c.rotate(90); c.drawString(0, 0, "CHASE C — 14'-0\" WEIGHT TRAVEL"); c.restoreState()
    c.drawRightString(363, 371, "P-3 LOCKED ACCESS")
    c.drawRightString(363, 342, "2'-6\" SERVICE CLEAR")

    # Switchboard and a real stair run with numbered treads.
    c.setFillGray(0.94); c.rect(126, 454, 54, 82, fill=1, stroke=1)
    c.setFillGray(0.08)
    c.drawCentredString(153, 491, "S-1")
    c.drawCentredString(153, 480, "SWITCHBOARD")
    c.rect(117, 282, 62, 119, fill=0)
    for tread in range(1, 9):
        y = 282 + tread * 13
        c.line(117, y, 179, y)
    c.line(148, 295, 148, 385); c.line(148, 385, 143, 375); c.line(148, 385, 153, 375)
    c.drawString(121, 268, "UP / 8 RISERS @ 7 1/2\"")

    # North arrow, plan dimensions and graphic scale.
    c.setLineWidth(0.8); c.line(502, 610, 502, 674); c.line(502, 674, 495, 660); c.line(502, 674, 509, 660)
    c.setFillGray(0.08); c.setFont("Helvetica-Bold", 9); c.drawCentredString(502, 682, "N")
    c.setFont("Courier", 6.2)
    c.line(92, 628, 468, 628); c.line(92, 620, 92, 636); c.line(468, 620, 468, 636)
    c.setFont("Courier-Bold", 7); c.drawCentredString(280, 615, "30'-0\" INSIDE DIAMETER")
    c.line(220, 322, 340, 322); c.line(220, 316, 220, 328); c.line(340, 316, 340, 328)
    c.drawCentredString(280, 309, "8'-0\"")
    c.setFillGray(0.08)
    for index in range(4):
        c.setFillGray(0.08 if index % 2 == 0 else 0.94)
        c.rect(188 + index * 24, 150, 24, 6, fill=1, stroke=1)
    c.setFillGray(0.08); c.drawString(188, 138, "0    2    4    6    8 FT")

    # Period drawing-control title block.
    c.setStrokeGray(0.12); c.rect(360, 82, 200, 102, fill=0)
    c.line(360, 152, 560, 152); c.line(360, 126, 560, 126); c.line(456, 82, 456, 126)
    c.setFont("Helvetica-Bold", 8); c.drawString(368, 169, m["observatory"].upper())
    c.setFont("Helvetica-Bold", 7); c.drawString(368, 157, "DOME GROUND-FLOOR SERVICE PLAN")
    c.setFont("Courier", 6.1)
    c.drawString(368, 140, "PROJECT: DRIVE & TIME-SERVICE ALTERATIONS")
    c.drawString(368, 131, "SCALE: 1/4\" = 1'-0\"")
    c.drawString(368, 114, "DRAWN: T.R.  12 JAN 1937")
    c.drawString(368, 101, "CHECKED: A.V. 15 JAN 1937")
    c.drawString(464, 114, "DWG. D-4")
    c.drawString(464, 101, "REV. 1")
    c.drawString(464, 88, "SHEET 4 OF 6")
    c.setFillGray(0.93); c.setStrokeGray(0.25); c.rect(54, 74, 288, 53, fill=1, stroke=1)
    c.setFillGray(0.12); c.setFont("Courier-Bold", 6.2)
    c.drawString(62, 116, "SERVICE RECOVERY NOTE / PLANT BOOK III")
    _ink(c, "17 Jan 10:42 — panel P-3 opened.", 62, 94,
         seed=m["scan_seed"] + 1501, writer=m["engineer"], width=190, height=9.5)
    _ink(c, "Body of Dr. Alistair Vale recovered from chase C. T.R.", 62, 78,
         seed=m["scan_seed"] + 1502, writer=m["engineer"], width=270, height=9.5)
    lines += [m["observatory"], "DOME GROUND-FLOOR SERVICE PLAN",
              "drawing D-4 / revision 1 / sheet 4 of 6", "scale 1/4 inch equals 1 foot",
              "north arrow", "30 foot inside diameter",
              "8 foot concrete pier / 2 inch isolation joint / no wall bearing",
              "chase C / 14 foot weight travel", "P-3 locked access",
              "2 foot 6 inch service clearance", "D-1 / 3 foot 6 inch door",
              "UP / 8 risers at 7 1/2 inches", "S-1 switchboard",
              "drawn T.R. 12 Jan 1937 / checked A.V. 15 Jan 1937",
              "SERVICE RECOVERY NOTE / PLANT BOOK III",
              "17 Jan 10:42 — panel P-3 opened",
              "Body of Dr. Alistair Vale recovered from chase C. T.R."]
    finish(lines)

    # 16. Local storm and utilities.
    lines = _header(c, "STORM AND POWER LOG", f"{m['observatory']} / Plant Book III leaf 24 / private spur and dome circuits", form=True)
    _grid(c, 52, 650, [95, 150, 265], 10, 45, ["TIME E.S.T.", "SYSTEM", "OBSERVATION"])
    records = [
        ("8:40 P.M.", "PRIVATE SPUR", f"drifted shut; {m['snow_depth_in']} in. at upper bend"),
        ("9:31 P.M.", "TELEPHONE", "overhead pair lost beyond gatehouse"),
        (m["blackout_civil_time"], "MAINS", "lights, dome motor, remote displays lost"),
        ("10:03:14", "S-2 REGULATOR", "mechanical standard continued"),
        ("10:05 P.M.", "GENERATOR", f"started; {m['generator_gallons']} gal.; lights only"),
        ("ALL NIGHT", "PUBLIC ROAD", "reported open to valley gate"),
    ]
    for row, record in enumerate(records, 1):
        x = 52
        for cell, (value, width) in enumerate(zip(record, [95, 150, 265])):
            _ink(c, value, x + 4, 650 - row * 45 + 4,
                 seed=m["scan_seed"] + 1600 + row * 10 + cell,
                 writer=m["engineer"],
                 width=max(46, width - 14)); x += width
    lines += [m["observatory"], "Plant Book III leaf 24 / private spur and dome circuits",
              f"8:40 P.M. / PRIVATE SPUR / drifted shut; {m['snow_depth_in']} in. at upper bend",
              "9:31 P.M. / TELEPHONE / overhead pair lost beyond gatehouse",
              f"{m['blackout_civil_time']} / MAINS / lights, dome motor, remote displays lost",
              "10:03:14 / S-2 REGULATOR / mechanical standard continued",
              f"10:05 P.M. / GENERATOR / started; {m['generator_gallons']} gal.; lights only",
              "ALL NIGHT / PUBLIC ROAD / reported open to valley gate"]
    finish(lines)

    # 17. Eleanor's bounded alteration.
    lines = _header(c, "FINAL OBSERVING ORDER", f"{m['observatory']} / Dome Order O-37-016 / issued 16 January 1937", form=True)
    order = ["Night January 16–17",
             f"1  Plate {m['comparison_plate_id']} — comparison field",
             f"2  Plate {m['final_plate_id']} — {m['object_name']}",
             "3  Repeat plate 0417", "3  Repeat plate 0417", "5", "A. Vale"]
    for row, text in enumerate(order):
        _ink(c, text, 76, 624 - row * 53,
             seed=m["scan_seed"] + 1700 + row, writer=m["founder"],
             width=330 if row < 5 else 90)
    lines += [m["observatory"], "Dome Order O-37-016 / issued 16 January 1937",
              "Night January 16–17", f"1 Plate {m['comparison_plate_id']} — comparison field",
              f"2 Plate {m['final_plate_id']} — {m['object_name']}",
              "3 Repeat plate 0417", "3 Repeat plate 0417", "5", "A. Vale"]
    finish(lines)

    # 18. Ruth's early plate envelope.
    lines = [f"EARLY PLATE ENVELOPE {m['early_plate_id']}", "archive pull copy"]
    _paper(c, 0.78, material="envelope", key="plate-envelope-1911")
    c.saveState(); c.translate(306, 394); c.rotate(0.8); c.translate(-306, -394)
    c.setFillGray(0.60); c.rect(84, 152, 460, 450, fill=1, stroke=0)
    c.setStrokeGray(0.33); c.setFillGray(0.82); c.rect(74, 170, 460, 450, fill=1)
    c.line(74, 536, 304, 440); c.line(534, 536, 304, 440)
    _type(c, [m["observatory"].upper(), f"PLATE {m['early_plate_id']}",
              "DATE: 17 FEB 1911"], 112, 520, size=9.5, leading=28)
    _ink(c, "B-17 field precursor", 112, 390,
         seed=m["scan_seed"] + 1801, writer=m["curator"], width=190)
    _ink(c, "R. Bell — object identified and measured", 112, 330,
         seed=m["scan_seed"] + 1802, writer=m["curator"], width=260)
    c.setFillGray(0.18); c.setFont("Courier", 7.5)
    c.drawString(112, 242, "ARCHIVE CHARGE: R.B. / 16 JAN 1937")
    c.restoreState()
    lines += [m["observatory"], "local series V", m["early_plate_id"], "17 February 1911", "B-17 field precursor", "R. Bell object identified and measured", "Archive charge R.B. 16 Jan 1937"]
    finish(lines)

    # 19. Wren's overwritten jacket.
    lines = [f"PLATE JACKET {m['comparison_plate_id']} - RAKING-LIGHT COPY"]
    _paper(c, 0.72, material="raking-copy", key="plate-raking-copy-1937")
    raking = ImageReader(io.BytesIO(_raking_jacket_png(
        m["scan_seed"] + 1900, writer=m["astronomer"])))
    c.drawImage(raking, 66, 158, width=480, height=456, mask="auto")
    c.setStrokeGray(0.34); c.rect(66, 158, 480, 456, fill=0)
    c.setFillGray(0.17); c.setFont("Courier", 9)
    c.drawString(92, 578, f"{m['observatory'].upper()} / LOCAL SERIES V / PLATE {m['comparison_plate_id']}")
    c.setLineWidth(1.0); c.line(92, 646, 162, 646); c.line(162, 646, 151, 652); c.line(162, 646, 151, 640)
    c.setFont("Courier", 7); c.drawString(92, 656, "RAKING LIGHT FROM LEFT / 22.5 DEGREES")
    c.drawRightString(520, 138, "COPY RL-0416-1 / R. BELL / 17 JAN 1937")
    lines += [m["observatory"], "LOCAL SERIES V", f"PLATE {m['comparison_plate_id']}",
              "RAKING LIGHT FROM LEFT / 22.5 DEGREES",
              "probable minor planet struck through", "S.W. candidate", "S.W.",
              "COPY RL-0416-1 / R. BELL / 17 JAN 1937"]
    finish(lines)

    # 20. A fictional local comparison card licensed by sourced U.S.N.O./N.B.S.
    # time-service procedure. It does not claim to reproduce a federal form.
    lines = _header(
        c,
        "GATEHOUSE CHRONOMETER CARD L-2",
        f"{m['observatory']} / Time Service file / 16-17 JAN 1937",
        form=True,
    )
    _type(c, [
        "TIME AUTHORITY: U.S. NAVAL OBSERVATORY RADIO TIME",
        f"RADIO COMPARISON: 16 JANUARY 1937 / {m['radio_comparison_civil_time']}",
        f"MEAN-TIME CHRONOMETER: {m['mean_time_chronometer']}",
        "SIDEREAL STANDARD: S-2",
    ], 58, 654, size=8.6, leading=24)
    card_columns = [132, 132, 55, 200]
    card_headers = [
        f"{m['mean_time_chronometer']} E.S.T.",
        "S-2 CORRECTED L.S.T.",
        "OP.",
        "REFERENCE",
    ]
    _grid(c, 46, 520, card_columns, 4, 52, card_headers)
    card_row = (
        cf["honest_plate_close_civil_time"],
        tf["corrected_stop_lst"],
        "T.R.",
        f"PLATE {m['final_plate_id']} / CLOSE",
    )
    x = 46
    for cell, (value, width) in enumerate(zip(card_row, card_columns)):
        _ink(
            c, value, x + 4, 480,
            seed=m["scan_seed"] + 2000 + cell,
            writer=m["engineer"], width=max(42, width - 12), height=10,
        )
        x += width
    _type(c, [
        "TIME-SERVICE CROSS-CHECK / 17 JAN 1937",
        "TIME BOOK II: S-2 FAST 56.8 SEC.",
        "SHEET S-2-1937-016: +56.8 SEC. / F. MERCER",
        f"S-2 SHEET CLOSE: {cf['false_plate_close_civil_time']}",
        f"LIBRARY REGISTER (MINUTE ENTRY): F. MERCER / {cf['library_entry_civil_time']}",
    ], 58, 270, size=8.3, leading=27)
    c.setStrokeGray(0.28)
    c.setLineWidth(0.7)
    c.line(58, 145, 554, 145)
    c.setFillGray(0.18)
    c.setFont("Courier", 6.5)
    c.drawString(58, 130, "LOCAL CARD / PROCEDURE SOURCE: U.S.N.O. RADIO COMPARISON")
    c.drawRightString(554, 130, "FILE L-2 / T.R.")
    lines += [
        m["observatory"],
        "Time Service file / 16-17 JAN 1937",
        "TIME AUTHORITY U.S. NAVAL OBSERVATORY RADIO TIME",
        f"RADIO COMPARISON 16 JANUARY 1937 / {m['radio_comparison_civil_time']}",
        f"MEAN-TIME CHRONOMETER {m['mean_time_chronometer']}",
        "SIDEREAL STANDARD S-2",
        *card_headers,
        *card_row,
        "TIME-SERVICE CROSS-CHECK / 17 JAN 1937",
        "TIME BOOK II S-2 FAST 56.8 SEC.",
        "SHEET S-2-1937-016 +56.8 SEC. / F. MERCER",
        f"S-2 SHEET CLOSE {cf['false_plate_close_civil_time']}",
        f"LIBRARY REGISTER (MINUTE ENTRY) F. MERCER / {cf['library_entry_civil_time']}",
        "LOCAL CARD / PROCEDURE SOURCE U.S.N.O. RADIO COMPARISON",
        "FILE L-2 / T.R.",
    ]
    finish(lines)

    c.save()
    return buffer.getvalue(), pages


def render_packet(model: dict, *, metadata: dict, defect: dict | None = None,
                  scan_dpi: int = 150) -> bytes:
    """Compose every object into a noncanonical image-only review binder.

    The earlier emitter parked an invented transcript in the upper margin as
    invisible OCR.  These fictional archive captures now remain honest scans;
    structured accessible readings are supplied separately in display facts.
    """
    vector, _pages = _compose_vector(model, defect)

    return scan.rescan(
        vector,
        rng=random.Random(model["scan_seed"]),
        metadata=metadata,
        dpi=scan_dpi,
        profile=scan.ARCHIVAL_COLOR_PROFILE,
        capture_context=_packet_capture_context,
    )


def _single_vector_page(vector: bytes, page_index: int) -> bytes:
    """Extract one vector page before scanning so only that object is emitted."""
    try:
        import pypdfium2 as pdfium
    except ImportError as exc:  # pragma: no cover - declared dependency
        raise RuntimeError("observatory artifact extraction needs pypdfium2") from exc
    source = pdfium.PdfDocument(vector)
    if not 0 <= page_index < len(source):
        source.close()
        raise IndexError(f"observatory page index outside packet: {page_index}")
    single = pdfium.PdfDocument.new()
    try:
        single.import_pages(source, pages=[page_index])
        buffer = io.BytesIO()
        single.save(buffer)
        return buffer.getvalue()
    finally:
        single.close()
        source.close()


def _artifact_scan_seed(scan_seed: int, artifact_id: str) -> int:
    payload = f"observatory:{scan_seed}:{artifact_id}".encode("utf-8")
    return int.from_bytes(hashlib.sha256(payload).digest()[:8], "big")


def render_artifact(model: dict, *, artifact_id: str, metadata: dict,
                    defect: dict | None = None, scan_dpi: int = 150) -> bytes:
    """Render and scan one native evidence artifact.

    Every object receives an identity-derived scan seed.  Its bytes therefore
    do not depend on which other game artifacts were requested, their order,
    or whether a review binder was also compiled.
    """
    if artifact_id not in _ARTIFACT_BY_ID:
        raise KeyError(f"unknown observatory artifact {artifact_id!r}")
    if defect and artifact_id != "clock_correction":
        raise ValueError("the correction-sign defect belongs only to clock_correction")
    _identifier, _class_name, page_index = _ARTIFACT_BY_ID[artifact_id]
    vector, _pages = _compose_vector(model, defect)
    vector_page = _single_vector_page(vector, page_index)

    return scan.rescan(
        vector_page,
        rng=random.Random(_artifact_scan_seed(model["scan_seed"], artifact_id)),
        metadata=metadata,
        dpi=scan_dpi,
        profile=scan.ARCHIVAL_COLOR_PROFILE,
        capture_context=_artifact_capture_context(artifact_id),
    )
