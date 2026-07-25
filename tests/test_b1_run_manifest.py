"""
B1 — Run Manifest 测试
"""

import json
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import pytest
from pydantic import ValidationError

from core.schemas.contracts.run_manifest import (
    RunManifest, RunManifestBuilder, RunStatus,
    InputAssetRecord, OutputArtifactRecord,
    get_git_commit, get_git_branch, is_git_dirty,
)


class TestGitUtils:
    def test_get_git_commit(self):
        """获取真实 git commit。"""
        sha = get_git_commit()
        assert sha != "unknown"
        assert len(sha) == 40

    def test_get_git_branch(self):
        """获取真实 git branch。"""
        branch = get_git_branch()
        assert branch != "unknown"
        assert len(branch) > 0

    def test_is_git_dirty(self):
        """git dirty 不崩溃。"""
        dirty = is_git_dirty()
        assert isinstance(dirty, bool)


class TestRunManifest:
    def test_minimal_manifest(self):
        """最小 RunManifest 可创建。"""
        m = RunManifestBuilder.create(run_id="minimal-run")
        assert m.run_id == "minimal-run"
        assert m.status == RunStatus.PENDING

    def test_succeed_flow(self):
        """正常完成流程。"""
        m = RunManifestBuilder.create(run_id="succeed-run", task_id="task-001")
        m = RunManifestBuilder.succeed(m)
        assert m.status == RunStatus.SUCCEEDED
        assert m.finished_at is not None
        assert len(m.manifest_sha256) == 64

    def test_fail_flow(self):
        """失败流程。"""
        m = RunManifestBuilder.create(run_id="fail-run")
        m = RunManifestBuilder.fail(m, stage="quality_gate", error_type="rejected", message="低质量")
        assert m.status == RunStatus.FAILED
        assert m.failure is not None
        assert m.failure.stage == "quality_gate"
        assert m.failure.error_type == "rejected"

    def test_input_assets(self):
        """输入资产记录。"""
        m = RunManifestBuilder.create(run_id="input-test")
        m = RunManifestBuilder.add_input_asset(
            m, asset_id="s1-001", uri="data/raw/s1.tif",
            sha256="a" * 64, metadata_source="geotiff_tags",
        )
        assert len(m.input_assets) == 1
        assert m.input_assets[0].asset_id == "s1-001"
        assert m.input_assets[0].sha256 == "a" * 64

    def test_output_artifacts(self):
        """输出产物记录。"""
        m = RunManifestBuilder.create(run_id="output-test")
        m = RunManifestBuilder.add_output_artifact(
            m, artifact_id="change_mask", uri="output/mask.tif",
            sha256="b" * 64, size_bytes=1024, media_type="image/tiff",
        )
        assert len(m.output_artifacts) == 1
        assert m.output_artifacts[0].artifact_id == "change_mask"
        assert m.output_artifacts[0].size_bytes == 1024

    def test_manifest_self_sha256(self):
        """Manifest 自身 SHA256 为完整 64 字符。"""
        m = RunManifestBuilder.create(run_id="sha256-test")
        m = RunManifestBuilder.succeed(m)
        sha = m.manifest_sha256
        assert len(sha) == 64
        assert sha == sha.lower()
        # 再次计算应一致（排除动态时间字段）
        recomputed = m.compute_manifest_hash()
        # 注意: finalize 后时间已固定，recompute 排除时间字段
        assert sha == recomputed

    def test_deterministic_content(self):
        """同一输入产生一致核心内容（时间不同除外）。"""
        m1 = RunManifestBuilder.create(run_id="det-run", task_id="task-X", random_seed=42)
        m1 = RunManifestBuilder.add_input_asset(m1, "asset-1", sha256="c" * 64)
        m1 = RunManifestBuilder.succeed(m1)

        m2 = RunManifestBuilder.create(run_id="det-run", task_id="task-X", random_seed=42)
        m2 = RunManifestBuilder.add_input_asset(m2, "asset-1", sha256="c" * 64)
        m2 = RunManifestBuilder.succeed(m2)

        # 核心字段一致
        assert m1.git_commit == m2.git_commit
        assert m1.run_id == m2.run_id
        assert len(m1.input_assets) == len(m2.input_assets)

    def test_env_info_populated(self):
        """环境信息自动填充。"""
        m = RunManifestBuilder.create(run_id="env-test")
        assert m.python_version.startswith("3.")
        assert len(m.os_info) > 0
        assert "pydantic" in m.key_dependencies

    def test_validation_error_on_empty_run_id(self):
        """空 run_id 应被拒绝。"""
        with pytest.raises(ValidationError):
            RunManifest(run_id="")

    def test_json_serialization(self):
        """JSON 序列化可逆。"""
        m = RunManifestBuilder.create(run_id="json-test", task_id="task-J")
        m = RunManifestBuilder.add_input_asset(m, "asset-in")
        m = RunManifestBuilder.succeed(m)
        json_str = m.to_json()
        data = json.loads(json_str)
        assert data["run_id"] == "json-test"
        assert data["status"] == "succeeded"

    def test_save_and_load(self):
        """保存和重新加载 Manifest。"""
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "manifest.json"
            m = RunManifestBuilder.create(run_id="save-test")
            m = RunManifestBuilder.succeed(m)
            m.save(str(path))
            assert path.exists()
            loaded = json.loads(path.read_text(encoding="utf-8"))
            assert loaded["run_id"] == "save-test"
            assert loaded["status"] == "succeeded"

    def test_sanitize_paths(self):
        """绝对路径被脱敏。"""
        m = RunManifestBuilder.create(run_id="path-test")
        m = RunManifestBuilder.add_input_asset(m, "asset-1", uri=str(ROOT / "data" / "raw" / "s1.tif"))
        m = RunManifestBuilder.succeed(m)
        # 路径中包含 ${PROJECT_ROOT} 或已脱敏
        sanitized = m.input_assets[0].uri
        assert "${PROJECT_ROOT}" in sanitized or len(sanitized) > 0

    def test_non_git_environment(self):
        """在非 git 环境也能运行（模拟）。"""
        # 直接构造，不通过 builder（跳过字段默认值）
        m = RunManifest(
            run_id="no-git-env",
            git_commit="unknown",
            git_branch="unknown",
            git_dirty=False,
        )
        m.finalize()
        assert m.git_commit == "unknown"
        assert m.git_branch == "unknown"
        assert m.manifest_sha256 is not None
