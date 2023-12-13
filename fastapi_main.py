import base64
import logging
import os
import shutil
import threading
from contextlib import asynccontextmanager
from typing import Annotated, Union

from fastapi import (
    APIRouter,
    BackgroundTasks,
    FastAPI,
    Path,
    UploadFile,
    WebSocket,
    status,
)
from fastapi.responses import FileResponse, RedirectResponse, Response
from fastapi.staticfiles import StaticFiles
from pydantic import ValidationError
from starlette.middleware import Middleware
from starlette.middleware.cors import CORSMiddleware

import crud
from benchmark import Benchmark
from config import model_config, scan_config, search_config, server_config
from database import SessionLocal
from fastapi_schemas import (
    GetConfigResponse,
    MatchTextAndImageRequest,
    MatchTextAndImageResponse,
    ScanStartResponse,
    ScanStatusResponse,
    SearchByImageInDatabaseRequest,
    SearchByImageUploadRequest,
    SearchByPathRequest,
    SearchByPathResponse,
    SearchByTextRequest,
    SearchImageResponse,
    SearchVideoResponse,
    SetConfigRequest,
    SetConfigResponse,
)
from optimize_database import optimize_database
from process_assets import crop_video, match_text_and_image, process_image, process_text
from scan import Scanner
from search import (
    clean_cache,
    search_image_by_image,
    search_image_by_text,
    search_image_file,
    search_video_by_image,
    search_video_by_text,
    search_video_file,
)
from utils import get_hash

logging.basicConfig(
    level=server_config.value.logLevel,
    format="%(asctime)s %(name)s %(levelname)s %(message)s",
)
logger = logging.getLogger(__name__)
scanner = Scanner()


@asynccontextmanager
async def lifespan(app: FastAPI):
    """
    初始化数据库，创建临时文件夹，根据AUTO_SCAN决定是否开启自动扫描线程
    :return: None
    """
    # 参考： https://fastapi.tiangolo.com/advanced/events/
    # yield 前的部分为此前 startup 事件
    # 在这里编写初始化代码
    global scanner
    # 删除上传目录中所有文件
    shutil.rmtree(f"{server_config.value.tempPath}/upload", ignore_errors=True)
    os.makedirs(f"{server_config.value.tempPath}/upload")
    shutil.rmtree(f"{server_config.value.tempPath}/video_clips", ignore_errors=True)
    os.makedirs(f"{server_config.value.tempPath}/video_clips")
    # 兼容曾经的 Flask-SQLAlchemy 数据库默认路径
    os.makedirs("./var/main-instance/", exist_ok=True)
    scanner.init()
    optimize_database()  # 数据库优化（临时功能）
    if scan_config.value.autoScan:
        auto_scan_thread = threading.Thread(target=scanner.auto_scan, args=())
        auto_scan_thread.start()
    yield
    # yield 后的部分为此前 shutdown 事件
    # 在这里编写清理代码


middleware = [
    Middleware(
        CORSMiddleware,
        allow_origins=server_config.value.allowOrigins,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )
]
app = FastAPI(lifespan=lifespan, middleware=middleware)
app.mount("/static", StaticFiles(directory="static"), name="static")
router = APIRouter(prefix="/api")
wsrouter = APIRouter(prefix="/ws")


@app.get("/", name="Home Page")
def index_page():
    """主页"""
    return RedirectResponse("/static/index.html")


@router.get("/scan", response_model=ScanStartResponse)
def api_scan(backgroundtasks: BackgroundTasks):
    """开始扫描"""
    global scanner
    if not scanner.is_scanning:
        backgroundtasks.add_task(scanner.scan, False)
        return ScanStartResponse(status="start scanning")
    return ScanStartResponse(status="already scanning")


@router.get("/status", response_model=ScanStatusResponse)
def api_status():
    """获取扫描状态"""
    global scanner
    return ScanStatusResponse(**scanner.get_status())


@router.get("/clean_cache")
def api_clean_cache():
    """清缓存"""
    clean_cache()
    return Response("", status.HTTP_204_NO_CONTENT)


