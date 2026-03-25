"""Orientation detection helpers.

Detects the clockwise rotation (0, 90, 180, 270 degrees) needed to upright a
postcard image.  Two strategies are offered and chosen by the caller:

  OSD (pytesseract)  — fast, reliable on text-bearing back images.
  VLM (mlx-vlm)      — local vision-language model; for front images where
                        there is no text to anchor orientation.

Installation
------------
  # OSD strategy
  pip install pytesseract
  brew install tesseract          # Tesseract binary (macOS)

  # VLM strategy (Apple Silicon only)
  pip install mlx-vlm

Both imports are lazy so this module loads without either package installed;
ImportError is raised only when the relevant function is actually called.
"""

from __future__ import annotations

import logging
from pathlib import Path

logger = logging.getLogger(__name__)

_VALID_ANGLES: frozenset[int] = frozenset({0, 90, 180, 270})
_DEFAULT_VLM_MODEL = "mlx-community/Qwen2-VL-2B-Instruct-4bit"


# ---------------------------------------------------------------------------
# OSD strategy
# ---------------------------------------------------------------------------

def detect_via_osd(image_path: str | Path) -> tuple[int, float]:
    """Use pytesseract OSD to detect orientation of a text-bearing image.

    Returns ``(cw_degrees_to_correct, confidence)``.

    The returned angle is Tesseract's "Rotate" value — the clockwise rotation
    the image needs so that text becomes upright.

    Raises
    ------
    ImportError   if pytesseract is not installed.
    RuntimeError  if the Tesseract binary is not found on PATH.
    """
    try:
        import pytesseract
    except ImportError as exc:
        raise ImportError(
            "pytesseract is required: pip install pytesseract  "
            "(also run: brew install tesseract)"
        ) from exc

    from PIL import Image

    with Image.open(image_path) as img:
        osd = pytesseract.image_to_osd(img, output_type=pytesseract.Output.DICT)

    # 'rotate' is the CW correction angle Tesseract recommends.
    angle = int(osd.get("rotate", 0)) % 360
    if angle not in _VALID_ANGLES:
        logger.warning(
            "OSD returned unexpected angle %d for %s; defaulting to 0", angle, image_path
        )
        angle = 0

    confidence = float(osd.get("orientation_conf", 0.0))
    return angle, confidence


# ---------------------------------------------------------------------------
# VLM strategy
# ---------------------------------------------------------------------------

def load_vlm(model_name: str = _DEFAULT_VLM_MODEL):
    """Load and return a ``(model, processor, config)`` tuple for reuse.

    Call this once before a batch of :func:`detect_via_vlm` calls to avoid
    re-downloading and re-initialising the model for every image.

    Example::

        ctx = load_vlm()
        for path in image_paths:
            angle, conf = detect_via_vlm(path, vlm_context=ctx)

    Raises
    ------
    ImportError  if mlx-vlm is not installed.
    """
    try:
        from mlx_vlm import load
        from mlx_vlm.utils import load_config
    except ImportError as exc:
        raise ImportError(
            "mlx-vlm is required (Apple Silicon only): pip install mlx-vlm"
        ) from exc

    model, processor = load(model_name)
    config = load_config(model_name)
    return model, processor, config


def detect_via_vlm(
    image_path: str | Path,
    model_name: str = _DEFAULT_VLM_MODEL,
    vlm_context=None,
) -> tuple[int, float]:
    """Use a local MLX vision-language model to detect image orientation.

    Returns ``(cw_degrees_to_correct, confidence)``.
    Confidence is ``1.0`` when the model returns a parseable valid angle,
    or ``0.0`` when the output cannot be interpreted.

    Pass a pre-loaded ``vlm_context`` (from :func:`load_vlm`) to avoid
    re-loading the model on every call.

    Raises
    ------
    ImportError  if mlx-vlm is not installed.
    """
    if vlm_context is not None:
        model, processor, config = vlm_context
    else:
        model, processor, config = load_vlm(model_name)

    return _run_vlm(model, processor, config, image_path)


