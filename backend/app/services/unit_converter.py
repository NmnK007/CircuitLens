"""CircuitLens SI Unit Conversion and Formatting Engine.

Converts electrical strings (e.g. '1k', '4k7', '10uF', '5V', '10ms') to standard
SI values with explicit numerical magnitudes, and formats SI values for human
display and SPICE netlists.
"""

import re
from typing import Tuple
from ..schemas.circuit import SIValue, ComponentType

PREFIX_MULTIPLIERS = {
    "t": 1e12,
    "tera": 1e12,
    "g": 1e9,
    "giga": 1e9,
    "meg": 1e6,
    "mega": 1e6,
    "k": 1e3,
    "kilo": 1e3,
    "m": 1e-3,
    "milli": 1e-3,
    "u": 1e-6,
    "μ": 1e-6,
    "micro": 1e-6,
    "n": 1e-9,
    "nano": 1e-9,
    "p": 1e-12,
    "pico": 1e-12,
    "f": 1e-15,
    "femto": 1e-15,
}

UNIT_CANONICAL = {
    "ohm": "ohm",
    "ohms": "ohm",
    "ω": "ohm",
    "r": "ohm",
    "f": "F",
    "farad": "F",
    "farads": "F",
    "v": "V",
    "volt": "V",
    "volts": "V",
    "a": "A",
    "amp": "A",
    "amps": "A",
    "ampere": "A",
    "s": "s",
    "sec": "s",
    "second": "s",
    "seconds": "s",
    "hz": "Hz",
    "hertz": "Hz",
}


def _clean_float(val: float) -> float:
    """Format float to clean up standard IEEE-754 representation noise."""
    return float(f"{val:.12g}")


def parse_value_string(text: str, default_unit: str = "") -> SIValue:
    """Parse a string into an SIValue with magnitude in base SI units.
    
    Examples:
        "1k" -> magnitude=1000.0, unit="ohm" (if default_unit is ohm)
        "1kΩ" -> magnitude=1000.0, unit="ohm"
        "4k7" -> magnitude=4700.0, unit="ohm"
        "10uF" -> magnitude=1e-5, unit="F"
        "5V" -> magnitude=5.0, unit="V"
        "10ms" -> magnitude=0.01, unit="s"
        "100n" -> magnitude=1e-7, unit="F" (if default_unit is F)
    """
    if not text:
        raise ValueError("Cannot parse empty value string")

    raw = text.strip()

    # Check for engineering embedded prefix like '4k7', '2u2', '1r5'
    eng_match = re.fullmatch(r"^(\d+)([kKmMgGuUnNpPrR])(\d+)\s*([a-zA-ZΩμ]*)?$", raw)
    if eng_match:
        integer_part = eng_match.group(1)
        prefix_char = eng_match.group(2)
        fraction_part = eng_match.group(3)
        unit_part = eng_match.group(4) or default_unit

        num_val = float(f"{integer_part}.{fraction_part}")
        if prefix_char.lower() == "r":
            mult = 1.0
            resolved_unit = "ohm"
        elif prefix_char == "M":
            mult = 1e6
            resolved_unit = unit_part
        elif prefix_char == "m":
            mult = 1e-3
            resolved_unit = unit_part
        else:
            mult = PREFIX_MULTIPLIERS.get(prefix_char.lower(), 1.0)
            resolved_unit = unit_part

        canonical_unit = _resolve_unit(resolved_unit or default_unit)
        return SIValue(magnitude=_clean_float(num_val * mult), unit=canonical_unit)

    # Standard format: number optionally followed by prefix and unit
    # e.g. "10uF", "1000 ohm", "5 V", "-5V", "1e-5", "10 MEG"
    clean = raw.replace(" ", "")

    # Match numeric portion: optional sign, digits, optional decimal, optional exponent
    match = re.match(r"^([+-]?(?:\d+(?:\.\d*)?|\.\d+)(?:[eE][+-]?\d+)?)(.*)$", clean)
    if not match:
        raise ValueError(f"Invalid numeric value in '{text}'")

    num_str = match.group(1)
    suffix = match.group(2).strip()

    num_val = float(num_str)

    if not suffix:
        canonical_unit = _resolve_unit(default_unit or "unit")
        return SIValue(magnitude=_clean_float(num_val), unit=canonical_unit)

    # Parse suffix into multiplier and base unit
    mult, detected_unit = _parse_suffix(suffix, default_unit)
    canonical_unit = _resolve_unit(detected_unit or default_unit or "unit")

    return SIValue(magnitude=_clean_float(num_val * mult), unit=canonical_unit)


