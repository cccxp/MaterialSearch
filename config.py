import datetime
import os
from pydantic import BaseModel, Field
from dotenv import load_dotenv
import logging


# 加载.env文件中的环境变量
load_dotenv()
logger = logging.getLogger(__name__)

class ScanConfigModel(BaseModel):
    assetsPaths: list[str] = Field(['/home', '/srv'], description='素材所在的目录(绝对路径)')
    skipPaths: list[str] = Field(['/tmp'], description='跳过扫描的目录(绝对路径)')
    ignoreStrings: list[str] = Field(['thumb','avatar','__macosx','icons','cache'], description='如果路径或文件名包含这些字符串，就跳过，不区分大小写')
    imageExtensions: list[str] = Field(['.jpg', '.jpeg','.png','.gif'], description='支持的图片拓展名，小写')
    videoExtensions: list[str] = Field(['.mp4','.flv','.mov','.mkv', '.avi'], description='支持的视频拓展名，小写')
    frameInterval: int = Field(2, description='视频每隔多少秒取一帧，视频展示的时候，间隔小于等于2倍FRAME_INTERVAL的算为同一个素材，同时开始时间和结束时间各延长0.5个FRAME_INTERVAL')
    imageMinWidth: int = Field(64, description='图片最小宽度，小于此宽度则忽略。不需要可以改成0')
    imageMinHeight:int = Field(64, description='图片最小高度，小于此高度则忽略。不需要可以改成0')
    imageMaxPixels: int = Field(100000000, description='图片最大像素数，大于则忽略（避免 PNG Bomb 攻击）')
    autoScan: bool = Field(False, description='是否自动扫描，如果开启，则会在指定时间内进行扫描')
    autoScanStartTime: str = Field("22:30", description='自动扫描开始时间')
    autoScanEndTime: str = Field("8:00", description='自动扫描结束时间')
    autoScanInterval: int = Field(100, description='扫描自动保存间隔')
    scanProcessBatchSize: int = Field(32, description='扫描的视频批处理数量，默认每读取32帧计算一次特征，设置太高或太低都会降低视频扫描效率')

    @property  # property 默认不序列化，也无需序列化
    def autoScanStartTime_(self):
        # 自动扫描开始时间(转为datetime.time)
        return datetime.time(*tuple(map(int, self.autoScanStartTime.split(':'))))

    @property
    def autoScanEndTime_(self):
        # 自动扫描结束时间(转为datetime.time)
        return datetime.time(*tuple(map(int, self.autoScanEndTime.split(':'))))


