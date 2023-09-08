import datetime
import logging
import os

from sqlalchemy.orm import Session

from database import Image, Video

logger = logging.getLogger(__name__)


def get_image(session: Session):
    return session.query(Image).first()


def get_images(session: Session):
    return session.query(Image)


def get_image_count(session: Session):
    return session.query(Image).count()


def delete_image_if_outdated(
    session: Session, path: str, modify_time: datetime.datetime
) -> bool:
    """
    判断图片是否修改，若修改则删除
    :param session: Session, 数据库 session
    :param path: str, 图片路径
    :param modify_time: datetime, 文件修改时间
    :return: bool, 若文件未修改返回 True
    """
    record = session.query(Image).filter_by(path=path).first()
    if not record:
        logger.info(f"新增文件：{path}")
        return False
    modify_time = os.path.getmtime(path)
    modify_time = datetime.datetime.fromtimestamp(modify_time)
    if record and record.modify_time == modify_time:
        # 未修改
        logger.debug(f"文件无变更，跳过：{path}")
        return True
    logger.info(f"文件有更新：{path}")
    session.delete(record)
    session.commit()
    return False


def delete_video_if_outdated(
    session: Session, path: str, modify_time: datetime.datetime
) -> bool:
    """
    判断视频是否修改，若修改则删除
    :param session: Session, 数据库 session
    :param path: str, 视频路径
    :param modify_time: datetime, 文件修改时间
    :return: bool, 若文件未修改返回 True
    """
    record = session.query(Video).filter_by(path=path).first()
    if not record:
        logger.info(f"新增文件：{path}")
        return False
    if record and record.modify_time == modify_time:
        # 未修改
        logger.debug(f"文件无变更，跳过：{path}")
        return True
    logger.info(f"文件有更新：{path}")
    session.query(Video).filter_by(path=path).delete()
    session.commit()
    return False


def get_video_paths(session: Session):
    return session.query(Video.path).distinct()


def get_video_count(session: Session):
    return session.query(Video.path).distinct().count()


def get_video_frame_count(session: Session):
    return session.query(Video).count()


def delete_video_by_path(session: Session, path: str):
    session.query(Video).filter_by(path=path).delete()
    session.commit()


def add_image(session: Session, image: Image):
    session.add(image)
    session.commit()


def add_video(session: Session, video_list: list[Video]):
    # 使用 bulk_save_objects 一次性提交
    session.bulk_save_objects(video_list)
    session.commit()


def delete_record_if_not_exist(session: Session, assets: set):
    """
    删除不存在于 assets 集合中的图片 / 视频记录
    """
    for file in session.query(Image):
        if file.path not in assets:
            logger.info(f"文件已删除：{file.path}")
            session.delete(file)
    for path in session.query(Video.path).distinct():
        path = path[0]
        if path not in assets:
            logger.info(f"文件已删除：{path}")
            session.query(Video).filter_by(path=path).delete()
    session.commit()
