import base64
import logging
import time
from functools import lru_cache

import numpy as np

import crud
from config import *
from database import SessionLocal
from process_assets import match_batch, process_image, process_text
from utils import softmax

logger = logging.getLogger(__name__)


def clean_cache():
    """
    清空搜索缓存
    :return: None
    """
    search_image_by_text.cache_clear()
    search_image_by_image.cache_clear()
    search_image_file.cache_clear()
    search_video_by_text.cache_clear()
    search_video_by_image.cache_clear()
    search_video_file.cache_clear()


def search_image_by_feature(
    positive_feature,
    negative_feature=None,
    positive_threshold=POSITIVE_THRESHOLD,
    negative_threshold=NEGATIVE_THRESHOLD,
):
    """
    通过特征搜索图片
    :param positive_feature: np.array, 正向特征向量
    :param negative_feature: np.array, 反向特征向量
    :param positive_threshold: int/float, 正向阈值
    :param negative_threshold: int/float, 反向阈值
    :return: list[dict], 搜索结果列表
    """
    t0 = time.time()
    with SessionLocal() as session:
        ids, paths, features = crud.get_image_id_path_features(session)
    features = np.frombuffer(b"".join(features), dtype=np.float32).reshape(
        len(features), -1
    )
    if len(ids) == 0:  # 没有素材，直接返回空
        return []
    scores = match_batch(
        positive_feature,
        negative_feature,
        features,
        positive_threshold,
        negative_threshold,
    )
    data_list = []
    scores_list = []
    for i in range(len(ids)):
        if not scores[i]:
            continue
        data_list.append((ids[i], paths[i], scores[i]))
        scores_list.append(scores[i])
    softmax_scores = softmax(scores_list)
    return_list = [
        {
            "url": "api/get_image/%d" % id,
            "path": path,
            "score": float(score),
            "softmax_score": float(softmax_score),
        }
        for (id, path, score), softmax_score in zip(data_list, softmax_scores)
    ]
    return_list = sorted(return_list, key=lambda x: x["score"], reverse=True)
    logger.info("查询使用时间：%.2f" % (time.time() - t0))
    return return_list


@lru_cache(maxsize=CACHE_SIZE)
def search_image_by_text(
    positive_prompt="",
    negative_prompt="",
    positive_threshold=POSITIVE_THRESHOLD,
    negative_threshold=NEGATIVE_THRESHOLD,
):
    """
    使用文字搜图片
    :param positive_prompt: string, 正向提示词
    :param negative_prompt: string, 反向提示词
    :param positive_threshold: int/float, 正向阈值
    :param negative_threshold: int/float, 反向阈值
    :return: list[dict], 搜索结果列表
    """
    positive_feature = process_text(positive_prompt)
    negative_feature = process_text(negative_prompt)
    return search_image_by_feature(
        positive_feature, negative_feature, positive_threshold, negative_threshold
    )


@lru_cache(maxsize=CACHE_SIZE)
def search_image_by_image(img_id_or_path, threshold=IMAGE_THRESHOLD):
    """
    使用图片搜图片
    :param img_id_or_path: int/string, 图片ID 或 图片路径
    :param threshold: int/float, 搜索阈值
    :return: list[dict], 搜索结果列表
    """
    try:
        img_id = int(img_id_or_path)
    except ValueError as e:
        img_path = img_id_or_path
    if img_id:
        features = b""
        with SessionLocal() as session:
            features = crud.get_image_features_by_id(session, img_id)
        if not features:
            return []
        features = np.frombuffer(features, dtype=np.float32).reshape(1, -1)
    elif img_path:
        features = process_image(img_path)
    return search_image_by_feature(features, None, threshold)


def get_index_pairs(scores):
    """
    根据每一帧的余弦相似度计算素材片段
    :param scores: [<class 'numpy.nparray'>], 余弦相似度列表，里面每个元素的shape=(1, 1)
    :return: 返回连续的帧序号列表，如第2-5帧、第11-13帧都符合搜索内容，则返回[(2,5),(11,13)]
    """
    indexes = []
    for i in range(len(scores)):
        if scores[i]:
            indexes.append(i)
    result = []
    start_index = -1
    for i in range(len(indexes)):
        if start_index == -1:
            start_index = indexes[i]
        elif indexes[i] - indexes[i - 1] > 2:  # 允许中间空1帧
            result.append((start_index, indexes[i - 1]))
            start_index = indexes[i]
    if start_index != -1:
        result.append((start_index, indexes[-1]))
    return result


