from fastapi import APIRouter
from fastapi.responses import StreamingResponse

from api.model import TrainingRequest, TrainingResponse, TrainingStatus, \
    TrainingState
from backend.training.trainer import Trainer
from loguru import logger as log

PREFIX = "/training"
router = APIRouter()


@router.post("/train/", response_model=TrainingResponse, tags=["training"])
async def train(req: TrainingRequest):
    log.info(f"POST request on  {PREFIX}/train/ with TrainingRequest {req}")
    return Trainer.train(req)


@router.post("/log/", tags=["training"])
async def get_train_log(resp: TrainingResponse):
    log.info(f"POST request on  {PREFIX}/log/ with TrainingResponse {resp}")
    log_path = Trainer.get_training_log(resp)
    file_like = open(str(log_path), mode="rb")
    return StreamingResponse(file_like, media_type="text/plain")


@router.post("/status/", response_model=TrainingStatus, tags=["training"])
async def get_training_status(resp: TrainingResponse):
    log.info(f"POST request on  {PREFIX}/status/ with TrainingResponse {resp}")
    status = Trainer.get_train_status(resp)
    if status is None:
        return TrainingStatus(state=TrainingState.finished, process_status="finished")
    else:
        return status
