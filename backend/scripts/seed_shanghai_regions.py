"""一次性 seed 脚本：导入上海市完整三级行政区域（市 / 区 / 街镇）。

数据基于公开行政区划整理（1 市 + 16 区 + 约 215 个街道/镇/乡）。
行政区划时有撤并调整，街镇级可能与最新官方区划有个别出入——导入后
请在前端「区域管理」页核对、增删。

幂等：若数据库已存在 name='上海市' 且 level='city' 的区域，整体跳过，
不会重复导入。

用法
----
    cd backend
    SECRET_KEY=... DATABASE_URL=... python -m scripts.seed_shanghai_regions

退出码
------
  0  成功（或已存在跳过）
  2  数据库错误
"""

from __future__ import annotations

import logging
import os
import sys
import uuid

from sqlalchemy import select
from sqlalchemy.exc import SQLAlchemyError

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app import models  # noqa: E402,F401  触发 Base.metadata 注册
from app.core.database import SyncSessionLocal  # noqa: E402
from app.models import Region  # noqa: E402

logger = logging.getLogger(__name__)
logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")

CITY_NAME = "上海市"

# 上海市 16 区，每区下街道/镇/乡。
SHANGHAI: dict[str, list[str]] = {
    "黄浦区": [
        "南京东路街道", "外滩街道", "半淞园路街道", "小东门街道",
        "豫园街道", "老西门街道", "五里桥街道", "打浦桥街道",
        "淮海中路街道", "瑞金二路街道",
    ],
    "徐汇区": [
        "徐家汇街道", "天平路街道", "湖南路街道", "斜土路街道",
        "枫林路街道", "长桥街道", "田林街道", "虹梅路街道",
        "康健新村街道", "凌云路街道", "龙华街道", "漕河泾街道",
        "华泾镇",
    ],
    "长宁区": [
        "江苏路街道", "华阳路街道", "新华路街道", "周家桥街道",
        "天山路街道", "仙霞新村街道", "虹桥街道", "程家桥街道",
        "北新泾街道", "新泾镇",
    ],
    "静安区": [
        "江宁路街道", "石门二路街道", "南京西路街道", "静安寺街道",
        "曹家渡街道", "天目西路街道", "北站街道", "宝山路街道",
        "共和新路街道", "大宁路街道", "芷江西路街道", "彭浦新村街道",
        "临汾路街道", "彭浦镇",
    ],
    "普陀区": [
        "曹杨新村街道", "长风新村街道", "长寿路街道", "甘泉路街道",
        "石泉路街道", "宜川路街道", "万里街道", "真如镇街道",
        "长征镇", "桃浦镇",
    ],
    "虹口区": [
        "欧阳路街道", "曲阳路街道", "广中路街道", "嘉兴路街道",
        "凉城新村街道", "四川北路街道", "提篮桥街道", "江湾镇街道",
    ],
    "杨浦区": [
        "定海路街道", "平凉路街道", "江浦路街道", "四平路街道",
        "控江路街道", "长白新村街道", "延吉新村街道", "殷行街道",
        "大桥街道", "新江湾城街道", "五角场街道", "长海路街道",
    ],
    "闵行区": [
        "江川路街道", "古美路街道", "新虹街道", "浦锦街道",
        "莘庄镇", "七宝镇", "颛桥镇", "华漕镇", "梅陇镇",
        "吴泾镇", "马桥镇", "浦江镇", "虹桥镇",
    ],
    "宝山区": [
        "友谊路街道", "吴淞街道", "张庙街道", "罗店镇", "大场镇",
        "杨行镇", "月浦镇", "罗泾镇", "顾村镇", "高境镇",
        "庙行镇", "淞南镇",
    ],
    "嘉定区": [
        "新成路街道", "真新街道", "嘉定镇街道", "南翔镇", "安亭镇",
        "马陆镇", "徐行镇", "华亭镇", "外冈镇", "江桥镇",
    ],
    "浦东新区": [
        "潍坊新村街道", "陆家嘴街道", "周家渡街道", "塘桥街道",
        "上钢新村街道", "南码头路街道", "沪东新村街道", "金杨新村街道",
        "洋泾街道", "浦兴路街道", "东明路街道", "花木街道",
        "川沙新镇", "高桥镇", "北蔡镇", "合庆镇", "唐镇", "曹路镇",
        "金桥镇", "高行镇", "张江镇", "三林镇", "惠南镇", "周浦镇",
        "新场镇", "大团镇", "康桥镇", "航头镇", "祝桥镇", "泥城镇",
        "宣桥镇", "书院镇", "万祥镇", "老港镇", "南汇新城镇", "高东镇",
    ],
    "金山区": [
        "石化街道", "朱泾镇", "枫泾镇", "张堰镇", "亭林镇",
        "吕巷镇", "廊下镇", "金山卫镇", "漕泾镇", "山阳镇",
    ],
    "松江区": [
        "岳阳街道", "永丰街道", "方松街道", "中山街道",
        "广富林街道", "九里亭街道", "泗泾镇", "佘山镇", "车墩镇",
        "新桥镇", "洞泾镇", "九亭镇", "泖港镇", "石湖荡镇",
        "新浜镇", "叶榭镇", "小昆山镇",
    ],
    "青浦区": [
        "夏阳街道", "盈浦街道", "香花桥街道", "朱家角镇", "练塘镇",
        "金泽镇", "赵巷镇", "徐泾镇", "华新镇", "白鹤镇", "重固镇",
    ],
    "奉贤区": [
        "西渡街道", "奉浦街道", "金海街道", "南桥镇", "奉城镇",
        "四团镇", "青村镇", "柘林镇", "庄行镇", "金汇镇", "海湾镇",
    ],
    "崇明区": [
        "城桥镇", "堡镇", "新河镇", "庙镇", "竖新镇", "向化镇",
        "三星镇", "港沿镇", "中兴镇", "陈家镇", "绿华镇", "港西镇",
        "建设镇", "新海镇", "东平镇", "长兴镇", "新村乡", "横沙乡",
    ],
}


def _new_id() -> str:
    return str(uuid.uuid4())


def main() -> int:
    try:
        with SyncSessionLocal() as db:
            # 幂等检查
            existing = db.execute(
                select(Region).where(
                    Region.name == CITY_NAME, Region.level == "city"
                )
            ).scalar_one_or_none()
            if existing is not None:
                logger.info("「%s」已存在 (id=%s)，跳过导入", CITY_NAME, existing.id)
                return 0

            city_id = _new_id()
            db.add(
                Region(
                    id=city_id,
                    name=CITY_NAME,
                    level="city",
                    parent_id=None,
                    full_path=CITY_NAME,
                )
            )

            district_count = 0
            town_count = 0
            for district_name, towns in SHANGHAI.items():
                district_id = _new_id()
                db.add(
                    Region(
                        id=district_id,
                        name=district_name,
                        level="district",
                        parent_id=city_id,
                        full_path=f"{CITY_NAME}/{district_name}",
                    )
                )
                district_count += 1
                for town_name in towns:
                    db.add(
                        Region(
                            id=_new_id(),
                            name=town_name,
                            level="town",
                            parent_id=district_id,
                            full_path=f"{CITY_NAME}/{district_name}/{town_name}",
                        )
                    )
                    town_count += 1

            db.commit()
            logger.info(
                "OK: 已导入 %s — %d 个区, %d 个街镇",
                CITY_NAME,
                district_count,
                town_count,
            )
            return 0
    except SQLAlchemyError as exc:
        logger.error("数据库错误: %s", exc)
        return 2


if __name__ == "__main__":
    sys.exit(main())
