"""Firmware release file server — superuser only."""
import json
import os
import re
from pathlib import Path

from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.responses import FileResponse

from app.api.deps import require_password_changed
from app.models.user import User

router = APIRouter(prefix="/firmware", tags=["firmware"])

# Mounted into the container via docker-compose volume bind.
RELEASES_DIR = Path(os.getenv("FIRMWARE_RELEASES_DIR", "/firmware_profiles"))

_SAFE_VERSION = re.compile(r"^v[\w.\-]+$")
_ALLOWED_FILES = {"bootloader.bin", "partitions.bin", "firmware.bin", "manifest.json"}


def _require_superuser(user: User = Depends(require_password_changed)) -> User:
    if user.role != "superuser":
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Superuser only")
    return user


@router.get("/releases")
async def list_releases(
    _user: User = Depends(_require_superuser),
) -> list[dict]:
    """Return a list of available firmware releases with their manifests."""
    if not RELEASES_DIR.exists():
        return []
    releases = []
    for entry in sorted(RELEASES_DIR.iterdir()):
        if not entry.is_dir():
            continue
        manifest_path = entry / "manifest.json"
        if not manifest_path.exists():
            continue
        manifest = json.loads(manifest_path.read_text())
        # Only include releases where all binary files are present
        files_present = all(
            (entry / f["path"]).exists() for f in manifest.get("files", [])
        )
        releases.append({**manifest, "version": entry.name, "ready": files_present})
    return releases


@router.get("/releases/{version}/{filename}")
async def get_release_file(
    version: str,
    filename: str,
    _user: User = Depends(_require_superuser),
) -> FileResponse:
    """Serve a firmware binary or manifest for a given release version."""
    if not _SAFE_VERSION.match(version):
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid version")
    if filename not in _ALLOWED_FILES:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid filename")

    file_path = RELEASES_DIR / version / filename
    if not file_path.exists():
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="File not found")

    media_type = "application/octet-stream" if filename.endswith(".bin") else "application/json"
    return FileResponse(path=str(file_path), media_type=media_type, filename=filename)
