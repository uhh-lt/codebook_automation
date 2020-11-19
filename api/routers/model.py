from typing import Optional

from fastapi import APIRouter, UploadFile, File, Form

from backend import ModelManager
from logger import api_logger
from ..model import CodebookModel, BooleanResponse, StringResponse, ModelMetadata

PREFIX = "/model"

router = APIRouter()


@router.post("/is_available/", response_model=BooleanResponse, tags=["model"])
async def is_available(cb: CodebookModel, model_version: Optional[str] = "default"):
    api_logger.info(
        f"POST request on {PREFIX}/is_available with model version '{model_version}'for Codebook {cb.json()}")
    return BooleanResponse(value=ModelManager.model_is_available(cb=cb, model_version=model_version))


@router.post("/get_metadata/", response_model=ModelMetadata, tags=["model"])
async def get_metadata(cb: CodebookModel, model_version: Optional[str] = "default"):
    api_logger.info(
        f"POST request on {PREFIX}/get_metadata with model version '{model_version}'for Codebook {cb.json()}")
    return ModelManager.load_model_metadata(cb, model_version=model_version)


@router.put("/upload_for_codebook/", response_model=StringResponse, tags=["model"])
async def upload_for_codebook(codebook_name: str = Form(..., description="The name of the Codebook. Case-sensitive!"),
                              codebook_tag_list: str = Form(...,
                                                            description="Comma-separated list of tags. E.g. tag1,Tag2"),
                              model_version: str = Form(...,
                                                        description="Optional version tag of the model. If a tag "
                                                                    "is not provided and if there is already an "
                                                                    "existing model with the same (default) tag, "
                                                                    "the model gets overwritten.  E.g. v1"),
                              model_archive: UploadFile = File(..., description="Zip-archive of the model.")):
    cb = CodebookModel(name=codebook_name, tags=codebook_tag_list.replace(" ", "").split(','))
    model_version = "default" if model_version is None or model_archive == "" else model_version

    api_logger.info(
        f"POST request on {PREFIX}/upload_for_codebook with model version '{model_version}'for Codebook {cb.json()}")

    return StringResponse(value=ModelManager.store_uploaded_model(cb, model_version, model_archive))
