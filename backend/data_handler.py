import shutil
import zipfile
from pathlib import Path
from zipfile import ZipFile

from fastapi import UploadFile
from loguru import logger as log

from api.model import DatasetMetadata, ModelMetadata
from backend.exceptions import DatasetNotAvailableException, ModelNotAvailableException, NoDataForCodebookException, \
    ErroneousDatasetException, ModelMetadataNotAvailableException, DatasetMetadataNotAvailableException, StoringError
from config import conf


class DataHandler(object):
    _singleton = None
    _DATA_ROOT: Path = None
    _relative_dataset_directory: Path = Path("dataset/")
    _relative_model_directory: Path = Path("model/")
    _redis = None

    def __new__(cls, *args, **kwargs):
        if cls._singleton is None:
            log.info('Instantiating DataHandler!')
            cls._singleton = super(DataHandler, cls).__new__(cls)

            # read the data base path from config
            data_root = str(conf.backend.data_root).strip()
            assert data_root is not None and data_root != "", f"Data root path not set!"
            cls._DATA_ROOT = Path(data_root)

            # create the base path if it doesn't exist
            if not cls._DATA_ROOT.exists():
                cls._DATA_ROOT.mkdir(parents=True)

        return cls._singleton

    @staticmethod
    def get_model_directory(cb_name: str, model_version: str = "default", create: bool = False) -> Path:
        model_version = "default" if model_version is None or model_version == "" else model_version
        model_dir = DataHandler._get_data_directory(cb_name, create).joinpath(
            DataHandler._relative_model_directory).joinpath(
            model_version)
        if create:
            model_dir.mkdir(exist_ok=True, parents=True)
        if not model_dir.is_dir():
            raise ModelNotAvailableException(model_version=model_version, cb_name=cb_name)
        return model_dir

    @staticmethod
    def store_dataset(cb_name: str, dataset_archive: UploadFile, dataset_version: str) -> Path:
        try:
            ds_dir = DataHandler.get_dataset_directory(cb_name, dataset_version=dataset_version, create=True)
            dst = ds_dir.joinpath(dataset_archive.filename)
            log.info(f"Extracting dataset archive to {str(dst)}")
            archive_path = DataHandler._store_uploaded_file(dataset_archive, dst)
            return DataHandler._extract_archive(archive=archive_path, dst=ds_dir)
        except Exception as e:
            raise StoringError(msg=f"Error while storing Dataset '{dataset_version}' for Codebook '{cb_name}'",
                               caused_by=str(e))
        finally:
            dataset_archive.file.close()

    @staticmethod
    def store_dataset_metadata(cb_name: str, dataset_metadata: DatasetMetadata) -> Path:
        ds_dir = DataHandler.get_dataset_directory(cb_name, dataset_version=dataset_metadata.version, create=False)
        dst = ds_dir.joinpath('metadata.json')
        with open(dst, 'w') as out:
            log.info(f"Storing dataset metadata at {str(dst)}")
            print(dataset_metadata.json(), file=out)
        if not dst.exists() and DatasetMetadata.parse_file(dst) == dataset_metadata:
            raise StoringError(f"Error while storing Dataset Metadata for Dataset '{dataset_metadata.version}'"
                               f"for Codebook '{cb_name}'!")
        return dst

    @staticmethod
    def get_dataset_metadata(cb_name: str, dataset_version: str) -> DatasetMetadata:
        model_dir = DataHandler.get_dataset_directory(cb_name, dataset_version=dataset_version)
        path = model_dir.joinpath('metadata.json')
        if not path.exists():
            raise DatasetMetadataNotAvailableException(cb_name=cb_name, dataset_version=dataset_version)
        return DatasetMetadata.parse_file(path)

    @staticmethod
    def store_model(cb_name: str, model_archive: UploadFile, model_version: str) -> Path:
        try:
            model_dir = DataHandler.get_model_directory(cb_name, model_version=model_version, create=True)
            dst = model_dir.joinpath(model_archive.filename)
            log.info(f"Extracting model archive to {str(dst)}")
            archive_path = DataHandler._store_uploaded_file(model_archive, dst)
            return DataHandler._extract_archive(archive=archive_path, dst=model_dir)
        except Exception as e:
            raise StoringError(msg=f"Error while storing Model '{model_version}' for Codebook '{cb_name}'",
                               caused_by=str(e))
        finally:
            model_archive.file.close()

    @staticmethod
    def store_model_metadata(cb_name: str, model_metadata: ModelMetadata) -> Path:
        model_dir = DataHandler.get_model_directory(cb_name, model_version=model_metadata.version, create=False)
        dst = model_dir.joinpath('metadata.json')
        with open(dst, 'w') as out:
            log.info(f"Storing model metadata at {str(dst)}")
            print(model_metadata.json(), file=out)
        if not dst.exists() and ModelMetadata.parse_file(dst) == model_metadata:
            raise StoringError(f"Error while storing Model Metadata for Model '{model_metadata.version}'"
                               f"for Codebook '{cb_name}'!")
        return dst

    @staticmethod
    def get_model_metadata(cb_name: str, model_version: str) -> ModelMetadata:
        model_dir = DataHandler.get_model_directory(cb_name, model_version=model_version)
        path = model_dir.joinpath('metadata.json')
        if not path.exists():
            raise ModelMetadataNotAvailableException(model_version=model_version, cb_name=cb_name)
        return ModelMetadata.parse_file(path)

    @staticmethod
    def get_dataset_directory(cb_name: str, dataset_version: str = "default", create: bool = False) -> Path:
        data_directory = DataHandler._get_data_directory(cb_name, create).joinpath(
            DataHandler._relative_dataset_directory).joinpath(
            dataset_version)
        if create:
            data_directory.mkdir(exist_ok=True, parents=True)
        if not data_directory.is_dir():
            raise DatasetNotAvailableException(dataset_version=dataset_version, cb_name=cb_name)
        return data_directory

    @staticmethod
    def _get_data_directory(cb_name: str, create: bool = False) -> Path:
        data_directory = Path(DataHandler._DATA_ROOT, cb_name)
        if create:
            data_directory.mkdir(exist_ok=True, parents=True)
        if not data_directory.is_dir():
            raise NoDataForCodebookException(cb_name=cb_name)
        return data_directory

    @staticmethod
    def _extract_archive(archive: Path, dst: Path):
        assert zipfile.is_zipfile(archive)
        with ZipFile(archive, 'r') as zip_archive:
            zip_archive.extractall(dst)
        if not dst.is_dir():
            raise ErroneousDatasetException(msg="Cannot extract dataset zip archive!")
        if not dst.joinpath('train.csv').exists():
            raise ErroneousDatasetException(msg="Dataset archive does not contain test.csv file!")
        if not dst.joinpath('test.csv').exists():
            raise ErroneousDatasetException(msg="Dataset archive does not contain test.csv file!")
        return dst

    @staticmethod
    def _store_uploaded_file(uploaded_file: UploadFile, dst: Path):
        try:
            with open(dst, "wb") as buffer:
                shutil.copyfileobj(uploaded_file.file, buffer)
                return Path(dst)
        except Exception as e:
            raise StoringError(msg=f"Cannot store uploaded file at {str(dst)}!", caused_by=str(e))

    @staticmethod
    def purge_dataset_directory(cb_name: str, dataset_version: str):
        dataset_dir = DataHandler.get_dataset_directory(cb_name, dataset_version=dataset_version)
        log.warning(f"Permanently removing dataset '{dataset_version}' of Codebook '{cb_name}'")
        shutil.rmtree(dataset_dir)

    @staticmethod
    def purge_model_directory(cb_name: str, model_version: str):
        model_dir = DataHandler.get_model_directory(cb_name, model_version=model_version)
        log.warning(f"Permanently removing data of model '{model_version}' of Codebook '{cb_name}'")
        shutil.rmtree(model_dir)

    @staticmethod
    def _purge_data(cb_name: str):
        log.warning(
            f"Permanently removing all data (including models and datasets) of Codebook <{cb_name}>!")
        data_directory = Path(DataHandler._DATA_ROOT, cb_name)
        shutil.rmtree(data_directory)
