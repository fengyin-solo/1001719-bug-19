"""压力容器业务规则：状态流转、字段校验与筛选口径都收在这里。"""
from __future__ import annotations

from datetime import date
from typing import Any

from app.store import store

MODULE = "vessel"
# 登记时整条落库的字段：必填项与设计压力、容积规格等非必填项都写进同一条记录。
ALL_FIELDS = ["容器编号", "容器名称", "设计压力", "容积规格", "介质类别", "使用场所", "下次检验日"]
REQUIRED_FIELDS = ["容器编号", "容器名称", "设计压力"]
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
            rows = [row for row in rows if row.get("status") == status]
        total = len(rows)
        start = max(page - 1, 0) * size
        return rows[start:start + size], total

    def get_entry(self, entry_id: int) -> dict[str, Any] | None:
        return store.find(MODULE, entry_id)

    def create_entry(self, values: dict[str, Any]) -> tuple[dict[str, Any] | None, list[str]]:
        """登记或复登记一条压力容器。

        以容器编号为业务键：已存在同编号记录时更新这一条（重复保存只留一条），
        不存在时新建。必填项缺失时返回缺失字段与可读理由，且不改动已有记录，
        把原来的值留住；校验通过后整条字段写进同一条记录。
        """
        missing = [field for field in REQUIRED_FIELDS if not str(values.get(field) or "").strip()]
        if missing:
            return None, missing

        code = str(values.get("容器编号") or "").strip()
        existing = next(
            (row for row in store.rows(MODULE) if str(row.get("容器编号", "")) == code),
            None,
        )
        data = {field: values.get(field) for field in ALL_FIELDS}
        if existing is not None:
            # 复登记：只更新业务字段，保留原记录的工作流状态与 id。
            existing.update(data)
            existing["容器状态"] = existing.get("status") or existing.get("容器状态")
            return existing, []

        rows = store.rows(MODULE)
        entry = {"id": max((int(row.get("id", 0)) for row in rows), default=0) + 1}
        entry.update(data)
        entry["status"] = STATUS_ORDER[0]
        entry["容器状态"] = STATUS_ORDER[0]
        entry["pending"] = True
        entry["abnormal"] = False
        rows.append(entry)
        return entry, []

    def stats(self) -> dict[str, int]:
        """在册台数与各状态台数，供运营概览与页面统计卡片重算。"""
        rows = store.rows(MODULE)
        today = date.today().isoformat()
        return {
            "在册台数": len(rows),
            "在用容器": sum(1 for row in rows if row.get("status") == "在用运行"),
            "停用待检": sum(1 for row in rows if row.get("status") == "停用待检"),
            "超期未检": sum(
                1
                for row in rows
                if row.get("status") != "已报废" and str(row.get("下次检验日") or "") < today
            ),
        }

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
        entry["pending"] = target != STATUS_ORDER[-1]
        entry["abnormal"] = action in NEGATIVE_ACTIONS
        return entry, f"压力容器已{action}"