class ScanConfig:
    def __init__(self) -> None:
        self._config = ScanConfigModel()
        os.makedirs('./config', exist_ok=True)
        self.config_path = './config/scan.json'
        if os.path.exists(self.config_path):
            # 读取配置文件
            self.load_config_from_file()
        else:
            # 初次 dump 默认配置到文件
            # 兼容曾经使用环境变量设置的值
            self._config = ScanConfigModel(
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
            self.save_config_to_file()

    def load_config_from_file(self):
        with open(self.config_path, 'r', encoding='utf-8') as f:
            try:
                self._config = ScanConfigModel.model_validate_json(f.read())
            except ValueError as e:
                logger.error(f'{self.config_path} 配置文件错误')
                logger.error(f'{repr(e)}')
        logger.info('读取扫描配置文件成功')

    def save_config_to_file(self):
        with open(self.config_path, 'w', encoding='utf-8') as f:
            f.write(self._config.model_dump_json(indent=4))

    def get(self, key: str):
        """
        获取配置项
        """
        try:
            ret = getattr(self._config, key)
            return ret
        except AttributeError:
            logger.error(f'scan config not found: {key}')

    def set(self, key: str, value):
        """
        设置配置项
        """
        try:
            setattr(self._config, key, value)
        except AttributeError:
            logger.error(f'scan config set error: {key}: {value}')
        self.save_config_to_file()

    def set_all(self, **kwargs):
        """
        通过参数设置多个配置项
        """
        try:
            self._config = ScanConfig(**kwargs)
        except ValueError as e:
            logger.error(f'{self.config_path} 配置文件设置错误')
            logger.error(f'{repr(e)}')
        self.save_config_to_file()

    def reset(self):
        """
        恢复默认值
        """
        self._config = ScanConfig()
        self.save_config_to_file()


scan_config = ScanConfig()

# *****服务器配置*****
HOST = os.getenv('HOST', '0.0.0.0')  # 监听IP，如果只想本地访问，把这个改成127.0.0.1
PORT = int(os.getenv('PORT', 8085))  # 监听端口
ALLOW_ORIGINS = os.getenv('ALLOW_ORIGINS', '').split(',')  # 允许访问API的IP地址，逗号分隔（用于调试前端）

# *****模型配置*****
# 目前支持中文或英文搜索，只能二选一。英文搜索速度会更快。中文搜索需要额外下载模型，而且搜索英文或NSFW内容的效果不好。
# 更换模型需要删库重新扫描，否则搜索会报错。数据库名字为assets.db。切换语言或设备不需要删库，重启程序即可。
# TEXT_MODEL_NAME 仅在中文搜索时需要，模型需要和 MODEL_NAME 配套。
# 显存小于4G使用： "openai/clip-vit-base-patch32" 和 "IDEA-CCNL/Taiyi-CLIP-Roberta-102M-Chinese"
# 显存大于等于4G使用："openai/clip-vit-large-patch14" 和 "IDEA-CCNL/Taiyi-CLIP-Roberta-large-326M-Chinese"
MODEL_LANGUAGE = os.getenv('MODEL_LANGUAGE', 'Chinese')  # 模型搜索时用的语言，可选：Chinese/English
MODEL_NAME = os.getenv('MODEL_NAME', 'openai/clip-vit-base-patch32')  # CLIP模型
TEXT_MODEL_NAME = os.getenv('TEXT_MODEL_NAME', 'IDEA-CCNL/Taiyi-CLIP-Roberta-102M-Chinese')  # 中文模型，需要和CLIP模型配套使用，如果MODEL_LANGUAGE为English则忽略此项
DEVICE = os.getenv('DEVICE', 'cpu')  # 推理设备，cpu/cuda/mps，建议先跑benchmark.py看看cpu还是显卡速度更快。因为数据搬运也需要时间，所以不一定是GPU更快。
DEVICE_TEXT = os.getenv('DEVICE_TEXT', 'cpu')  # text_encoder使用的设备，如果MODEL_LANGUAGE为English则忽略此项。

# *****搜索配置*****
# 不知道为什么中文模型搜索出来的分数比较低，如果使用英文模型，则POSITIVE_THRESHOLD和NEGATIVE_THRESHOLD可以上调到30。
CACHE_SIZE = int(os.getenv('CACHE_SIZE', 64))  # 搜索缓存条目数量，表示缓存最近的n次搜索结果，0表示不缓存。缓存保存在内存中。图片搜索和视频搜索分开缓存。重启程序或扫描完成会清空缓存，或前端点击清空缓存（前端按钮已隐藏）。
MAX_RESULT_NUM = int(os.getenv('MAX_RESULT_NUM', 150))  # 最大搜索出来的结果数量，如果需要改大这个值，目前还需要手动修改前端代码（前端代码写死最大150）
POSITIVE_THRESHOLD = int(os.getenv('POSITIVE_THRESHOLD', 10))  # 正向搜索词搜出来的素材，高于这个分数才展示。这个是默认值，用的时候可以在前端修改。（前端代码也写死了这个默认值）
NEGATIVE_THRESHOLD = int(os.getenv('NEGATIVE_THRESHOLD', 10))  # 反向搜索词搜出来的素材，低于这个分数才展示。这个是默认值，用的时候可以在前端修改。（前端代码也写死了这个默认值）
IMAGE_THRESHOLD = int(os.getenv('IMAGE_THRESHOLD', 85))  # 图片搜出来的素材，高于这个分数才展示。这个是默认值，用的时候可以在前端修改。（前端代码也写死了这个默认值）

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
FLASK_DEBUG = os.getenv('FLASK_DEBUG', 'False').lower() == 'true'  # flask 调试开关（热重载）
# *****打印配置内容*****
print("********** 运行配置 / RUNNING CONFIGURATIONS **********")
global_vars = globals().copy()
for var_name, var_value in global_vars.items():
    if var_name[0].isupper():
        print(f"{var_name}: {var_value!r}")
print("**************************************************")
