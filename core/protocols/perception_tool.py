"""
RS-01A — PerceptionTool Protocol

所有感知工具的统一接口。可替换、可测试。
"""

from typing import Protocol, runtime_checkable
from core.schemas.contracts.task import InferenceTask, TaskSpec, RunContext
from core.schemas.contracts.perception import PerceptionResult


@runtime_checkable
class PerceptionTool(Protocol):
    """感知工具接口。输入任务定义 + 规则 + 配置，输出 PerceptionResult。"""

    def run(self, task: InferenceTask, spec: TaskSpec, context: RunContext) -> PerceptionResult:
        ...
