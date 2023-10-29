from typing import Any, Literal
from pydantic import BaseModel, Field

from config_model import ScanConfigModel, ModelConfigModel, SearchConfigModel


class RequestBase(BaseModel):
    pass


class ResponseBase(BaseModel):
    pass


class ScanStartResponse(ResponseBase):
    status: str = Field(description="扫描状态")


class ScanStatusResponse(ResponseBase):
    status: bool = Field(description="当前是否正在扫描")
    total_images: int = Field(description="图片总数")
    total_videos: int = Field(description="视频总数")
    total_video_frames: int = Field(description="视频帧总数")
    scanning_files: int = Field(description="扫描中文件")
    remain_files: int = Field(description="剩余文件")
    progress: float = Field(description="当前进度")
    current_file: str = Field(description="当前文件")
    remain_time: int = Field(description="剩余时间")
    enable_login: bool = Field(description="是否开启登录")


class BaseMatchRequest(RequestBase):
    top_n: int = Field(description="查询数量")
    search_type: int = Field(description="搜索种类")


class SearchByTextRequest(BaseMatchRequest):
    search_type: Literal[0, 2] = Field(description="搜索种类")
    positive: str = Field(description="正向提示词")
    negative: str = Field(description="负向提示词")
    positive_threshold: float = Field(description="正向提示词阈值")
    negative_threshold: float = Field(description="负向提示词阈值")
    path: str | None = Field("", description="按路径搜索的路径")


class SearchByImageInDatabaseRequest(BaseMatchRequest):
    search_type: Literal[5, 6] = Field(description="搜索种类")
    img_id: int = Field(description="图像ID")
    image_threshold: float = Field(description="以图搜索时的图像阈值")


class SearchByImageUploadRequest(BaseMatchRequest):
    search_type: Literal[1, 3] = Field(description="搜索种类")
    image_threshold: float = Field(description="以图搜索时的图像阈值")
    upload_file_hash: str = Field(description="上传文件的哈希值（以图搜时使用）")


class SearchByPathRequest(BaseMatchRequest):
    search_type: Literal[7, 8] = Field(description="搜索种类")
    path: str = Field(description="按路径搜索的路径")


class MatchTextAndImageRequest(BaseMatchRequest):
    search_type: Literal[4] = Field(description="搜索种类")
    text: str = Field(description="匹配图文相似度时的文本")
    upload_file_hash: str = Field(description="上传文件的哈希值（以图搜时使用）")


class SearchImageResponse(ResponseBase):
    type: str = Field("image", description="搜索结果类型")
    url: str = Field(description="图片URL")
    path: str = Field(description="图片路径")
    score: float = Field(description="匹配得分")
    softmax_score: float = Field(description="softmax分数")


class SearchVideoResponse(ResponseBase):
    type: str = Field("video", description="搜索结果类型")
    start_time: str = Field(description="视频片段开始时间")
    end_time: str = Field(description="视频片段结束时间")
    url: str = Field(description="视频URL")
    path: str = Field(description="视频路径")
    score: float = Field(description="匹配得分")
    softmax_score: float = Field(description="softmax分数")


class SearchByPathResponse(ResponseBase):
    type: str = Field(description="搜索结果类型")
    url: str = Field(description="文件URL")
    path: str = Field(description="文件路径")


class MatchTextAndImageResponse(ResponseBase):
    score: float = Field(description="匹配图文相似度得分")


class GetConfigResponse(ResponseBase):
    scan: ScanConfigModel = Field(description="扫描相关配置")
    search: SearchConfigModel = Field(description="搜索相关配置")
    model: ModelConfigModel = Field(description="模型相关配置")


class SetConfigRequest(RequestBase):
    type: Literal["scan", "search", "model"] = Field(description="配置类型")
    key: str = Field(description="配置项")
    value: Any = Field(description="配置值")
