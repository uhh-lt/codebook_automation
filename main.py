import uvicorn
from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse
from loguru import logger as log

from api.routers import general, model, prediction, training, dataset, mapping
from backend import DataHandler, ModelFactory, ModelManager, Predictor, Trainer, DatasetManager, RedisHandler
from backend.exceptions import ModelNotAvailableException, ErroneousMappingException, ErroneousModelException, \
    PredictionError, ModelInitializationException, ErroneousDatasetException, \
    NoDataForCodebookException, DatasetNotAvailableException, InvalidModelIdException, \
    TagLabelMappingNotAvailableException, ModelMetadataNotAvailableException, DatasetMetadataNotAvailableException, \
    StoringError, RedisError
from config import conf

# create the main app
app = FastAPI(title="Codebook Automation API",
              description="An easy to use API for AI based prediction of Codebook Tags for CodeAnno documents.",
              version="beta")


@app.on_event("startup")
def startup_event():
    try:
        # setup loguru logging
        log.add('logs/{time}.log', rotation=f"{conf.logging.rotation} MB", level=conf.logging.level)

        # instantiate singletons
        DataHandler()
        RedisHandler()
        DatasetManager()
        ModelFactory()
        ModelManager()
        Predictor()
        Trainer()
    except Exception as e:
        msg = f"Error while starting the API! Exception: {str(e)}"
        log.error(msg)
        raise SystemExit(msg)


@app.on_event("shutdown")
async def shutdown_event():
    await Trainer.shutdown()


# include the routers
app.include_router(general.router)
app.include_router(dataset.router, prefix=dataset.PREFIX)
app.include_router(model.router, prefix=model.PREFIX)
app.include_router(prediction.router, prefix=prediction.PREFIX)
app.include_router(training.router, prefix=training.PREFIX)
app.include_router(mapping.router, prefix=mapping.PREFIX)


# custom exception handlers
@app.exception_handler(RedisError)
async def redis_error_handler(request: Request, exc: RedisError):
    log.error(exc.message)
    return JSONResponse(
        status_code=500,
        content={"message": exc.message}
    )


@app.exception_handler(StoringError)
async def storing_error_handler(request: Request, exc: StoringError):
    log.error(exc.message)
    return JSONResponse(
        status_code=500,
        content={"message": exc.message}
    )


@app.exception_handler(PredictionError)
async def prediction_error_handler(request: Request, exc: PredictionError):
    log.error(exc.message)
    return JSONResponse(
        status_code=500,
        content={"message": exc.message}
    )


@app.exception_handler(ModelNotAvailableException)
async def model_not_available_exception_handler(request: Request, exc: ModelNotAvailableException):
    log.error(exc.message)
    return JSONResponse(
        status_code=404,
        content={"message": exc.message}
    )


@app.exception_handler(TagLabelMappingNotAvailableException)
async def mapping_not_available_exception_handler(request: Request, exc: TagLabelMappingNotAvailableException):
    log.error(exc.message)
    return JSONResponse(
        status_code=404,
        content={"message": exc.message}
    )


@app.exception_handler(ModelInitializationException)
async def model_initialization_exception_handler(request: Request, exc: ModelInitializationException):
    log.error(exc.message)
    return JSONResponse(
        status_code=500,
        content={"message": exc.message,
                 "caused_by": exc.caused_by}
    )


@app.exception_handler(ErroneousMappingException)
async def erroneous_mapping_exception_handler(request: Request, exc: ErroneousMappingException):
    log.error(exc.message)
    return JSONResponse(
        status_code=400,
        content={"message": exc.message}
    )


@app.exception_handler(ErroneousModelException)
async def erroneous_model_exception_handler(request: Request, exc: ErroneousModelException):
    log.error(exc.message)
    return JSONResponse(
        status_code=500,
        content={"message": exc.message}
    )


@app.exception_handler(ErroneousDatasetException)
async def erroneous_dataset_exception_handler(request: Request, exc: ErroneousDatasetException):
    log.error(exc.message)
    return JSONResponse(
        status_code=400,
        content={"message": exc.message,
                 "caused_by": exc.caused_by}
    )


@app.exception_handler(NoDataForCodebookException)
async def no_data_for_codebook_exception_handler(request: Request, exc: NoDataForCodebookException):
    log.error(exc.message)
    return JSONResponse(
        status_code=404,
        content={"message": exc.message}
    )


@app.exception_handler(InvalidModelIdException)
async def invalid_model_id_exception_exception_handler(request: Request, exc: InvalidModelIdException):
    log.error(exc.message)
    return JSONResponse(
        status_code=400,
        content={"message": exc.message}
    )


@app.exception_handler(DatasetNotAvailableException)
async def dataset_not_available_exception_exception_handler(request: Request, exc: DatasetNotAvailableException):
    log.error(exc.message)
    return JSONResponse(
        status_code=404,
        content={"message": exc.message}
    )


@app.exception_handler(ModelMetadataNotAvailableException)
async def model_metadata_not_available_exception_exception_handler(request: Request,
                                                                   exc: ModelMetadataNotAvailableException):
    log.error(exc.message)
    return JSONResponse(
        status_code=404,
        content={"message": exc.message}
    )


@app.exception_handler(DatasetMetadataNotAvailableException)
async def dataset_metadata_not_available_exception_exception_handler(request: Request,
                                                                     exc: DatasetMetadataNotAvailableException):
    log.error(exc.message)
    return JSONResponse(
        status_code=404,
        content={"message": exc.message}
    )


if __name__ == "__main__":
    # read port from config
    port = int(conf.api.port)
    assert port is not None and isinstance(port, int) and port > 0, "The api_port has to be an integer! E.g. 8081"

    uvicorn.run(app, host="0.0.0.0", port=port, debug=True)
