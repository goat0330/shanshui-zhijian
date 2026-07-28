"""
RS-01A.1 — TaskDrivenRunner (注入模式)

不导入具体工具。所有工具通过构造器注入。
"""

from core.schemas.contracts.task import InferenceTask, TaskSpec, RunContext
from core.schemas.contracts.perception import PerceptionResult
from core.protocols.perception_tool import PerceptionTool


class TaskDrivenRunner:
    """任务驱动 Runner。工具通过构造器注入，不绑定具体实现。"""

    def __init__(self, tool: PerceptionTool):
        self._tool = tool

    def run(self, task: InferenceTask, spec: TaskSpec, context: RunContext) -> PerceptionResult:
        return self._tool.run(task, spec, context)