def get_video_range(start_index, end_index, scores, frame_times):
    """
    根据帧数范围，获取视频时长范围
    """
    # 间隔小于等于2倍FRAME_INTERVAL的算为同一个素材，同时开始时间和结束时间各延长0.5个FRAME_INTERVAL
    if start_index > 0:
        start_time = int((frame_times[start_index] + frame_times[start_index - 1]) / 2)
    else:
        start_time = frame_times[start_index]
    if end_index < len(scores) - 1:
        end_time = int((frame_times[end_index] + frame_times[end_index + 1]) / 2 + 0.5)
    else:
        end_time = frame_times[end_index]
    return start_time, end_time


def search_video_by_feature(
    positive_feature,
    negative_feature=None,
    positive_threshold=POSITIVE_THRESHOLD,
    negative_threshold=NEGATIVE_THRESHOLD,
):
    """
    通过特征搜索视频
    :param positive_feature: np.array, 正向特征向量
    :param negative_feature: np.array, 反向特征向量
    :param positive_threshold: int/float, 正向阈值
    :param negative_threshold: int/float, 反向阈值
    :return: list[dict], 搜索结果列表
    """
    t0 = time.time()
    scores_list = []
    data_list = []
    with SessionLocal() as session:
        for path in crud.get_video_paths(session):  # 逐个视频比对
            frame_times, features = crud.get_frame_times_features_by_path(session, path)
            features = np.frombuffer(b"".join(features), dtype=np.float32).reshape(
                len(features), -1
            )
            scores = match_batch(
                positive_feature,
                negative_feature,
                features,
                positive_threshold,
                negative_threshold,
            )
            index_pairs = get_index_pairs(scores)
            for start_index, end_index in index_pairs:
                score = max(scores[start_index : end_index + 1])
                start_time, end_time = get_video_range(
                    start_index, end_index, scores, frame_times
                )
                data_list.append((path, score, start_time, end_time))
                scores_list.append(score)
    softmax_scores = softmax(scores_list)
    return_list = [
        {
            "url": "api/get_video/%s" % base64.urlsafe_b64encode(path.encode()).decode()
            + "#t=%.1f,%.1f" % (start_time, end_time),
            "path": path,
            "score": float(score),
            "start_time": start_time,
            "end_time": end_time,
            "softmax_score": float(softmax_score),
        }
        for (path, score, start_time, end_time), softmax_score in zip(
            data_list, softmax_scores
        )
    ]
    logger.info("查询使用时间：%.2f" % (time.time() - t0))
    return_list = sorted(return_list, key=lambda x: x["score"], reverse=True)
    return return_list


@lru_cache(maxsize=CACHE_SIZE)
def search_video_by_text(
    positive_prompt="",
    negative_prompt="",
    positive_threshold=POSITIVE_THRESHOLD,
    negative_threshold=NEGATIVE_THRESHOLD,
):
    """
    使用文字搜视频
    :param positive_prompt: string, 正向提示词
    :param negative_prompt: string, 反向提示词
    :param positive_threshold: int/float, 正向阈值
    :param negative_threshold: int/float, 反向阈值
    :return: list[dict], 搜索结果列表
    """
    positive_feature = process_text(positive_prompt)
    negative_feature = process_text(negative_prompt)
    return search_video_by_feature(
        positive_feature, negative_feature, positive_threshold, negative_threshold
    )


@lru_cache(maxsize=CACHE_SIZE)
def search_video_by_image(img_id_or_path, threshold=IMAGE_THRESHOLD):
    """
    使用图片搜视频
    :param img_id_or_path: int/string, 图片ID 或 图片路径
    :param threshold: int/float, 搜索阈值
    :return: list[dict], 搜索结果列表
    """
    try:
        img_id = int(img_id_or_path)
    except ValueError as e:
        img_path = img_id_or_path
    if img_id:
        feature = b""
        with SessionLocal() as session:
            feature = crud.get_image_features_by_id(session, img_id)
        if not feature:
            return []
        feature = np.frombuffer(feature, dtype=np.float32).reshape(1, -1)
    elif img_path:
        feature = process_image(img_path)
    return search_video_by_feature(feature, None, threshold)


@lru_cache(maxsize=CACHE_SIZE)
def search_image_file(path: str):
    """
    通过路径搜索图片
    :param path: 路径
    :return:
    """
    file_list = []
    with SessionLocal() as session:
        id_paths = crud.search_image_by_path(session, path)
        file_list = [
            {
                "url": "api/get_image/%d" % id,
                "path": path,
            }
            for id, path in id_paths
        ]
        return file_list


@lru_cache(maxsize=CACHE_SIZE)
def search_video_file(path: str):
    """
    通过路径搜索视频
    :param path: 路径
    :return:
    """
    with SessionLocal() as session:
        paths = crud.search_video_by_path(session, path)
        file_list = [
            {
                "url": "api/get_video/%s"
                % base64.urlsafe_b64encode(path.encode()).decode(),
                "path": path,
            }
            for path, in paths
        ]  # 这里的,不可以省，用于解包tuple
        return file_list