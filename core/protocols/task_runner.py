"""
RS-01A — TaskDrivenRunner (最小运行链)

使用注入的 PerceptionTool 运行任务。
"""

from core.schemas.contracts.task import InferenceTask, TaskSpec, RunContext
from core.schemas.contracts.perception import PerceptionResult
from core.protocols.perception_tool import PerceptionTool
from tools.sar_temporal_change_tool import SarTemporalChangeTool


class TaskDrivenRunner:
    """
    任务驱动 Runner。
    通过 PerceptionTool 执行 InferenceTask，输出 PerceptionResult。
    SarTemporalChangeTool 为默认工具。
    """

    def __init__(self, tool: PerceptionTool | None = None):
        self._tool = tool or SarTemporalChangeTool()

    def run(self, task: InferenceTask, spec: TaskSpec, context: RunContext) -> PerceptionResult:
        """运行一个任务，返回 PerceptionResult。"""
        return self._tool.run(task, spec, context)
