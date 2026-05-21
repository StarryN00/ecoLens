"""行政区域管理接口（T1 多级目录架构）。

市 / 区 / 街镇 三级树。巡检任务挂在 town（街镇）级叶子节点上。

- GET    /api/v1/regions/tree                  完整三级树（登录可读）
- GET    /api/v1/regions/?level=&parent_id=    分层查询（Cascader 动态加载用）
- POST   /api/v1/regions/                      创建（admin）
- PUT    /api/v1/regions/{id}                  改名（admin，级联更新后代 full_path）
- DELETE /api/v1/regions/{id}                  删除（admin，仅无子区域且无任务时）
"""

from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.security import get_current_user
from app.models import InspectionTask, Region, User

router = APIRouter(prefix="/api/v1/regions", tags=["regions"])

# 三级，以及每一级的合法父级
LEVELS = ("city", "district", "town")
_PARENT_LEVEL = {"district": "city", "town": "district"}


def _check_admin(current_user: User = Depends(get_current_user)) -> User:
    """写操作（建/改/删区域）仅管理员。"""
    if not current_user.is_admin:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN, detail="需要管理员权限"
        )
    return current_user


class CreateRegionRequest(BaseModel):
    name: str = Field(..., min_length=1, max_length=100)
    level: str  # city / district / town
    parent_id: Optional[str] = None


class UpdateRegionRequest(BaseModel):
    name: str = Field(..., min_length=1, max_length=100)


def _region_dict(r: Region) -> dict:
    return {
        "id": r.id,
        "name": r.name,
        "level": r.level,
        "parent_id": r.parent_id,
        "full_path": r.full_path,
    }


async def _rebuild_subtree_paths(db: AsyncSession, root: Region) -> None:
    """root.full_path 已更新后，递归重算其所有后代的 full_path。"""
    res = await db.execute(
        select(Region).where(Region.parent_id == root.id)
    )
    for child in res.scalars().all():
        child.full_path = f"{root.full_path}/{child.name}"
        db.add(child)
        await _rebuild_subtree_paths(db, child)


@router.get("/tree")
async def get_region_tree(
    _user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """返回完整三级树：[{...city, children:[{...district, children:[town]}]}]。"""
    res = await db.execute(select(Region))
    regions = res.scalars().all()

    by_id = {r.id: {**_region_dict(r), "children": []} for r in regions}
    roots = []
    for r in regions:
        node = by_id[r.id]
        if r.parent_id and r.parent_id in by_id:
            by_id[r.parent_id]["children"].append(node)
        else:
            roots.append(node)

    # 各层按名称排序，保证前端 Cascader 顺序稳定
    def _sort(nodes):
        nodes.sort(key=lambda n: n["name"])
        for n in nodes:
            _sort(n["children"])

    _sort(roots)
    return {"items": roots}


@router.get("/")
async def list_regions(
    level: Optional[str] = None,
    parent_id: Optional[str] = None,
    _user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """按 level / parent_id 过滤查询区域（扁平列表）。"""
    query = select(Region)
    if level:
        query = query.where(Region.level == level)
    if parent_id:
        query = query.where(Region.parent_id == parent_id)
    res = await db.execute(query.order_by(Region.name))
    return {"items": [_region_dict(r) for r in res.scalars().all()]}


@router.post("/", status_code=status.HTTP_201_CREATED)
async def create_region(
    payload: CreateRegionRequest,
    _admin: User = Depends(_check_admin),
    db: AsyncSession = Depends(get_db),
):
    """创建区域。强校验三级层级关系：
    - city 不能有 parent_id
    - district 的 parent 必须是 city；town 的 parent 必须是 district
    """
    level = payload.level
    if level not in LEVELS:
        raise HTTPException(
            status_code=400, detail="level 必须是 city / district / town 之一"
        )

    parent: Optional[Region] = None
    if level == "city":
        if payload.parent_id:
            raise HTTPException(status_code=400, detail="city（市）不能有父区域")
    else:
        if not payload.parent_id:
            raise HTTPException(
                status_code=400, detail=f"{level} 必须指定 parent_id"
            )
        pres = await db.execute(
            select(Region).where(Region.id == payload.parent_id)
        )
        parent = pres.scalar_one_or_none()
        if parent is None:
            raise HTTPException(status_code=404, detail="父区域不存在")
        if parent.level != _PARENT_LEVEL[level]:
            raise HTTPException(
                status_code=400,
                detail=f"{level} 的父区域必须是 {_PARENT_LEVEL[level]} 级",
            )

    full_path = (
        payload.name if parent is None else f"{parent.full_path}/{payload.name}"
    )
    region = Region(
        name=payload.name,
        level=level,
        parent_id=payload.parent_id,
        full_path=full_path,
    )
    db.add(region)
    await db.commit()
    await db.refresh(region)
    return _region_dict(region)


@router.put("/{region_id}")
async def update_region(
    region_id: str,
    payload: UpdateRegionRequest,
    _admin: User = Depends(_check_admin),
    db: AsyncSession = Depends(get_db),
):
    """重命名区域，并级联刷新自身与所有后代的 full_path。"""
    res = await db.execute(select(Region).where(Region.id == region_id))
    region = res.scalar_one_or_none()
    if region is None:
        raise HTTPException(status_code=404, detail="区域不存在")

    region.name = payload.name
    # 重算自身 full_path
    parent_path = ""
    if region.parent_id:
        pres = await db.execute(
            select(Region).where(Region.id == region.parent_id)
        )
        parent = pres.scalar_one_or_none()
        parent_path = parent.full_path if parent else ""
    region.full_path = (
        payload.name if not parent_path else f"{parent_path}/{payload.name}"
    )
    db.add(region)
    # 级联刷新后代
    await _rebuild_subtree_paths(db, region)
    await db.commit()
    await db.refresh(region)
    return _region_dict(region)


@router.delete("/{region_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_region(
    region_id: str,
    _admin: User = Depends(_check_admin),
    db: AsyncSession = Depends(get_db),
):
    """删除区域。仅当该区域下既无子区域、也无巡检任务时允许。"""
    res = await db.execute(select(Region).where(Region.id == region_id))
    region = res.scalar_one_or_none()
    if region is None:
        raise HTTPException(status_code=404, detail="区域不存在")

    child_count = await db.execute(
        select(func.count(Region.id)).where(Region.parent_id == region_id)
    )
    if child_count.scalar_one() > 0:
        raise HTTPException(
            status_code=400, detail="该区域下还有子区域，不能删除"
        )

    task_count = await db.execute(
        select(func.count(InspectionTask.id)).where(
            InspectionTask.region_id == region_id
        )
    )
    if task_count.scalar_one() > 0:
        raise HTTPException(
            status_code=400, detail="该区域下还有巡检任务，不能删除"
        )

    await db.delete(region)
    await db.commit()
