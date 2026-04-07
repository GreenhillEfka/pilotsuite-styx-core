

# ── SLICE 160: Media API Expansion ─────────────────────────────────
from flask import Blueprint

bp = Blueprint("media", __name__, url_prefix="/media")


@bp.post("/<media_id>/transcode")
def media_transcode(media_id):
    """Transcode media to different format.
    
    Requires admin token.
    
    Body:
    - format: Target format (mp4|webm|mp3|wav|jpg|png)
    - quality: low|medium|high (default: medium)
    """
    auth_error = _require_admin_mutation("TRANSCODE_MEDIA", "Admin token required")
    if auth_error:
        return auth_error
    
    data = request.get_json() or {}
    target_format = data.get("format")
    quality = data.get("quality", "medium")
    
    if not target_format:
        return jsonify({
            "ok": False,
            "error": "Missing format"
        }), 400
    
    from copilot_core.media.engine import get_media_engine
    
    try:
        engine = get_media_engine()
        result = engine.transcode(media_id=media_id, target_format=target_format, quality=quality)
        success = result.get("success", False)
        new_media_id = result.get("new_media_id")
    except Exception as e:
        _LOGGER.warning("Failed to transcode media: %s", e)
        success = False
        new_media_id = None
    
    return jsonify({
        "ok": success,
        "media_id": media_id,
        "new_media_id": new_media_id,
        "format": target_format,
        "quality": quality
    })


@bp.post("/<media_id>/thumbnail")
def media_generate_thumbnail(media_id):
    """Generate thumbnail for media.
    
    Requires admin token.
    
    Body:
    - size: small|medium|large (default: medium)
    - timestamp: For video, which timestamp to capture (default: 0)
    """
    auth_error = _require_admin_mutation("GENERATE_THUMBNAIL", "Admin token required")
    if auth_error:
        return auth_error
    
    data = request.get_json() or {}
    size = data.get("size", "medium")
    timestamp = data.get("timestamp", 0)
    
    from copilot_core.media.engine import get_media_engine
    
    try:
        engine = get_media_engine()
        result = engine.generate_thumbnail(media_id=media_id, size=size, timestamp=timestamp)
        success = result.get("success", False)
        thumbnail_id = result.get("thumbnail_id")
    except Exception as e:
        _LOGGER.warning("Failed to generate thumbnail: %s", e)
        success = False
        thumbnail_id = None
    
    return jsonify({
        "ok": success,
        "media_id": media_id,
        "thumbnail_id": thumbnail_id,
        "size": size
    })


@bp.get("/albums")
def media_albums():
    """List media albums.
    
    Query params:
    - limit: Max albums (default 50)
    """
    from copilot_core.media.engine import get_media_engine
    
    try:
        limit = int(request.args.get("limit", "50"))
    except (ValueError, TypeError):
        limit = 50
    
    limit = max(1, min(limit, 200))
    
    try:
        engine = get_media_engine()
        albums = engine.list_albums(limit=limit)
    except Exception as e:
        _LOGGER.warning("Failed to list albums: %s", e)
        albums = []
    
    return jsonify({
        "ok": True,
        "albums": albums,
        "count": len(albums),
        "limit": limit
    })


@bp.post("/albums")
def media_create_album():
    """Create a new media album.
    
    Body:
    - name: Album name
    - description: Optional description
    - media_ids: Optional list of media IDs to add
    """
    data = request.get_json() or {}
    name = data.get("name")
    description = data.get("description", "")
    media_ids = data.get("media_ids", [])
    
    if not name:
        return jsonify({
            "ok": False,
            "error": "Missing name"
        }), 400
    
    from copilot_core.media.engine import get_media_engine
    
    try:
        engine = get_media_engine()
        album_id = engine.create_album(name=name, description=description, media_ids=media_ids)
        success = True
    except Exception as e:
        _LOGGER.warning("Failed to create album: %s", e)
        success = False
        album_id = None
    
    return jsonify({
        "ok": success,
        "album_id": album_id,
        "name": name,
        "description": description
    })


@bp.get("/albums/<album_id>/media")
def media_album_contents(album_id):
    """Get media items in an album.
    
    Query params:
    - limit: Max items (default 50)
    - offset: Pagination offset (default 0)
    """
    from copilot_core.media.engine import get_media_engine
    
    try:
        limit = int(request.args.get("limit", "50"))
    except (ValueError, TypeError):
        limit = 50
    
    try:
        offset = int(request.args.get("offset", "0"))
    except (ValueError, TypeError):
        offset = 0
    
    limit = max(1, min(limit, 200))
    offset = max(0, offset)
    
    try:
        engine = get_media_engine()
        media = engine.get_album_contents(album_id=album_id, limit=limit, offset=offset)
    except Exception as e:
        _LOGGER.warning("Failed to get album contents: %s", e)
        media = []
    
    return jsonify({
        "ok": True,
        "album_id": album_id,
        "media": media,
        "count": len(media),
        "limit": limit,
        "offset": offset
    })
