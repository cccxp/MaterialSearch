import logging
import pickle
import sqlite3

import config

NEWEST_VERSION = 2
logger = logging.getLogger(__name__)


def update_database(version: int):
    """
    升级到版本version。 确保当前数据库版本仅低一级
    :param version: int, 要升级到的版本号
    """
    logger.info(f"正在升级为: {version}")
    match version:
        case 2:
            def is_optimized(features):
                try:
                    pickle.loads(features)
                    return False
                except Exception as e:
                    return True

            # 首先尝试优化数据库
            db = sqlite3.connect(config.SQLALCHEMY_DATABASE_URL)
            cursor = db.cursor()
            (features,) = cursor.execute(
                "select features from image limit 1;"
            ).fetchone()
            if not is_optimized(features):
                query = cursor.execute("select id, features from image;")
                for i, (id, features) in enumerate(query):
                    if not features:
                        cursor.execute("delete from image where id = ?;", (id,))
                        continue
                    features = pickle.loads(features).tobytes()
                    cursor.execute(
                        "update image set features = ? where id = ?;", (features, id)
                    )
                    if i % 1000 == 0:
                        db.commit()
                query = cursor.execute("select id, features from video;")
                for i, (id, features) in enumerate(query):
                    if not features:
                        cursor.execute("delete from video where id = ?;", (id,))
                        continue
                    features = pickle.loads(features).tobytes()
                    cursor.execute(
                        "update video set features = ? where id = ?;", (features, id)
                    )
                    if i % 1000 == 0:
                        db.commit()
                db.commit()
            logger.info("features 列优化完成")
            cursor.execute(
                """
                create table version(
                    database_version int,
                );
            """
            )
            cursor.execute("insert into database_version values (?);", (version,))
            db.commit()
            logger.info("version 表创建完成")
        case 3:
            # TODO: 向数据库添加一些元数据列，以便更详细的筛选？
            ... 
    logger.info(f"成功升级至：{version}")

def optimize_database():
    """
    优化最新版的数据库
    TODO: 删除数据库中的无效项目
    """
    logger.info("开始优化数据库")
    ...
    logger.info("优化完成")


def main():
    logger.info(f"连接至数据库： {config.SQLALCHEMY_DATABASE_URL}")
    try:
        db = sqlite3.connect(config.SQLALCHEMY_DATABASE_URL, timeout=1)
        cursor = db.cursor()
        cursor.execute("select id from image limit 1;")
    except sqlite3.OperationalError:
        logger.info("数据表未创建，无需更新。")
        exit(0)
    logger.info("连接成功。")
    logger.info("检查数据库版本：")
    version = 0
    try:
        (version,) = cursor.execute("select version from version;").fetchone()
        db.commit()  # 通过 version 表获取版本
    except sqlite3.OperationalError as e:
        # 初始版本
        version = 1
    cursor.close()
    db.close()
    if NEWEST_VERSION <= version:
        logger.info(f"当前数据库版本：{version}, 为最新版本。")
        optimize_database()
        return
    while NEWEST_VERSION > version:
        # 滚动升级至最新版本
        logger.info(f"当前数据库版本：{version}")
        logger.info(f"最新版本：{NEWEST_VERSION}")
        version += 1
        update_database(version)
    logger.info("升级成功！")
    optimize_database()


if __name__ == "__main__":
    main()