def _parse_suffix(suffix: str, fallback_unit: str = "") -> Tuple[float, str]:
    """Extract metric multiplier and unit name from suffix.
    
    Distinguishes uppercase 'M' (Mega = 1e6) from lowercase 'm' (milli = 1e-3).
    """
    s = suffix.strip()
    s_lower = s.lower()

    # Check for 'meg' prefix
    if s_lower.startswith("meg"):
        rest = s[3:].strip()
        return 1e6, rest or fallback_unit

    # Check for 'giga' / 'tera' / 'micro' / 'milli' / 'nano' / 'pico'
    for full_prefix in ("giga", "tera", "micro", "milli", "nano", "pico", "kilo"):
        if s_lower.startswith(full_prefix):
            mult = PREFIX_MULTIPLIERS[full_prefix]
            rest = s[len(full_prefix):].strip()
            return mult, rest or fallback_unit

    first_char = s[0]
    rest = s[1:].strip()

    # Capital 'M' without 'meg' is Mega (e.g. 2.2MΩ, 1M)
    if first_char == "M":
        return 1e6, rest or fallback_unit

    # Lowercase 'm' is milli (e.g. 500mV, 10ms)
    if first_char == "m":
        return 1e-3, rest or fallback_unit

    first_char_lower = first_char.lower()
    if first_char_lower in PREFIX_MULTIPLIERS:
        mult = PREFIX_MULTIPLIERS[first_char_lower]
        return mult, rest or fallback_unit

    # If first char is not a known multiplier prefix, treat entire suffix as unit
    return 1.0, s


def _resolve_unit(unit_str: str) -> str:
    """Normalize unit string to canonical name."""
    u = unit_str.strip().lower()
    return UNIT_CANONICAL.get(u, unit_str.strip())


def format_value(value: SIValue) -> str:
    """Format an SIValue with appropriate engineering prefix for UI display."""
    mag = value.magnitude
    unit = value.unit

    if mag == 0:
        return f"0 {unit}"

    sign = "-" if mag < 0 else ""
    abs_mag = abs(mag)

    if abs_mag >= 1e9:
        return f"{sign}{abs_mag / 1e9:.3g} G{_format_unit_symbol(unit)}"
    elif abs_mag >= 1e6:
        return f"{sign}{abs_mag / 1e6:.3g} M{_format_unit_symbol(unit)}"
    elif abs_mag >= 1e3:
        return f"{sign}{abs_mag / 1e3:.3g} k{_format_unit_symbol(unit)}"
    elif abs_mag >= 1.0:
        return f"{sign}{abs_mag:.3g} {_format_unit_symbol(unit)}"
    elif abs_mag >= 1e-3:
        return f"{sign}{abs_mag * 1e3:.3g} m{_format_unit_symbol(unit)}"
    elif abs_mag >= 1e-6:
        return f"{sign}{abs_mag * 1e6:.3g} μ{_format_unit_symbol(unit)}"
    elif abs_mag >= 1e-9:
        return f"{sign}{abs_mag * 1e9:.3g} n{_format_unit_symbol(unit)}"
    elif abs_mag >= 1e-12:
        return f"{sign}{abs_mag * 1e12:.3g} p{_format_unit_symbol(unit)}"
    else:
        return f"{sign}{abs_mag:.3e} {_format_unit_symbol(unit)}"


def _format_unit_symbol(unit: str) -> str:
    """Convert canonical unit name to standard UI symbol."""
    u = unit.lower()
    if u in ("ohm", "ohms"):
        return "Ω"
    if u in ("f", "farad"):
        return "F"
    if u in ("v", "volt"):
        return "V"
    if u in ("a", "amp", "ampere"):
        return "A"
    if u in ("s", "sec", "second"):
        return "s"
    return unit


def to_spice_value_str(value: SIValue, comp_type: ComponentType = ComponentType.RESISTOR) -> str:
    """Generate SPICE-compatible value string without confusing SPICE's m/meg rules."""
    mag = value.magnitude
    abs_mag = abs(mag)

    if abs_mag == 0:
        return "0"

    # In SPICE:
    # 'meg' = 1e6
    # 'm' = 1e-3 (NOT mega!)
    # 'k' = 1e3
    # 'u' = 1e-6
    # 'n' = 1e-9
    # 'p' = 1e-12
    if abs_mag >= 1e6 and abs_mag % 1e6 == 0:
        return f"{mag / 1e6:g}meg"
    elif abs_mag >= 1e3 and abs_mag % 1e3 == 0:
        return f"{mag / 1e3:g}k"
    elif abs_mag < 1.0:
        if 1e-3 <= abs_mag < 0.1:
            return f"{mag * 1e3:g}m"
        elif 1e-6 <= abs_mag < 1e-3:
            return f"{mag * 1e6:g}u"
        elif 1e-9 <= abs_mag < 1e-6:
            return f"{mag * 1e9:g}n"
        elif 1e-12 <= abs_mag < 1e-9:
            return f"{mag * 1e12:g}p"

    # Default to standard float formatting if not a clean power of 10
    return f"{mag:g}"
