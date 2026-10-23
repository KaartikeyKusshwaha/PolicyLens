from fastapi import APIRouter, Request
from pydantic import Field

from adapters import ADAPTERS, import_bundle, preview
from models import Input
from providers import problem

router = APIRouter(prefix="/api/adapters")


class PreviewInput(Input):
    bundle: dict


class ImportInput(PreviewInput):
    preview_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")


def author(request):
    if request.state.user["role"] not in ("admin", "analyst"):
        raise problem(
            403,
            "role_required",
            "Only workspace import authors can import engine records.",
        )


@router.get("")
def catalog():
    return {
        "adapters": [
            {
                "id": name,
                "transport": "export_bundle",
                "scope": "Read/import only; no upstream write actions.",
            }
            for name in ADAPTERS
        ]
    }


@router.post("/{provider}/preview")
def preview_bundle(provider: str, data: PreviewInput, request: Request):
    author(request)
    return preview(request.state.store, provider, data.bundle)


@router.post("/{provider}/import", status_code=201)
def commit_bundle(provider: str, data: ImportInput, request: Request):
    author(request)
    return import_bundle(
        request.state.store,
        provider,
        data.bundle,
        data.preview_sha256,
        request.state.user,
    )