def detect_via_vlm_batch(
    image_paths: list[str | Path],
    model_name: str = _DEFAULT_VLM_MODEL,
) -> list[tuple[int, float]]:
    """Like :func:`detect_via_vlm` but loads the model once for multiple images.

    Returns a list of ``(cw_degrees_to_correct, confidence)`` tuples, one per
    input path (in the same order).
    """
    ctx = load_vlm(model_name)
    return [_run_vlm(*ctx, p) for p in image_paths]


def _parse_vlm_response(raw: str) -> int | None:
    """Extract an orientation angle from a VLM response (strict or natural language).

    Returns one of {0, 90, 180, 270} or ``None`` if the response can't be parsed.
    """
    import re

    stripped = raw.strip()

    # Best case: model obeyed and returned a plain integer
    try:
        val = int(stripped)
        if val in _VALID_ANGLES:
            return val
    except (ValueError, TypeError):
        pass

    lower = stripped.lower()

    # Phrases that mean "already upright" → 0
    upright_phrases = (
        "correctly oriented",
        "properly oriented",
        "no rotation",
        "already upright",
        "is upright",
        "is correct",
        "does not need",
        "not need to be rotated",
        "0 degrees",
        "0°",
    )
    if any(p in lower for p in upright_phrases):
        return 0

    # Look for explicit degree mentions — check larger values first to avoid
    # "180" matching inside "1800" etc.
    for angle in (270, 180, 90):
        if re.search(rf"\b{angle}\b", lower):
            return angle

    return None


def _run_vlm(model, processor, config, image_path: str | Path) -> tuple[int, float]:
    """Internal: run a single VLM inference given an already-loaded model."""
    from mlx_vlm import generate
    from mlx_vlm.prompt_utils import apply_chat_template

    prompt = (
        "Look at this postcard image carefully. "
        "How many degrees clockwise must it be rotated so the main subject appears upright? "
        "Answer with ONLY one of these four integers: 0, 90, 180, 270. "
        "0 means it is already upright. No other words."
    )
    formatted = apply_chat_template(processor, config, prompt, num_images=1)
    result = generate(
        model, processor, formatted, str(image_path), max_tokens=64, verbose=False
    )
    raw = result.text.strip() if hasattr(result, "text") else str(result).strip()

    angle = _parse_vlm_response(raw)
    if angle is not None:
        return angle, 1.0

    logger.warning(
        "VLM returned unparseable output %r for %s; defaulting to 0", raw, image_path
    )
    return 0, 0.0


# ---------------------------------------------------------------------------
# Unified dispatcher
# ---------------------------------------------------------------------------

def detect_orientation(
    image_path: str | Path,
    *,
    is_back: bool,
    osd_confidence_threshold: float = 3.0,
    vlm_model: str = _DEFAULT_VLM_MODEL,
    vlm_context=None,
) -> tuple[int, float, str]:
    """Detect the clockwise rotation (degrees) needed to upright an image.

    Strategy
    --------
    Back images  (text-bearing) — try OSD first; fall back to VLM when OSD
                                   confidence is below *osd_confidence_threshold*.
    Front images (visual)       — use VLM directly.

    Pass a pre-loaded ``vlm_context`` (from :func:`load_vlm`) to avoid
    re-loading the model on every call.

    Returns ``(cw_degrees_to_correct, confidence, method)`` where *method* is
    ``"osd"`` or ``"vlm"``.
    """
    if is_back:
        try:
            angle, conf = detect_via_osd(image_path)
            if conf >= osd_confidence_threshold:
                return angle, conf, "osd"
            logger.debug(
                "OSD confidence %.1f below threshold for %s; falling back to VLM",
                conf,
                image_path,
            )
        except Exception as exc:
            logger.debug("OSD failed for %s: %s; falling back to VLM", image_path, exc)

    angle, conf = detect_via_vlm(image_path, model_name=vlm_model, vlm_context=vlm_context)
    return angle, conf, "vlm"
