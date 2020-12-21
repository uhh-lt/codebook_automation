from typing import List, Optional

from pydantic import BaseModel

from .document_dto import DocumentDTO
from .tag_label_mapping import TagLabelMapping


class PredictionRequest(BaseModel):
    doc: DocumentDTO
    cb_name: str
    mapping: TagLabelMapping = None
    model_version: Optional[str] = "default"


class MultiDocumentPredictionRequest(BaseModel):
    docs: List[DocumentDTO]
    cb_name: str
    mapping: Optional[TagLabelMapping] = None
    model_version: Optional[str] = "default"
