"""
B1 — Run Manifest: 自动记录运行血缘

每次 Pipeline 运行自动记录：
- run_id, task_id, task_spec_ref
- git_commit, git_branch, git_dirty
- Python 版本, OS, 关键依赖版本
- 输入 Asset ID, URI, SHA256, 元数据来源
- 输出 Artifact ID, URI, SHA256, 大小, 媒体类型
- 配置快照或配置哈希
- 时间戳、状态、失败详情
- 运行命令和随机种子
- validation policy
- Manifest 自身 SHA256
"""

import enum
import hashlib
import json
import os
import platform
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from pydantic import BaseModel, Field


# ── Git 工具函数 ─────────────────────────────────────────────────

def _git_cmd(*args: str, cwd: str | None = None) -> str | None:
    """执行 git 命令，失败时返回 None。"""
    try:
        git_root = _find_git_root()
        result = subprocess.run(
            ["git", *args],
            capture_output=True, text=True, timeout=10,
            encoding="utf-8", errors="replace",
            cwd=cwd or git_root,
        )
        if result.returncode == 0 and result.stdout:
            return result.stdout.strip()
        return None
    except (FileNotFoundError, subprocess.TimeoutExpired, PermissionError):
        return None


def _find_git_root() -> str | None:
    """尝试找到 git 根目录。"""
    try:
        result = subprocess.run(
            ["git", "rev-parse", "--show-toplevel"],
            capture_output=True, text=True, timeout=5,
            encoding="utf-8", errors="replace",
        )
        if result.returncode == 0 and result.stdout:
            return result.stdout.strip()
    except (FileNotFoundError, subprocess.TimeoutExpired):
        pass
    return None


def get_git_commit(cwd: str | None = None) -> str:
    """获取当前 HEAD commit SHA（完整 40 字符）。"""
    sha = _git_cmd("rev-parse", "HEAD", cwd=cwd)
    return sha if sha else "unknown"


def get_git_branch(cwd: str | None = None) -> str:
    """获取当前分支名。"""
    branch = _git_cmd("rev-parse", "--abbrev-ref", "HEAD", cwd=cwd)
    return branch if branch else "unknown"


def is_git_dirty(cwd: str | None = None) -> bool:
    """检查工作树是否有未提交修改。"""
    status = _git_cmd("status", "--porcelain", cwd=cwd)
    if status is None:
        return False
    return len(status.strip()) > 0


def get_git_root_or_none() -> str | None:
    return _find_git_root()


# ── 环境信息 ─────────────────────────────────────────────────────

def _get_python_version() -> str:
    return sys.version.split()[0]


def _get_os_info() -> str:
    return f"{platform.system()} {platform.release()} ({platform.version()})"


def _get_package_version(package: str) -> str:
    """获取已安装包的版本。"""
    try:
        import importlib.metadata
        return importlib.metadata.version(package)
    except Exception:
        return "unknown"


def _get_key_dependencies() -> dict[str, str]:
    """关键依赖版本。"""
    deps = ["pydantic", "rasterio", "numpy", "fastapi", "requests"]
    return {d: _get_package_version(d) for d in deps}


# ── 状态枚举 ─────────────────────────────────────────────────────

class RunStatus(str, enum.Enum):
    PENDING = "pending"
    RUNNING = "running"
    SUCCEEDED = "succeeded"
    FAILED = "failed"
    CANCELLED = "cancelled"


# ── 输入/输出记录 ────────────────────────────────────────────────

class InputAssetRecord(BaseModel):
    """输入资产的运行记录。"""
    asset_id: str
    uri: str = ""
    sha256: str = ""
    metadata_source: str = "unknown"
    dataset_version: str | None = None


class OutputArtifactRecord(BaseModel):
    """输出产物的运行记录。"""
    artifact_id: str
    uri: str = ""
    sha256: str = ""
    size_bytes: int = 0
    media_type: str = ""


# ── 失败信息 ─────────────────────────────────────────────────────

class FailureInfo(BaseModel):
    stage: str = ""
    error_type: str = ""
    message: str = ""


# ── Run Manifest ─────────────────────────────────────────────────

