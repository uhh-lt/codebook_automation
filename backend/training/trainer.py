import logging
import multiprocessing
import os
import pprint as pp
import shutil
from multiprocessing import Manager, Process
from pathlib import Path
from typing import Dict, Optional

import psutil
import tensorflow as tf
from loguru import logger as log

from api.model import TrainingResponse, TrainingRequest, TrainingState, TrainingStatus
from backend import DataHandler, DatasetManager, ModelManager
from backend.exceptions import ModelNotAvailableException, StoringError
from backend.training.model_factory import ModelFactory
from config import conf


class Trainer(object):
    _singleton = None
    # TODO persist in redis or similar
    _status_dict: Dict[str, TrainingStatus] = None
    _active_pids: Dict[int, str] = None
    _manager: Manager = None

    def __new__(cls, *args, **kwargs):
        if cls._singleton is None:
            log.info('Instantiating Trainer!')

            # make sure GPU is available for ModelTrainer (if there is one)
            if not bool(conf.backend.use_gpu_for_training):
                log.info("GPU support for training disabled!")
                os.environ["CUDA_VISIBLE_DEVICES"] = "-1"
            else:
                log.info("GPU support for training enabled!")

            cls._singleton = super(Trainer, cls).__new__(cls)
            cls._manager = Manager()
            # TODO persist those dicts in redis or similar
            cls._status_dict = cls._manager.dict()
            cls._active_pids = cls._manager.dict()

        return cls._singleton

    @staticmethod
    def shutdown():
        Trainer._manager.shutdown()

    @staticmethod
    def train(request: TrainingRequest) -> TrainingResponse:
        # TODO
        #  - how to assign GPU(s)
        #  - set max number of active processes implement a job queue

        # remove model if another with same version exists!
        if ModelManager.is_available(request.cb_name, request.model_version):
            log.warning(f"Model {request.model_version} for Codebook '{request.cb_name}' already exists!")
            ModelManager.remove(cb_name=request.cb_name, model_version=request.model_version)

        with Manager() as manager:
            log.info(f"Spawning new process for train-eval-export cycle for Codebook <{request.cb_name}>")
            p = Process(target=train_eval_export, args=(request, Trainer._status_dict, Trainer._active_pids))
            p.start()

        model_id = ModelManager.build_model_id(request.cb_name, request.model_version, request.dataset_version)
        return TrainingResponse(model_id=model_id)

    @staticmethod
    def get_training_log(resp: TrainingResponse, create: bool = False) -> Path:
        # TODO change method signature
        cb_name, model_version, _ = ModelManager.parse_model_id(resp.model_id)
        model_dir = DataHandler.get_model_directory(cb_name=cb_name, model_version=model_version, create=create)
        log_path = model_dir.joinpath("training.log")
        if create:
            log_path.touch()
        # TODO throw exception
        assert log_path.exists(), f"Log File not found at {log_path}"
        return log_path

    @staticmethod
    def get_train_status(resp: TrainingResponse) -> Optional[TrainingStatus]:
        try:
            status = Trainer._status_dict[resp.model_id]

            # TODO just a quick fix.
            if resp.model_id not in Trainer._active_pids.values():
                status.process_status = 'finished'

            return status

        except Exception:
            return None


"""
The following methods are outside of the class because they have to be pickled for multi-processing and pickling 
methods of classes is not trivial.. (they have to be specially registered to the python interpreter and custom pickling 
functions have to be implemented.)
"""


def input_fn(r: TrainingRequest, train: bool = False):
    # note that TF is not in EagerExecution mode when this method gets called
    # https://www.tensorflow.org/api_docs/python/tf/estimator/Estimator#eager_compatibility

    # create tf datasets (we have to load them in the input fn otherwise we get an EagerExecution problem)
    train_ds, test_ds, label_categories = DatasetManager.get_tensorflow_dataset(r.cb_name, r.dataset_version)
    if train:
        train_ds = train_ds.shuffle(256).batch(r.batch_size_train).repeat()
        return train_ds
    else:
        test_ds = test_ds.shuffle(256).batch(r.batch_size_test)
        return test_ds


def update_training_status(status_dict: Dict[str, TrainingStatus], mid: str, state: TrainingState, pid: int):
    status = TrainingStatus()
    status.state = state
    status.process_status = psutil.Process(pid).status()
    status_dict[mid] = status


