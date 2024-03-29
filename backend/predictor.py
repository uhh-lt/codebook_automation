import os
from multiprocessing import Process, Queue
from typing import Dict, List, Tuple, Union

import tensorflow as tf
from loguru import logger as log

from api.model import DocumentDTO, PredictionResult, MultiDocumentPredictionResult, PredictionRequest, \
    MultiDocumentPredictionRequest, TagLabelMapping
from backend import DatasetManager
from backend.exceptions import ErroneousModelException, ErroneousMappingException, PredictionError, \
    ModelNotAvailableException
from backend.model_manager import ModelManager
from config import conf


# TODO
#  - split up document text into chunks of MAX_SEQ_LEN (200?!)
#  - Let user select merging strategy of result (i.e. mean, max, min... over all predictions)
#  - documentation
#  - testing


class Predictor(object):
    _singleton = None

    def __new__(cls, *args, **kwargs):
        if cls._singleton is None:
            log.info('Instantiating Predictor!')

            # disable GPU for prediction if the configured this way.
            if not bool(conf.backend.use_gpu_for_prediction):
                log.info("GPU support for prediction disabled!")
                os.environ["CUDA_VISIBLE_DEVICES"] = "-1"
            else:
                log.info("GPU support for prediction enabled!")

            cls._singleton = super(Predictor, cls).__new__(cls)

        return cls._singleton

    def predict(self, req: Union[PredictionRequest, MultiDocumentPredictionRequest]) -> \
            Union[PredictionResult, MultiDocumentPredictionResult]:

        if not ModelManager.is_available(req.cb_name, req.model_version):
            raise ModelNotAvailableException(cb_name=req.cb_name, model_version=req.model_version)

        def p_single(r: PredictionRequest, q: Queue):
            try:
                cb_name = r.cb_name
                doc = r.doc
                model_version = r.model_version

                # load the model
                model = ModelManager.load(cb_name, model_version=model_version)
                # build the sample(s) for the doc
                samples = self._build_tf_sample(doc)
                # get predictions
                prediction = model.signatures["predict"](examples=samples)
                # build result and add to queue
                q.put(self._build_prediction_result(r, prediction))
            except Exception as e:
                # if any error occurs, return
                log.error("Error occurred within prediction process with PID " + str(os.getpid()) + "!")
                log.error(type(e))
                if hasattr(e, 'message'):
                    log.error(e.message)
                return

        def p_multi(r: MultiDocumentPredictionRequest, q: Queue):
            try:
                cb_name = r.cb_name
                docs = r.docs
                model_version = r.model_version

                # load the model
                model = ModelManager.load(cb_name, model_version=model_version)
                # build the sample(s) for the doc
                samples = [self._build_tf_sample(doc) for doc in docs]
                # get predictions
                predictions = [model.signatures["predict"](examples=sample) for sample in samples]
                # build result and add to queue
                q.put(self._build_multi_prediction_result(r, predictions))
            except Exception as e:
                # if any error occurs, return
                log.error("Error occurred within prediction process with PID " + str(os.getpid()) + "!")
                log.error(type(e))
                if hasattr(e, 'message'):
                    log.error(e.message)
                return

        queue = Queue()

        if isinstance(req, PredictionRequest):
            log.info("Spawning new single document prediction process.")
            proc = Process(target=p_single, args=(req, queue,))
        elif isinstance(req, MultiDocumentPredictionRequest):
            log.info("Spawning new multi document prediction process.")
            proc = Process(target=p_multi, args=(req, queue,))

        proc.start()
        log.info("Started prediction process with PID " + str(proc.pid) + ".")

        log.info("Waiting for prediction process with PID " + str(proc.pid) + " ...")
        proc.join()

        if not queue.empty():
            log.info("Prediction process with PID " + str(proc.pid) + " finished successfully!")
            res = queue.get()
            queue.close()
            return res
        else:
            if proc.is_alive():
                proc.kill()
            queue.close()
            log.error(
                "Prediction process with PID " + str(proc.pid) + " finished erroneously! Process terminated!")
            raise PredictionError()

    @staticmethod
    def _build_tf_sample(doc: DocumentDTO):
        ex = tf.train.Example()
        ex.features.feature['text'].bytes_list.value.extend([bytes(doc.text, encoding='utf-8')])
        return tf.constant(ex.SerializeToString())

    @staticmethod
    def _build_prediction_result(req: PredictionRequest, pred) -> PredictionResult:

        # get the actual labels from the predicted class ids via the dataset id to label map
        mm = ModelManager().get_metadata(req.cb_name, req.model_version)
        dm = DatasetManager().get_metadata(req.cb_name, mm.dataset_version)
        pred_label = dm.labels[str(pred['class_ids'].numpy()[0, 0])]

        classes = list(dm.labels.values())

        probs = pred['probabilities'].numpy()[0].tolist()

        cb_name = req.cb_name
        if not len(probs) == len(classes):
            raise ErroneousModelException(cb_name=cb_name)

        # apply mapping
        doc = req.doc
        mapping = req.mapping
        probabilities, pred_tag = Predictor._apply_mapping(pred_label, classes, probs, mapping, cb_name)

        return PredictionResult(
            doc_id=doc.doc_id,
            proj_id=doc.proj_id,
            codebook_name=cb_name,
            predicted_tag=pred_tag,
            probabilities=probabilities
        )

    @staticmethod
    def _build_multi_prediction_result(req: MultiDocumentPredictionRequest,
                                       preds: List) -> MultiDocumentPredictionResult:

        # get the actual labels from the predicted class ids via the dataset id to label map
        mm = ModelManager().get_metadata(req.cb_name, req.model_version)
        dm = DatasetManager().get_metadata(req.cb_name, mm.dataset_version)
        pred_labels = [dm.labels[str(p['class_ids'].numpy()[0, 0])] for p in preds]

        classes = list(dm.labels.values())

        probs_list = [p['probabilities'].numpy()[0].tolist() for p in preds]

        cb_name = req.cb_name
        if not len(probs_list[0]) == len(classes):
            raise ErroneousModelException(cb_name=cb_name)

        # apply CodeAnno tag to class label mapping
        mapping = req.mapping
        probabilities, pred_tags = dict(), dict()
        for pred_label, probs, doc in zip(pred_labels, probs_list, req.docs):
            mapped_probs, pred_tag = Predictor._apply_mapping(pred_label, classes, probs, mapping, cb_name)
            probabilities[doc.doc_id] = mapped_probs
            pred_tags[doc.doc_id] = pred_tag

        return MultiDocumentPredictionResult(
            proj_id=req.docs[0].proj_id,
            codebook_name=cb_name,
            predicted_tags=pred_tags,
            probabilities=probabilities
        )

    @staticmethod
    def _verify_mapping(classes: List[str], tag_label_map: TagLabelMapping, cb_name: str):

        correct = True

        tag_label_map = tag_label_map.map
        if tag_label_map is None:
            correct = False

        tags = tag_label_map.keys()
        if len(tags) != len(classes):
            correct = False

        if not correct:
            raise ErroneousMappingException(cb_name)

    @staticmethod
    def _apply_mapping(pred_label: str,
                       classes: List[str],
                       probs: List[float],
                       tag_label_map: TagLabelMapping,
                       cb_name: str) \
            -> Tuple[Dict[str, float], str]:

        not_mapped = dict(zip(classes, probs))

        if tag_label_map is not None:
            Predictor._verify_mapping(classes, tag_label_map, cb_name)

            tag_label_map = tag_label_map.map

            label_tag_map = {v: k for k, v in tag_label_map.items()}

            # map the predicted label to tag
            pred_tag = label_tag_map[pred_label]

            # map the other tags
            mapped = dict()
            for m in tag_label_map:
                mapped[m] = not_mapped[tag_label_map[m]]

            return mapped, pred_tag
        else:
            return not_mapped, pred_label
