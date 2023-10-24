import abc
import inspect
import logging
import os

from dotenv import load_dotenv
from config_model import * 

logger = logging.getLogger(__name__)


class BaseConfig(metaclass=abc.ABCMeta):
    @property
    @abc.abstractmethod
    def config_path(self) -> str:
        return './config/abstract_config.json'
    
    def __repr__(self) -> str:
        return repr(self.value)
 
    @property
    def value(self):
        return self._config 

    @value.setter 
    def value(self, data):
        self._config = data
        self.save_to_file()
    
    def __init__(self, config_model_class: BaseConfigModel) -> None:
        self.config_model_class = config_model_class
        os.makedirs('./config', exist_ok=True)
        if os.path.exists(self.config_path):
            # 读取配置文件
            self.load_from_file()
        else:
            print(self.config_path, 'load from env')
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
        with open(self.config_path, 'r', encoding='utf-8') as f:
            try:
                self.value = self.config_model_class.model_validate_json(f.read())
            except ValueError as e:
                logger.error(f'{self.config_path} 配置文件错误')
                logger.error(f'{repr(e)}')
        logger.info('读取扫描配置文件成功')

    def save_to_file(self):
        with open(self.config_path, 'w', encoding='utf-8') as f:
            f.write(self.value.model_dump_json(indent=4))


class ScanConfig(BaseConfig):
    value: ScanConfigModel
    @property
    def config_path(self) -> str:
        return './config/scan.json'

    def __init__(self) -> None:
        super().__init__(ScanConfigModel)

    def load_from_env(self):
        self.value = ScanConfigModel(
            assetsPaths = os.getenv('ASSETS_PATH', '/home,/srv').split(','),
            skipPaths = os.getenv('SKIP_PATH', '/tmp').split(','),
            imageExtensions = os.getenv('IMAGE_EXTENSIONS', '.jpg,.jpeg,.png,.gif').split(','),
            videoExtensions = os.getenv('VIDEO_EXTENSIONS', '.mp4,.flv,.mov,.mkv').split(','),
            ignoreStrings = os.getenv('IGNORE_STRINGS', 'thumb,avatar,__macosx,icons,cache').split(','),
            frameInterval = int(os.getenv('FRAME_INTERVAL', 2)),
            imageMinWidth = int(os.getenv('IMAGE_MIN_WIDTH', 64)),
            imageMinHeight = int(os.getenv('IMAGE_MIN_HEIGHT', 64)),
            imageMaxPixels = int(os.getenv('IMAGE_MAX_PIXELS', 100000000)),
            autoScan = os.getenv('AUTO_SCAN', 'False').lower() == 'true',
            autoScanStartTime = os.getenv('AUTO_SCAN_START_TIME', '22:30'),
            autoScanEndTime = os.getenv('AUTO_SCAN_END_TIME', '8:00'),
            autoScanInterval = int(os.getenv('AUTO_SAVE_INTERVAL', 100)),
            scanProcessBatchSize = int(os.getenv('SCAN_PROCESS_BATCH_SIZE', 32)),
        )

class ModelConfig(BaseConfig):
    value: ModelConfigModel
    @property
    def config_path(self) -> str:
        return './config/model.json'
        
    def __init__(self) -> None:
        super().__init__(ModelConfigModel)

    def load_from_env(self):
        self.value = ModelConfigModel(
            language = os.getenv('MODEL_LANGUAGE', 'Chinese'),
            name = os.getenv('MODEL_NAME', 'openai/clip-vit-base-patch32'),
            textModelName = os.getenv('TEXT_MODEL_NAME', 'IDEA-CCNL/Taiyi-CLIP-Roberta-102M-Chinese'),
            device = os.getenv('DEVICE', 'cpu'),
            textDevice = os.getenv('DEVICE_TEXT', 'cpu'),
        )


class SearchConfig(BaseConfig):
    value: SearchConfigModel
    @property
    def config_path(self) -> str:
        return './config/search.json'
        
    def __init__(self) -> None:
        super().__init__(SearchConfigModel)

    def load_from_env(self):
        self.value = SearchConfigModel(
            cacheSize = int(os.getenv('CACHE_SIZE', '64')),
            maxResultNum = int(os.getenv('MAX_RESULT_NUM', '150')),
        )
    

scan_config = ScanConfig()
model_config = ModelConfig()
search_config = SearchConfig()

# *****服务器配置*****
HOST = os.getenv('HOST', '0.0.0.0')  # 监听IP，如果只想本地访问，把这个改成127.0.0.1
PORT = int(os.getenv('PORT', 8085))  # 监听端口
ALLOW_ORIGINS = os.getenv('ALLOW_ORIGINS', '').split(',')  # 允许访问API的IP地址，逗号分隔（用于调试前端）

# *****日志配置*****
LOG_LEVEL = os.getenv('LOG_LEVEL', 'INFO')  # 日志等级：NOTSET/DEBUG/INFO/WARNING/ERROR/CRITICAL

# *****其它配置*****
# 数据库保存路径，默认路径为兼容 flask_sqlalchemy 创建的数据库
SQLALCHEMY_DATABASE_URL = os.getenv('SQLALCHEMY_DATABASE_URL', 'sqlite:///./var/main-instance/assets.db')  # 数据库保存路径
TEMP_PATH = os.getenv('TEMP_PATH', './tmp')  # 临时目录路径
VIDEO_EXTENSION_LENGTH = int(os.getenv('VIDEO_EXTENSION_LENGTH', 0))  # 下载视频片段时，视频前后增加的时长，单位为秒
ENABLE_LOGIN = os.getenv('ENABLE_LOGIN', 'False').lower() == 'true'  # 是否启用登录
USERNAME = os.getenv('USERNAME', 'admin')  # 登录用户名
PASSWORD = os.getenv('PASSWORD', 'MaterialSearch')  # 登录密码
HOT_RELOAD = os.getenv('HOT_RELOAD', 'False').lower() == 'true'  # flask / fastapi 调试开关（热重载）
# *****打印配置内容*****

def config_variable_filter(data):
    k, v = data  # 解包
    if any((inspect.ismodule(v), inspect.isclass(v), inspect.isfunction(v))):
        return False  # 跳过模块、类、函数
    # 如果变量名第一个字母为大写或以 config 结尾，则为配置
    return k[0].isupper() or k.endswith('config')


print("********** 运行配置 / RUNNING CONFIGURATIONS **********")
global_vars = globals().copy()

for var_name, var_value in filter(config_variable_filter, global_vars.items()):
    print(f"{var_name}: {var_value!r}")
print("**************************************************")