class RunManifest(BaseModel):
    """一次 Pipeline 运行的自动记录。"""

    # ── 核心标识 ────────────────────────────────────────────────
    schema_version: str = "run-manifest.v0.1"
    run_id: str = Field(..., min_length=1)
    task_id: str = Field("", description="任务 ID")
    task_spec_ref: str = Field("", description="TaskSpec 引用")

    # ── 时间 ────────────────────────────────────────────────────
    started_at: str = Field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    finished_at: str | None = None
    status: RunStatus = RunStatus.PENDING

    # ── Git 信息（自动获取） ────────────────────────────────────
    git_commit: str = Field(default_factory=get_git_commit)
    git_branch: str = Field(default_factory=get_git_branch)
    git_dirty: bool = Field(default_factory=is_git_dirty)
    git_root: str | None = Field(default_factory=get_git_root_or_none)

    # ── 环境信息 ────────────────────────────────────────────────
    python_version: str = Field(default_factory=_get_python_version)
    os_info: str = Field(default_factory=_get_os_info)
    key_dependencies: dict[str, str] = Field(default_factory=_get_key_dependencies)

    # ── 配置快照 ────────────────────────────────────────────────
    tool_config: dict = Field(default_factory=dict)
    validation_policy: dict = Field(default_factory=dict)
    config_hash: str = ""

    # ── 输入 ────────────────────────────────────────────────────
    input_assets: list[InputAssetRecord] = Field(default_factory=list)
    input_manifest_hash: str = ""

    # ── 输出 ────────────────────────────────────────────────────
    output_artifacts: list[OutputArtifactRecord] = Field(default_factory=list)

    # ── 代码与工具版本 ──────────────────────────────────────────
    code_version: str = ""
    tool_version: str = ""
    schema_version_tag: str = ""

    # ── 运行详情 ────────────────────────────────────────────────
    run_command: str = ""
    random_seed: int | None = None
    failure: FailureInfo | None = None

    # ── Manifest 自身 ───────────────────────────────────────────
    manifest_sha256: str = ""

    def compute_manifest_hash(self) -> str:
        """计算 Manifest 自身的完整 SHA256。"""
        # 排除动态字段和自身哈希
        data = self.model_dump(mode="json", exclude={"manifest_sha256", "started_at", "finished_at"})
        raw = json.dumps(data, sort_keys=True, ensure_ascii=False, separators=(",", ":"))
        return hashlib.sha256(raw.encode("utf-8")).hexdigest()

    def finalize(self, status: RunStatus = RunStatus.SUCCEEDED) -> "RunManifest":
        """完成 Manifest（设置完成时间、状态和哈希）。"""
        self.status = status
        self.finished_at = datetime.now(timezone.utc).isoformat()
        self.manifest_sha256 = self.compute_manifest_hash()
        # 脱敏路径（将绝对路径转为相对项目根）
        self._sanitize_paths()
        return self

    def _sanitize_paths(self) -> None:
        """将绝对路径脱敏为相对项目根或脱敏表示。"""
        root = _find_git_root()
        if not root:
            return
        for asset in self.input_assets:
            if asset.uri.startswith(root):
                asset.uri = asset.uri.replace(root, "${PROJECT_ROOT}", 1)
        for art in self.output_artifacts:
            if art.uri.startswith(root):
                art.uri = art.uri.replace(root, "${PROJECT_ROOT}", 1)

    def to_json(self, indent: int = 2) -> str:
        """输出规范 JSON。"""
        return self.model_dump_json(indent=indent)

    def save(self, path: str | Path) -> Path:
        """保存 Manifest 到文件。"""
        p = Path(path)
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(self.to_json(), encoding="utf-8")
        return p


# ── RunManifestBuilder（便捷构建器）─
class RunManifestBuilder:
    """便捷构建 Run Manifest。"""

    @staticmethod
    def create(
        run_id: str,
        task_id: str = "",
        task_spec_ref: str = "",
        tool_config: dict | None = None,
        validation_policy: dict | None = None,
        run_command: str = "",
        random_seed: int | None = None,
    ) -> RunManifest:
        return RunManifest(
            run_id=run_id,
            task_id=task_id,
            task_spec_ref=task_spec_ref,
            tool_config=tool_config or {},
            validation_policy=validation_policy or {},
            run_command=run_command,
            random_seed=random_seed,
        )

    @staticmethod
    def add_input_asset(
        manifest: RunManifest,
        asset_id: str,
        uri: str = "",
        sha256: str = "",
        metadata_source: str = "unknown",
    ) -> RunManifest:
        manifest.input_assets.append(InputAssetRecord(
            asset_id=asset_id, uri=uri, sha256=sha256,
            metadata_source=metadata_source,
        ))
        return manifest

    @staticmethod
    def add_output_artifact(
        manifest: RunManifest,
        artifact_id: str,
        uri: str = "",
        sha256: str = "",
        size_bytes: int = 0,
        media_type: str = "",
    ) -> RunManifest:
        manifest.output_artifacts.append(OutputArtifactRecord(
            artifact_id=artifact_id, uri=uri, sha256=sha256,
            size_bytes=size_bytes, media_type=media_type,
        ))
        return manifest

    @staticmethod
    def fail(manifest: RunManifest, stage: str, error_type: str, message: str) -> RunManifest:
        manifest.failure = FailureInfo(stage=stage, error_type=error_type, message=message)
        return manifest.finalize(RunStatus.FAILED)

    @staticmethod
    def succeed(manifest: RunManifest) -> RunManifest:
        return manifest.finalize(RunStatus.SUCCEEDED)
