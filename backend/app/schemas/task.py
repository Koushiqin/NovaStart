from datetime import date
from typing import Literal

from pydantic import BaseModel, field_validator

StepSource = Literal["llm", "mock", "fallback"]


def _clean_required_text(value: str, *, max_length: int, label: str) -> str:
    """去首尾空白后做长度校验；空值 / 超长统一走 422。"""
    cleaned = value.strip()
    if not cleaned or len(cleaned) > max_length:
        raise ValueError(f"{label}需为 1–{max_length} 字")
    return cleaned


class TaskCreate(BaseModel):
    raw_text: str

    @field_validator("raw_text")
    @classmethod
    def _validate_raw_text(cls, value: str) -> str:
        return _clean_required_text(value, max_length=200, label="任务内容")


class TaskUpdate(BaseModel):
    """只更新当前采用版；origin_* / analyzed_text / split_source 由 analyze 维护。"""

    raw_text: str | None = None
    starter_step: str | None = None
    steps: list[str] | None = None

    @field_validator("raw_text")
    @classmethod
    def _validate_raw_text(cls, value: str | None) -> str | None:
        if value is None:
            return None
        return _clean_required_text(value, max_length=200, label="任务内容")

    @field_validator("starter_step")
    @classmethod
    def _validate_starter_step(cls, value: str | None) -> str | None:
        if value is None:
            return None
        return _clean_required_text(value, max_length=200, label="启动步骤")

    @field_validator("steps")
    @classmethod
    def _validate_steps(cls, value: list[str] | None) -> list[str] | None:
        if value is None:
            return None
        if len(value) > 3:
            raise ValueError("后续步骤最多 3 条")
        return [_clean_required_text(step, max_length=200, label="步骤") for step in value]


class TaskState(BaseModel):
    """今日任务状态：analyzed / split_stale / locked 均为派生值，不落列。"""

    id: int
    raw_text: str
    starter_step: str
    steps: list[str]
    origin_starter_step: str | None
    origin_steps: list[str] | None
    analyzed: bool
    split_stale: bool
    locked: bool
    source: StepSource | None


class TaskResponse(BaseModel):
    task: TaskState
    server_time: str


class AnalyzeResult(BaseModel):
    starter_step: str
    steps: list[str]
    source: StepSource
    server_time: str


class CarryOver(BaseModel):
    raw_text: str
    date: date


class TodayResponse(BaseModel):
    task: TaskState | None
    carry_over: CarryOver | None
    server_time: str
