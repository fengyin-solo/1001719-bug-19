"""压力容器业务规则：状态流转、字段校验与筛选口径都收在这里。"""
from __future__ import annotations

from copy import deepcopy
from typing import Any

from app.store import store

MODULE = "vessel"
# 必填项：缺失时整条不允许入库，已有的原值原样保留
REQUIRED_FIELDS = ["容器编号", "容器名称", "设计压力"]
# 登记页可填的全部业务字段，保存时整条落在同一份记录上；
# 列表、详情、导出、运营概览都从这份记录读，不再各取一份。
OPTIONAL_FIELDS = ["容积规格", "介质类别", "使用场所", "下次检验日"]
ALL_FIELDS = REQUIRED_FIELDS + OPTIONAL_FIELDS
STATUS_LABEL = "容器状态"
STATUS_ORDER = ["待投用", "在用运行", "停用待检", "已报废"]
ACTION_RULES = {"办理投用": "在用运行", "安排检验": "停用待检", "报废容器": "已报废"}
NEGATIVE_ACTIONS = []


class VesselService:
    def list_entries(
        self,
        *,
        keyword: str | None = None,
        status: str | None = None,
        page: int = 1,
        size: int = 20,
    ) -> tuple[list[dict[str, Any]], int]:
        rows = store.rows(MODULE)
        if keyword:
            rows = [row for row in rows if keyword in str(row.get("容器编号", ""))]
        if status:
            rows = [row for row in rows if _row_status(row) == status]
        total = len(rows)
        start = max(page - 1, 0) * size
        return rows[start:start + size], total

    def get_entry(self, entry_id: int) -> dict[str, Any] | None:
        return store.find(MODULE, entry_id)

    def create_entry(self, values: dict[str, Any]) -> tuple[dict[str, Any] | None, str]:
        """登记一台压力容器。

        成功时整份字段（含容积规格等选填项）落到同一条记录；必填缺失或容器编号
        已存在时不写库，已有记录原样保留，返回 (None, 原因说明)。
        """
        normalized = {
            field: _clean(values.get(field)) for field in ALL_FIELDS
        }
        missing = [field for field in REQUIRED_FIELDS if not normalized[field]]
        if missing:
            return None, f"缺少必填字段：{'、'.join(missing)}，本次登记未保存，请补齐后重试"

        code = normalized["容器编号"]
        rows = store.rows(MODULE)
        duplicate = next(
            (row for row in rows if str(row.get("容器编号", "")).strip() == code),
            None,
        )
        if duplicate is not None:
            # 重复保存同一台只留一条：不覆盖、不新增，原值保留
            return None, (
                f"容器编号 {code} 已登记（记录 {duplicate.get('id')}），"
                "同一台容器只保留一条记录，本次提交未保存，原有信息未改动"
            )

        entry: dict[str, Any] = {"id": max((int(row.get("id", 0)) for row in rows), default=0) + 1}
        for field in ALL_FIELDS:
            entry[field] = normalized[field]
        entry["status"] = STATUS_ORDER[0]
        entry[STATUS_LABEL] = STATUS_ORDER[0]
        entry["pending"] = True
        entry["abnormal"] = False
        rows.append(entry)
        # 返回深拷贝，避免调用方拿到的"详情"与仓库里的记录被当成两份各自改动
        return deepcopy(entry), ""

    def run_action(self, entry_id: int, action: str) -> tuple[dict[str, Any] | None, str]:
        entry = store.find(MODULE, entry_id)
        if entry is None:
            return None, f"压力容器 {entry_id} 不存在或已归档"
        if action not in ACTION_RULES:
            return None, f"动作「{action}」不属于压力容器可执行范围"
        target = ACTION_RULES[action]
        if target not in STATUS_ORDER:
            return None, f"目标状态「{target}」不在允许的状态序列里"
        entry["status"] = target
        entry[STATUS_LABEL] = target
        entry["pending"] = target != STATUS_ORDER[-1]
        entry["abnormal"] = action in NEGATIVE_ACTIONS
        return deepcopy(entry), f"压力容器已{action}"


def _clean(value: Any) -> str:
    """把空串、纯空白统一归一为 ''，非字符串按原样转字符串后去首尾空白。"""
    if value is None:
        return ""
    text = str(value).strip()
    return text


def _row_status(row: dict[str, Any]) -> str:
    """统一状态读取口径：新记录的 status 与「容器状态」始终同步；

    历史数据里只有 status 或只有「容器状态」的，以 status 为准回退，
    读取口径统一但不改写历史行本身。
    """
    status = str(row.get("status") or "").strip()
    if status:
        return status
    return str(row.get(STATUS_LABEL) or "").strip()