@log.catch
def train_eval_export(req: TrainingRequest, status_dict: Dict[str, TrainingStatus], active_pids: Dict[int, str]):
    # TODO use redis or similar to persist status and logs etc
    mid = ModelManager.build_model_id(req.cb_name, req.model_version, req.dataset_version)
    proc = multiprocessing.current_process()
    # add pid to active pids
    active_pids[proc.pid] = mid
    log.info(f"Started train-eval-export cycle process with PID <{str(proc.pid)}>")

    # init training status
    training_status = TrainingStatus()
    status_dict[mid] = training_status

    # intercept logs to loguru sink
    intercept_handler = LoggingInterceptHandler()
    try:
        update_training_status(status_dict, mid, TrainingState.preparing, proc.pid)

        # create log file
        log_file = Trainer.get_training_log(TrainingResponse(model_id=mid), create=True)
        log.info(f"Setting up logging for process with PID <{str(proc.pid)}> at <{str(log_file)}>")
        # create loguru sink
        log.add(str(log_file), rotation="500 MB", enqueue=True)
        tf.get_logger().addHandler(intercept_handler)
        logging.basicConfig(handlers=[intercept_handler], level=0)

        # create model
        log.info(f"Building model <{req.model_version}> for Codebook <{req.cb_name}> with model config"
                 f"<{req.model_config}>. ModelID: <{mid}>")
        dataset_metadata = DatasetManager.get_metadata(req.cb_name, req.dataset_version)
        model, embedding_layer, mid = ModelFactory.build_model(req, n_classes=len(dataset_metadata.labels))

        # train model
        log.info(f"Starting training of model <{mid}>")
        # updating training status
        update_training_status(status_dict, mid, TrainingState.training, proc.pid)
        model.train(input_fn=lambda: input_fn(req, train=True), max_steps=req.max_steps_train)

        # evaluate model
        log.info(f"Starting evaluation of model <{mid}>")
        # updating training status
        update_training_status(status_dict, mid, TrainingState.evaluating, proc.pid)
        eval_results = model.evaluate(input_fn=lambda: input_fn(req, train=False), steps=req.max_steps_test)
        res_pp = pp.pformat(eval_results)
        log.info(f"Evaluation results of model <{mid}>:\n {res_pp}")

        # export # TODO this should be moved to ModelFactory
        log.info(f"Starting export of model <{mid}>")
        # updating training status
        update_training_status(status_dict, mid, TrainingState.training, proc.pid)
        # create serving function
        serving_input_fn = tf.estimator.export.build_parsing_serving_input_receiver_fn(
            tf.feature_column.make_parse_example_spec([embedding_layer]))
        # finally, persist model # TODO this should be moved to DataHandler
        dst = DataHandler.get_model_directory(req.cb_name, req.model_version, create=True)
        estimator_path = model.export_saved_model(str(dst),
                                                  serving_input_fn)
        estimator_path = estimator_path.decode('utf-8')
        log.info(f"Tensorflow exported model successfully at {estimator_path}")
        # move the exported model files to the mode dir (see export_saved_model docs)
        log.info(f"Moving <{mid}> to <{str(dst)}>")
        files = [f for f in Path(estimator_path).iterdir()]
        for f in files:
            shutil.move(str(f), str(f.parent.parent))

        # publish the model
        ModelManager.publish_model(req, eval_results)

        if not ModelManager.is_available(req.cb_name, req.model_version, complete_check=True):
            raise StoringError()

        log.info(f"Successfully exported model <{mid}> at {estimator_path}")
        log.info(f"Completed train-eval-export cycle for model <{mid}>")
        log.info(f"Model <{mid}> stored at {str(dst)}")
        # updating training status
        update_training_status(status_dict, mid, TrainingState.finished, proc.pid)
    except Exception as e:
        update_training_status(status_dict, mid, TrainingState.error, proc.pid)
        raise e
    finally:
        # remove pid from active pids
        active_pids.pop(proc.pid, None)
        # remove logging intercept handlers
        tf.get_logger().removeHandler(intercept_handler)
        logging.basicConfig(handlers=[], level=0)


class LoggingInterceptHandler(logging.Handler):
    def emit(self, record):
        # Get corresponding Loguru level if it exists
        try:
            level = log.level(record.levelname).name
        except ValueError:
            level = record.levelno

        # Find caller from where originated the logged message
        frame, depth = logging.currentframe(), 2
        while frame.f_code.co_filename == logging.__file__:
            frame = frame.f_back
            depth += 1

        log.opt(depth=depth, exception=record.exc_info).log(level, record.getMessage())
