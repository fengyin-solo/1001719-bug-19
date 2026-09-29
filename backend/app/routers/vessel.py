"""压力容器接口：维护压力容器，覆盖办理投用、安排检验、报废容器等动作。"""
from __future__ import annotations

from datetime import date
from typing import Any

from fastapi import APIRouter, HTTPException, Query

from app.schemas import ActionResult, EntryPayload, PageResult
from app.services.vessel import MODULE, STATUS_ORDER, VesselService
from app.store import store

router = APIRouter(prefix="/api/vessel", tags=["压力容器"])

service = VesselService()

LIST_FIELDS = ["容器编号", "容器名称", "设计压力", "容积规格", "介质类别", "使用场所", "下次检验日", "容器状态"]
STATUSES = ["待投用", "在用运行", "停用待检", "已报废"]


def _to_view(row: dict[str, Any]) -> dict[str, Any]:
    """列表、详情、导出共用的读取口径：始终从仓库里同一条记录投影。

    新登记的记录 status 与「容器状态」同步落库；历史数据可能只在 status 上有
    合法状态，这里仅在返回副本上补齐显示，不改写仓库里的历史行。
    """
    view = dict(row)
    if view.get("容器状态") not in STATUS_ORDER and view.get("status") in STATUS_ORDER:
        view["容器状态"] = view["status"]
    return view


@router.get("", response_model=PageResult[dict])
def list_entries(
    keyword: str | None = Query(default=None, description="按容器编号检索"),
    status: str | None = Query(default=None, description="待投用、在用运行、停用待检、已报废"),
    page: int = 1,
    size: int = 20,
) -> PageResult[dict]:
    """按容器编号与状态过滤压力容器列表；没有数据时返回空页，不报错。"""
    if size > 200:
        raise HTTPException(status_code=400, detail="每页最多 200 条，请缩小分页范围")
    items, total = service.list_entries(keyword=keyword, status=status, page=page, size=size)
    return PageResult(items=[_to_view(item) for item in items], total=total, page=page, size=size)


@router.get("/stats")
def entry_stats() -> dict[str, int]:
    """压力容器在册口径统计：在全量记录上实时计算，登记/状态流转后立即反映。"""
    today = date.today().isoformat()
    rows = store.rows(MODULE)
    in_register = 0
    in_use = 0
    idle_inspect = 0
    overdue = 0
    for row in rows:
        current = str(row.get("status") or "").strip()
        if current == "已报废":
            continue
        in_register += 1
        if current == "在用运行":
            in_use += 1
        if current == "停用待检":
            idle_inspect += 1
        next_check = str(row.get("下次检验日") or "").strip()
        if len(next_check) == 10 and next_check < today:
            overdue += 1
    return {"在册台数": in_register, "在用容器": in_use, "停用待检": idle_inspect, "超期未检": overdue}


@router.get("/export")
def export_entries() -> dict[str, Any]:
    """导出压力容器清单：返回当前过滤条件下的全量数据，与列表同一读取口径。"""
    items, total = service.list_entries(page=1, size=10000)
    return {"module": "vessel", "total": total, "items": [_to_view(item) for item in items]}


@router.get("/{entry_id}", response_model=dict)
def get_entry(entry_id: int) -> dict:
    """读取单条压力容器明细；不存在时给出可读的错误说明。"""
    entry = service.get_entry(entry_id)
    if entry is None:
        raise HTTPException(status_code=404, detail=f"压力容器 {entry_id} 不存在或已归档")
    return _to_view(entry)


@router.post("", response_model=ActionResult)
def create_entry(payload: EntryPayload) -> ActionResult:
    """登记一条压力容器，整份字段落库；缺字段或重复登记时不写库并说明原因。"""
    entry, reason = service.create_entry(payload.values)
    if entry is None:
        return ActionResult(ok=False, message=reason)
    return ActionResult(ok=True, message="压力容器已登记，全部字段已保存", entry=_to_view(entry))


@router.post("/{entry_id}/actions", response_model=ActionResult)
def run_action(entry_id: int, payload: EntryPayload) -> ActionResult:
    """对单条压力容器执行办理投用、安排检验、报废容器；不允许的动作会被拦下并说明原因。"""
    action = str(payload.values.get("action") or "").strip()
    entry, message = service.run_action(entry_id, action)
    if entry is None:
        return ActionResult(ok=False, message=message)
    return ActionResult(ok=True, message=message, entry=_to_view(entry))
