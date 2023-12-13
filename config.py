import abc
import logging
import os

from dotenv import load_dotenv

from config_model import (
    BaseConfigModel,
    ModelConfigModel,
    ScanConfigModel,
    SearchConfigModel,
    ServerConfigModel,
)

logger = logging.getLogger(__name__)


class BaseConfig(metaclass=abc.ABCMeta):
    @property
    @abc.abstractmethod
    def config_path(self) -> str:
        return "./config/abstract_config.json"

    def __repr__(self) -> str:
        return repr(self.value)

    @property
    def value(self):
        return self._config

    @value.setter
    def value(self, data):
        # 验证 json 格式
        self._config = self.config_model_class.model_validate(data)
        self.save_to_file()

    def __init__(self, config_model_class: BaseConfigModel) -> None:
        self.config_model_class = config_model_class
        os.makedirs("./config", exist_ok=True)
        if os.path.exists(self.config_path):
            # 读取配置文件
            self.load_from_file()
        else:
            print(self.config_path, "load from env")
            # 加载.env文件中的环境变量
            load_dotenv()
            self.load_from_env()
            # 初次 dump 默认配置到文件
            self.save_to_file()

    @abc.abstractmethod
    def load_from_env(self):
        # 从环境变量加载配置
        # 兼容曾经使用环境变量设置的值
        pass

    def load_from_file(self):
        with open(self.config_path, "r", encoding="utf-8") as f:
            try:
                self.value = self.config_model_class.model_validate_json(f.read())
            except ValueError as e:
                logger.error(f"{self.config_path} 配置文件错误")
                logger.error(f"{repr(e)}")
        logger.info("读取扫描配置文件成功")

    def save_to_file(self):
        with open(self.config_path, "w", encoding="utf-8") as f:
            f.write(self.value.model_dump_json(indent=4))


class ScanConfig(BaseConfig):
    value: ScanConfigModel

    @property
    def config_path(self) -> str:
        return "./config/scan.json"

    def __init__(self) -> None:
        super().__init__(ScanConfigModel)

    def load_from_env(self):
        self.value = ScanConfigModel(
            assetsPaths=os.getenv("ASSETS_PATH", "/home,/srv").split(","),
            skipPaths=os.getenv("SKIP_PATH", "/tmp").split(","),
            imageExtensions=os.getenv("IMAGE_EXTENSIONS", ".jpg,.jpeg,.png,.gif").split(
                ","
            ),
            videoExtensions=os.getenv("VIDEO_EXTENSIONS", ".mp4,.flv,.mov,.mkv").split(
                ","
            ),
            ignoreStrings=os.getenv(
                "IGNORE_STRINGS", "thumb,avatar,__macosx,icons,cache"
            ).split(","),
            frameInterval=int(os.getenv("FRAME_INTERVAL", 2)),
            imageMinWidth=int(os.getenv("IMAGE_MIN_WIDTH", 64)),
            imageMinHeight=int(os.getenv("IMAGE_MIN_HEIGHT", 64)),
            imageMaxPixels=int(os.getenv("IMAGE_MAX_PIXELS", 100000000)),
            autoScan=os.getenv("AUTO_SCAN", "False").lower() == "true",
            autoScanStartTime=os.getenv("AUTO_SCAN_START_TIME", "22:30"),
            autoScanEndTime=os.getenv("AUTO_SCAN_END_TIME", "8:00"),
            autoScanInterval=int(os.getenv("AUTO_SAVE_INTERVAL", 100)),
            scanProcessBatchSize=int(os.getenv("SCAN_PROCESS_BATCH_SIZE", 32)),
        )


class ModelConfig(BaseConfig):
    value: ModelConfigModel

    @property
    def config_path(self) -> str:
        return "./config/model.json"

    def __init__(self) -> None:
        super().__init__(ModelConfigModel)

    def load_from_env(self):
        self.value = ModelConfigModel(
            language=os.getenv("MODEL_LANGUAGE", "Chinese"),
            name=os.getenv("MODEL_NAME", "openai/clip-vit-base-patch32"),
            textModelName=os.getenv(
                "TEXT_MODEL_NAME", "IDEA-CCNL/Taiyi-CLIP-Roberta-102M-Chinese"
            ),
            device=os.getenv("DEVICE", "cpu"),
            textDevice=os.getenv("DEVICE_TEXT", "cpu"),
        )


class SearchConfig(BaseConfig):
    value: SearchConfigModel

    @property
    def config_path(self) -> str:
        return "./config/search.json"

    def __init__(self) -> None:
        super().__init__(SearchConfigModel)

    def load_from_env(self):
        self.value = SearchConfigModel(
            cacheSize=int(os.getenv("CACHE_SIZE", "64")),
            maxResultNum=int(os.getenv("MAX_RESULT_NUM", "150")),
        )


class ServerConfig(BaseConfig):
    value: ServerConfigModel

    @property
    def config_path(self) -> str:
        return "./config/server.json"

    def __init__(self) -> None:
        super().__init__(ServerConfigModel)

    def load_from_env(self):
        self.value = ServerConfigModel(
            host=os.getenv("HOST", "0.0.0.0"),
            port=int(os.getenv("PORT", 8085)),
            allowOrigins=os.getenv("ALLOW_ORIGINS", "").split(","),
            # *****日志配置*****
            logLevel=os.getenv("LOG_LEVEL", "INFO"),
            # *****其它配置*****
            sqlAlchemyDatabaseUrl=os.getenv(
                "SQLALCHEMY_DATABASE_URL", "sqlite:///./var/main-instance/assets.db"
            ),
            tempPath=os.getenv("TEMP_PATH", "./tmp"),
            videoExtensionLength=int(os.getenv("VIDEO_EXTENSION_LENGTH", 0)),
            enableLogin=os.getenv("ENABLE_LOGIN", "False").lower() == "true",
            username=os.getenv("USERNAME", "admin"),
            password=os.getenv("PASSWORD", "MaterialSearch"),
            hotReload=os.getenv("HOT_RELOAD", "False").lower() == "true",
        )


def print_running_configurations():
    # 打印配置内容

    print("********** 运行配置 / RUNNING CONFIGURATIONS **********")
    global_vars = globals().copy()

    for var_name, var_value in filter(
        lambda data: data[0].endswith("_config"), global_vars.items()
    ):
        print(f"{var_name}: {var_value!r}")
    print("**************************************************")


scan_config = ScanConfig()
model_config = ModelConfig()
search_config = SearchConfig()
server_config = ServerConfig()

print_running_configurations()
