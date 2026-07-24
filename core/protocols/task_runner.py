"""
RS-00 — TaskDrivenRunner

通过兼容包装调用现有 Pipeline。
不修改或替换 run_pipeline.py。
"""

from core.schemas.contracts.task import InferenceTask, TaskSpec, RunContext
from core.schemas.contracts.perception import PerceptionResult


class TaskDrivenRunner:
    """
    任务驱动 Runner：通过 InferenceTask + TaskSpec + RunContext 调用 Pipeline。

    当前通过兼容适配器调用现有 Pipeline。
    未来可替换为 SarTemporalChangeTool 等具体工具。
    """

    def __init__(self, pipeline_runner=None):
        """
        pipeline_runner: 可选，兼容 callable(task, spec, context) -> PerceptionResult
        如果为 None，使用默认的兼容包装。
        """
        self._runner = pipeline_runner

    def run(self, task: InferenceTask, spec: TaskSpec, context: RunContext) -> PerceptionResult:
        """
        运行一个任务。

        参数:
            task: 具体样本上下文（含资产绑定）
            spec: 任务规则定义
            context: 运行配置

        返回:
            PerceptionResult
        """
        if self._runner:
            return self._runner(task, spec, context)

        # 默认兼容模式：打印任务信息，返回占位结果
        # 实际使用时，这里会调用现有的 Pipeline
        raise NotImplementedError(
            "TaskDrivenRunner 需要注入 Pipeline 包装器。\n"
            "使用: TaskDrivenRunner(pipeline_runner=my_wrapper)\n"
            "或在子类中覆盖 run() 方法。"
        )