@router.post(
    "/match",
    response_model=Union[
        list[SearchVideoResponse],
        list[SearchImageResponse],
        list[SearchByPathResponse],
        MatchTextAndImageResponse,
    ],
)
def api_match(
    r: Union[
        SearchByTextRequest,
        SearchByImageInDatabaseRequest,
        SearchByImageUploadRequest,
        SearchByPathRequest,
        MatchTextAndImageRequest,
    ]
):
    """
    匹配文字对应的素材
    """
    try:
        upload_file_hash = r.upload_file_hash
        upload_file_path = f"{server_config.value.tempPath}/upload/{upload_file_hash}"
    except AttributeError:
        pass
    logger.debug(r)
    # 进行匹配
    match r.search_type:  # 文字搜图
        case 0:
            results = search_image_by_text(
                r.positive, r.negative, r.positive_threshold, r.negative_threshold
            )[: r.top_n]
            results = [SearchImageResponse(**i) for i in results]
        case 1:  # 以图搜图
            if not upload_file_path:
                return Response(status_code=status.HTTP_400_BAD_REQUEST)
            print(upload_file_path)
            results = search_image_by_image(upload_file_path, r.image_threshold)[
                : r.top_n
            ]
            results = [SearchImageResponse(**i) for i in results]
        case 2:  # 文字搜视频
            results = search_video_by_text(
                r.positive, r.negative, r.positive_threshold, r.negative_threshold
            )[: r.top_n]
            results = [SearchVideoResponse(**i) for i in results]
        case 3:  # 以图搜视频
            if not upload_file_path:
                return Response(status_code=status.HTTP_400_BAD_REQUEST)
            results = search_video_by_image(upload_file_path, r.image_threshold)[
                : r.top_n
            ]
            results = [SearchVideoResponse(**i) for i in results]
        case 4:  # 图文相似度匹配
            if not upload_file_path:
                return Response(status_code=status.HTTP_400_BAD_REQUEST)
            return MatchTextAndImageResponse(
                score=match_text_and_image(
                    process_text(r.text), process_image(upload_file_path)
                )
            )
        case 5:  # 以图搜图(图片是数据库中的)
            results = search_image_by_image(r.img_id, r.image_threshold)[: r.top_n]
            results = [SearchImageResponse(**i) for i in results]
        case 6:  # 以图搜视频(图片是数据库中的)
            results = search_video_by_image(r.img_id, r.image_threshold)[: r.top_n]
            results = [SearchVideoResponse(**i) for i in results]
        case 7:  # 路径搜图
            results = search_image_file(r.path)[: r.top_n]
            results = [SearchByPathResponse(**i) for i in results]
        case 8:  # 路径搜视频
            results = search_video_file(r.path)[: r.top_n]
            results = [SearchByPathResponse(**i) for i in results]
        case _:  # 空
            logger.warning(f"search_type不正确：{r.search_type}")
            return Response(status_code=status.HTTP_400_BAD_REQUEST)
    return results


@router.get("/get_image/{image_id}")
def api_get_image(image_id: Annotated[int, Path(title="图片ID")]):
    """
    读取图片
    :param image_id: int, 图片在数据库中的id
    :return: 图片文件
    """
    with SessionLocal() as session:
        path = crud.get_image_path_by_id(session, image_id)
        logger.debug(path)
        if not path:
            return Response(b"", status.HTTP_404_NOT_FOUND)
        return FileResponse(path)


@router.get("/get_video/{video_path}")
def api_get_video(video_path: Annotated[str, Path(title="视频路径")]):
    """
    读取视频
    :param video_path: string, 经过base64.urlsafe_b64encode的字符串，解码后可以得到视频在服务器上的绝对路径
    :return: 视频文件
    """
    path = base64.urlsafe_b64decode(video_path).decode()
    logger.debug(path)
    with SessionLocal() as session:
        if not crud.is_video_exist(session, path):  # 如果路径不在数据库中，则返回404，防止任意文件读取攻击
            return Response(status_code=status.HTTP_404_NOT_FOUND)
    return FileResponse(path)


@router.get("/download_video_clip/{video_path}/{start_time}/{end_time}")
def api_download_video_clip(
    video_path: Annotated[str, Path(title="视频路径")],
    start_time: Annotated[int, Path(title="开始时间")],
    end_time: Annotated[int, Path(title="结束时间")],
):
    """
    下载视频片段
    """
    path = base64.urlsafe_b64decode(video_path).decode()
    logger.debug(path)
    with SessionLocal() as session:
        if not crud.is_video_exist(session, path):  # 如果路径不在数据库中，则返回404，防止任意文件读取攻击
            return Response(status_code=status.HTTP_404_NOT_FOUND)
    # 根据 VIDEO_EXTENSION_LENGTH 调整时长
    output_path = crop_video(path, start_time, end_time)
    return FileResponse(output_path)


@router.post("/upload")
async def api_upload(file: UploadFile):
    """
    上传文件。计算hash, 保存为对应文件名
    FIXME: 由于无状态的设计，这里无法兼容原 API
    FIXME: 同理，登录操作也无法兼容原 API，需要新的设计
    """
    logger.debug(file)
    # 保存文件
    filehash = get_hash(await file.read())
    upload_file_path = f"{server_config.value.tempPath}/upload/{filehash}"
    with open(upload_file_path, "wb") as f:
        await file.seek(0)
        f.write(await file.read())
    return {"filehash": filehash}  # 返回文件哈希值，用于后续搜索时传入


@router.get(
    "/get_config",
    response_model=GetConfigResponse,
)
async def get_config():
    """
    获取当前配置信息
    """
    return GetConfigResponse(
        scan=scan_config.value, model=model_config.value, search=search_config.value
    )


@router.post(
    "/set_config",
)
async def set_config(r: SetConfigRequest):
    """
    TODO: 设置配置项
    """
    try:
        match r.type:
            case "scan":
                scan_config.value = r.value
            case "model":
                model_config.value = r.value
            case "search":
                search_config.value = r.value
            case _:
                return Response("", status.HTTP_404_NOT_FOUND)
    except ValidationError as e:
        # 格式错误
        return SetConfigResponse(success=False, message=repr(e))
    return SetConfigResponse(success=True, message="ok")


@wsrouter.websocket("/benchmark")
async def benckmark(websocket: WebSocket):
    await websocket.accept()
    msg = await websocket.receive()
    sign = msg.get("text", "")
    if sign != "start":
        await websocket.close()
        return
    bm = Benchmark(websocket)
    await bm.run()
    await websocket.close()


router.include_router(wsrouter)
app.include_router(router)


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(
        "fastapi_main:app",
        host=server_config.value.host,
        port=server_config.value.port,
        reload=server_config.value.hotReload,
    )
