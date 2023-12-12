import datetime
from typing import Literal

from pydantic import BaseModel, Field


class BaseConfigModel(BaseModel):
    def __repr__(self) -> str:
        # 优化打印
        ret = str(self.__class__) + "\n"
        for k, v in self.model_dump().items():
            ret += f"\t{k}: {repr(v)}\n"
        return ret


class ScanConfigModel(BaseConfigModel):
    """扫描配置"""

    assetsPaths: list[str] = Field(["/home", "/srv"], description="素材所在的目录(绝对路径)")
    skipPaths: list[str] = Field(["/tmp"], description="跳过扫描的目录(绝对路径)")
    ignoreStrings: list[str] = Field(
        ["thumb", "avatar", "__macosx", "icons", "cache"],
        description="如果路径或文件名包含这些字符串，就跳过，不区分大小写",
    )
    imageExtensions: list[str] = Field(
        [".jpg", ".jpeg", ".png", ".gif"], description="支持的图片拓展名，小写"
    )
    videoExtensions: list[str] = Field(
        [".mp4", ".flv", ".mov", ".mkv", ".avi"], description="支持的视频拓展名，小写"
    )
    frameInterval: int = Field(
        2,
        description="视频每隔多少秒取一帧，视频展示的时候，间隔小于等于2倍FRAME_INTERVAL的算为同一个素材，同时开始时间和结束时间各延长0.5个FRAME_INTERVAL",
    )
    imageMinWidth: int = Field(64, description="图片最小宽度，小于此宽度则忽略。不需要可以改成0")
    imageMinHeight: int = Field(64, description="图片最小高度，小于此高度则忽略。不需要可以改成0")
    imageMaxPixels: int = Field(100000000, description="图片最大像素数，大于则忽略（避免 PNG Bomb 攻击）")
    autoScan: bool = Field(False, description="是否自动扫描，如果开启，则会在指定时间内进行扫描")
    autoScanStartTime: str = Field("22:30", description="自动扫描开始时间")
    autoScanEndTime: str = Field("8:00", description="自动扫描结束时间")
    autoScanInterval: int = Field(100, description="扫描自动保存间隔")
    scanProcessBatchSize: int = Field(
        32, description="扫描的视频批处理数量，默认每读取32帧计算一次特征，设置太高或太低都会降低视频扫描效率"
    )

    @property  # property 默认不序列化，也无需序列化
    def autoScanStartTime_(self):
        # 自动扫描开始时间(转为datetime.time)
        return datetime.time(*tuple(map(int, self.autoScanStartTime.split(":"))))

    @property
    def autoScanEndTime_(self):
        # 自动扫描结束时间(转为datetime.time)
        return datetime.time(*tuple(map(int, self.autoScanEndTime.split(":"))))


class ModelConfigModel(BaseConfigModel):
    """模型配置
    目前支持中文或英文搜索，只能二选一。英文搜索速度会更快。
    中文搜索需要额外下载模型，而且搜索英文或NSFW内容的效果不好。
    更换模型需要删库重新扫描，否则搜索会报错。
    数据库名字为assets.db。切换语言或设备不需要删库，重启程序即可。
    TEXT_MODEL_NAME 仅在中文搜索时需要，模型需要和 MODEL_NAME 配套。
    显存小于4G使用： "openai/clip-vit-base-patch32" 和 "IDEA-CCNL/Taiyi-CLIP-Roberta-102M-Chinese"
    显存大于等于4G使用："openai/clip-vit-large-patch14" 和 "IDEA-CCNL/Taiyi-CLIP-Roberta-large-326M-Chinese"
    """

    language: Literal["Chinese", "English"] = Field(
        "Chinese", description="模型搜索时用的语言，可选：Chinese/English"
    )
    name: str = Field("openai/clip-vit-base-patch32", description="CLIP模型")
    textModelName: str = Field(
        "IDEA-CCNL/Taiyi-CLIP-Roberta-102M-Chinese",
        description="中文模型，需要和CLIP模型配套使用，如果MODEL_LANGUAGE为English则忽略此项",
    )
    device: Literal["cpu", "cuda", "mps"] = Field(
        "cpu",
        description="推理设备，cpu/cuda/mps，建议先跑benchmark.py看看cpu还是显卡速度更快。因为数据搬运也需要时间，所以不一定是GPU更快",
    )
    textDevice: Literal["cpu", "cuda", "mps"] = Field(
        "cpu", description="text_encoder使用的设备，如果MODEL_LANGUAGE为English则忽略此项"
    )


class SearchConfigModel(BaseConfigModel):
    """搜索配置"""

    cacheSize: int = Field(
        64,
        description="搜索缓存条目数量，表示缓存最近的n次搜索结果，0表示不缓存。缓存保存在内存中。图片搜索和视频搜索分开缓存。重启程序或扫描完成会清空缓存，或前端点击清空缓存（前端按钮已隐藏）",
    )
    maxResultNum: int = Field(
        150, description="最大搜索出来的结果数量，如果需要改大这个值，目前还需要手动修改前端代码（前端代码写死最大150）"
    )  # TODO: 修改前端


class ServerConfigModel(BaseConfigModel):
    """服务器相关配置"""

    host: str = Field("0.0.0.0", description="监听IP。如果只想本地访问，把这个改成127.0.0.1")
    port: int = Field(8085, description="监听端口")
    allowOrigins: list[str] = Field([], description="允许访问API的IP地址，逗号分隔（用于调试前端）")
    logLevel: Literal[
        "NOTSET", "DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"
    ] = Field("INFO", description="日志等级：NOTSET/DEBUG/INFO/WARNING/ERROR/CRITICAL")
    sqlAlchemyDatabaseUrl: str = Field(
        "sqlite:///./var/main-instance/assets.db", description="数据库保存路径"
    )
    tempPath: str = Field("./tmp", description="临时目录路径")
    videoExtensionLength: int = Field(0, description="下载视频片段时，视频前后增加的时长，单位为秒")
    enableLogin: bool = Field(False, description="是否启用登录")
    username: str = Field("admin", description="登录用户名")
    password: str = Field("MaterialSearch", description="登录密码")
    hotReload: bool = Field(False, description="flask / fastapi 调试开关（热重载）")
