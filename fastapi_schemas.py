from pydantic import BaseModel, Field


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
    positive: str = Field(description="正向提示词")
    negative: str = Field(description="负向提示词")
    positive_threshold: float = Field(description="正向提示词阈值")
    negative_threshold: float = Field(description="负向提示词阈值")
    path: str | None = Field("", description="按路径搜索的路径")


class SearchByImageInDatabaseRequest(BaseMatchRequest):
    img_id: int = Field(description="图像ID")
    image_threshold: float = Field(description="以图搜索时的图像阈值")


class SearchByImageUploadRequest(BaseMatchRequest):
    image_threshold: float = Field(description="以图搜索时的图像阈值")
    upload_file_hash: str = Field(description="上传文件的哈希值（以图搜时使用）")


class SearchByPathRequest(BaseMatchRequest):
    path: str = Field(description="按路径搜索的路径")


class MatchTextAndImageRequest(BaseMatchRequest):
    text: str = Field(description="匹配图文相似度时的文本")
    upload_file_hash: str = Field(description="上传文件的哈希值（以图搜时使用）")


class SearchImageResponse(ResponseBase):
    url: str = Field(description="图片URL")
    path: str = Field(description="图片路径")
    score: float = Field(description="匹配得分")
    softmax_score: float = Field(description="softmax分数")


class SearchVideoResponse(ResponseBase):
    url: str = Field(description="视频URL")
    path: str = Field(description="视频路径")
    score: float = Field(description="匹配得分")
    softmax_score: float = Field(description="softmax分数")
    start_time: int = Field(description="视频片段开始时间")
    end_time: int = Field(description="视频片段结束时间")


class SearchByPathResponse(ResponseBase):
    url: str = Field(description="文件URL")
    path: str = Field(description="文件路径")


class MatchTextAndImageResponse(ResponseBase):
    score: float = Field(description="匹配图文相似度得分")
