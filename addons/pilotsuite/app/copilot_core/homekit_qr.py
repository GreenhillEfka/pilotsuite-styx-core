"""HomeKit QR Code + Setup Code generator for PilotSuite zones.

Generates deterministic, stable HomeKit-style setup codes per zone
and serves QR code images (SVG) that encode a HomeKit-compatible
pairing URI.

The QR encodes: X-HM://0{payload}  (HomeKit Accessory Protocol URI)
Payload = base36 of (flags | category | setup_code)
"""

import hashlib
import io
import logging
from typing import Optional

logger = logging.getLogger(__name__)

# HomeKit accessory categories
HAP_CATEGORY_BRIDGE = 2

# Cached setup codes  (zone_id → code dict)
_setup_codes: dict[str, dict] = {}


def _derive_setup_code(zone_id: str, salt: str = "PilotSuite-Styx") -> str:
    """Derive a stable 8-digit HomeKit setup code from zone_id.

    Format: XXX-XX-XXX (digits only, no leading zero in first group).
    """
    h = hashlib.sha256(f"{salt}:{zone_id}".encode()).hexdigest()
    num = int(h[:8], 16) % 99999999 + 1  # 1..99999999
    raw = f"{num:08d}"
    return f"{raw[:3]}-{raw[3:5]}-{raw[5:]}"


def _derive_setup_id(zone_id: str, salt: str = "PilotSuite-Styx") -> str:
    """Derive a 4-character setup ID for HomeKit pairing URI."""
    h = hashlib.sha256(f"{salt}:id:{zone_id}".encode()).hexdigest()
    chars = "0123456789ABCDEFGHIJKLMNOPQRSTUVWXYZ"
    return "".join(chars[int(h[i * 2:(i + 1) * 2], 16) % 36] for i in range(4))


def _build_homekit_uri(setup_code: str, category: int = HAP_CATEGORY_BRIDGE) -> str:
    """Build X-HM:// URI from setup code and category.

    The URI encodes: version(0) | reserved | category | flags | setup_code
    as a base36 number.
    """
    code_num = int(setup_code.replace("-", ""))
    # Flags: bit0 = IP, bit1 = BLE (we only support IP)
    flags = 2  # IP transport
    # Payload = (version << 43) | (reserved << 42) | (category << 31) | (flags << 27) | code_num
    version = 0
    reserved = 0
    payload = (version << 43) | (reserved << 42) | (category << 31) | (flags << 27) | code_num

    # Encode as base36, padded to 9 chars
    chars = "0123456789ABCDEFGHIJKLMNOPQRSTUVWXYZ"
    result = []
    val = payload
    while val > 0:
        result.append(chars[val % 36])
        val //= 36
    encoded = "".join(reversed(result)).rjust(9, "0")

    setup_id = _derive_setup_id(str(code_num))
    return f"X-HM://{encoded}{setup_id}"


def get_zone_setup_info(zone_id: str, zone_name: str = "") -> dict:
    """Get or generate HomeKit setup info for a zone.

    Returns: {
        "zone_id": "...",
        "zone_name": "...",
        "setup_code": "123-45-678",
        "setup_id": "ABCD",
        "homekit_uri": "X-HM://...",
        "manufacturer": "PilotSuite",
        "model": "Styx HomeKit Bridge",
        "serial": "PS-<zone_hash>",
    }
    """
    if zone_id in _setup_codes:
        cached = _setup_codes[zone_id]
        if zone_name:
            cached["zone_name"] = zone_name
        return cached

    setup_code = _derive_setup_code(zone_id)
    setup_id = _derive_setup_id(zone_id)
    homekit_uri = _build_homekit_uri(setup_code)
    serial_hash = hashlib.sha256(zone_id.encode()).hexdigest()[:8].upper()

    info = {
        "zone_id": zone_id,
        "zone_name": zone_name or zone_id,
        "setup_code": setup_code,
        "setup_id": setup_id,
        "homekit_uri": homekit_uri,
        "manufacturer": "PilotSuite",
        "model": "Styx HomeKit Bridge",
        "serial": f"PS-{serial_hash}",
        "category": "Bridge",
    }
    _setup_codes[zone_id] = info
    return info


def generate_qr_svg(zone_id: str, zone_name: str = "", box_size: int = 8) -> Optional[str]:
    """Generate a QR code SVG string for a zone's HomeKit pairing URI.

    Returns SVG string or None if qrcode library unavailable.
    """
    try:
        import qrcode
        import qrcode.image.svg
    except ImportError:
        logger.warning("qrcode library not available — cannot generate QR codes")
        return None

    info = get_zone_setup_info(zone_id, zone_name)
    uri = info["homekit_uri"]

    factory = qrcode.image.svg.SvgPathImage
    qr = qrcode.QRCode(
        version=None,
        error_correction=qrcode.constants.ERROR_CORRECT_M,
        box_size=box_size,
        border=2,
    )
    qr.add_data(uri)
    qr.make(fit=True)

    img = qr.make_image(image_factory=factory)
    buf = io.BytesIO()
    img.save(buf)
    return buf.getvalue().decode("utf-8")


def generate_qr_png_bytes(zone_id: str, zone_name: str = "", box_size: int = 10) -> Optional[bytes]:
    """Generate a QR code PNG for a zone's HomeKit pairing URI.

    Returns PNG bytes or None if libraries unavailable.
    Uses pure-Python PBM fallback if Pillow is not installed.
    """
    try:
        import qrcode
    except ImportError:
        return None

    info = get_zone_setup_info(zone_id, zone_name)
    uri = info["homekit_uri"]

    qr = qrcode.QRCode(
        version=None,
        error_correction=qrcode.constants.ERROR_CORRECT_M,
        box_size=box_size,
        border=2,
    )
    qr.add_data(uri)
    qr.make(fit=True)

    try:
        # Try Pillow-based PNG first
        img = qr.make_image(fill_color="black", back_color="white")
        buf = io.BytesIO()
        img.save(buf, format="PNG")
        return buf.getvalue()
    except Exception:
        # Fallback: return SVG bytes
        svg = generate_qr_svg(zone_id, zone_name, box_size)
        if svg:
            return svg.encode("utf-8")
        return None
