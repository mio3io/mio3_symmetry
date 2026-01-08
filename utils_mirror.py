import re

SIDE_MAP = {
    "L": "R",
    "R": "L",
    "l": "r",
    "r": "l",
    "Left": "Right",
    "Right": "Left",
    "left": "right",
    "right": "left",
    "LEFT": "RIGHT",
    "RIGHT": "LEFT",
}

SIDE_TOKENS = ("L", "R", "l", "r", "Left", "Right", "left", "right", "LEFT", "RIGHT")
LONG_SIDE_TOKENS = ("Left", "Right", "left", "right", "LEFT", "RIGHT")

LEFT_SIDE_TOKENS = {"L", "Left", "l", "left", "LEFT"}
RIGHT_SIDE_TOKENS = {"R", "Right", "r", "right", "RIGHT"}

SIDE_PATTERN = "|".join(map(re.escape, SIDE_TOKENS))
LONG_SIDE_PATTERN = "|".join(map(re.escape, LONG_SIDE_TOKENS))


PATTERNS = [
    {  # _L, .R など＠セパレーター付き
        "id": 1,
        "pattern": re.compile(r"(?P<base>.+)(?P<sep>[._\-])(?P<side>(" + SIDE_PATTERN + r"))(?P<opt>[._]\d+(?:_end|\.end)?)?$"),
        "side_type": "suffix",
    },
    {  # L_aaa など＠セパレーター付き
        "id": 2,
        "pattern": re.compile(r"^(?P<side>(" + SIDE_PATTERN + r"))(?P<sep>[._-])(?P<base>.+)(?P<opt>[._]\d+(?:_end|\.end)?)?$"),
        "side_type": "prefix",
    },
    {  # UpperArmLeft など
        "id": 3,
        "pattern": re.compile(r"(?P<base>.+?)(?P<side>(" + LONG_SIDE_PATTERN + r"))(?P<opt>[._]\d+(?:_end|\.end)?)?$"),
        "side_type": "suffix",
    },
    {  # LeftUpperArm, leftUpperArm など
        "id": 4,
        "pattern": re.compile(r"^(?P<side>(" + LONG_SIDE_PATTERN + r"))(?P<base>[^a-z].+?)(?P<opt>[._]\d+(?:_end|\.end)?)?$"),
        "side_type": "prefix",
    },
    {  # 左右なし
        "id": 5,
        "pattern": re.compile(r"(?P<base>.+?)(?P<opt>[._]\d+(?:_end|\.end)?)?$"),
        "side_type": "none",
    },
]  # fmt: skip


def _normalize_side_label(side):
    if not side:
        return None
    if side in LEFT_SIDE_TOKENS:
        return "left"
    if side in RIGHT_SIDE_TOKENS:
        return "right"
    return None


def _compose_name(base, sep, side_token, opt, side_type):
    if side_type == "suffix":
        return f"{base}{sep}{side_token}{opt}"
    if side_type == "prefix":
        return f"{side_token}{sep}{base}{opt}"
    return base + opt


def analyze_lr_name(name):
    for pat in PATTERNS:
        if not (m := pat["pattern"].match(name)):
            continue

        group = m.groupdict()
        side = group.get("side") or ""
        sep = group.get("sep") or ""
        base = group.get("base") or ""
        opt = group.get("opt") or ""
        side_label = _normalize_side_label(side) if pat["side_type"] != "none" else None

        info = {
            "pattern_id": pat["id"],
            "side_type": pat["side_type"],
            "base": base,
            "side": side,
            "sep": sep,
            "opt": opt,
            "side_label": side_label,
            "has_side": pat["side_type"] != "none" and side_label is not None,
        }
        mirror_side = SIDE_MAP.get(side)
        if mirror_side:
            info["mirror_side"] = mirror_side

        return info
    return None


def get_mirror_name(name):
    info = analyze_lr_name(name)
    if not info or not info.get("has_side"):
        return name

    mirror_side = info.get("mirror_side")
    if not mirror_side:
        return name

    return _compose_name(info["base"], info["sep"], mirror_side, info["opt"], info["side_type"])


def is_lr_name(name, base):
    info = analyze_lr_name(name)
    if not info or not info.get("has_side"):
        return False
    return info["base"].casefold() == base.casefold()
