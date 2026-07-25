"""G0.3-B golden byte tests."""
import json, copy, pytest
from core.schemas.contracts import TaskType
from core.schemas.contracts.prediction import ClassificationPrediction, ChangePrediction, PredictionRecord
from core.schemas.contracts.submission_envelope import from_bundle
from core.schemas.contracts.run_manifest import RunManifest, RunManifestBuilder, RunStatus
from competition.exporters.competition_exporter import CompetitionExporter
from competition.validators.validator import SubmissionValidator

@pytest.fixture
def p():
    return [PredictionRecord(record_id="r1",inference_task_ref="t1",
        execution_status="succeeded_with_observations",
        payload=ClassificationPrediction(class_id=1,class_name="w",confidence=0.95)),
        PredictionRecord(record_id="r2",inference_task_ref="t2",
        execution_status="succeeded_with_observations",
        payload=ChangePrediction(change_pixels=5000))]

class TestDeterminism:
    def test_bytes_stable(self,p):
        e=CompetitionExporter()
        assert e.export(p,bundle_id="b1").to_bytes()==e.export(p,bundle_id="b1").to_bytes()
    def test_hash_stable(self,p):
        e=CompetitionExporter()
        assert e.export(p,bundle_id="b1").compute_checksum()==e.export(p,bundle_id="b1").compute_checksum()
    def test_content_changes_hash(self,p):
        b=CompetitionExporter().export(p,bundle_id="b1");h=b.compute_checksum()
        b.predictions[0].payload.class_id=2;assert b.compute_checksum()!=h
    def test_envelope(self,p):
        b=CompetitionExporter().export(p,bundle_id="b1")
        pl,env=from_bundle(b,source_manifest_hash="a"*64,producer_version="v1")
        assert env.bundle_id==b.bundle_id and env.payload_hash==pl.payload_hash and env.verify()
    def test_no_timestamp(self,p):
        assert "created_at" not in json.loads(from_bundle(CompetitionExporter().export(p,bundle_id="b1"))[0].model_dump_json())
    def test_has_timestamp(self,p):
        assert "created_at" in json.loads(from_bundle(CompetitionExporter().export(p,bundle_id="b1"))[1].model_dump_json())

class TestTaskType:
    def test_match(self):
        r=PredictionRecord(record_id="r1",inference_task_ref="t1",
            execution_status="succeeded_with_observations",payload=ClassificationPrediction(class_id=1,confidence=0.9))
        assert SubmissionValidator().validate(CompetitionExporter().export([r],bundle_id="tt"),
            task_type_map={"t1":TaskType.CLASSIFICATION}).passed
    def test_mismatch(self):
        r=PredictionRecord(record_id="r1",inference_task_ref="t1",
            execution_status="succeeded_with_observations",payload=ClassificationPrediction(class_id=1,confidence=0.9))
        rpt=SubmissionValidator().validate(CompetitionExporter().export([r],bundle_id="tt"),
            task_type_map={"t1":TaskType.TEMPORAL_CHANGE_DETECTION})
        assert len([e for e in rpt.errors if "payload_type" in e])>0

class TestStatus:
    def test_no_data_rejects(self):
        assert not SubmissionValidator().validate(CompetitionExporter().export([
            PredictionRecord(record_id="r1",inference_task_ref="t1",
                execution_status="no_data",payload=ClassificationPrediction(class_id=0,confidence=0.0))
        ],bundle_id="nd")).passed
    def test_failed_rejects(self):
        assert not SubmissionValidator().validate(CompetitionExporter().export([
            PredictionRecord(record_id="r1",inference_task_ref="t1",
                execution_status="failed",payload=ClassificationPrediction(class_id=0,confidence=0.0))
        ],bundle_id="fl")).passed

class TestManifest:
    def test_save_load(self,tmpdir):
        m=RunManifestBuilder.create(run_id="r1",task_id="t1").finalize(RunStatus.SUCCEEDED)
        h=m.manifest_sha256;p=str(tmpdir/"m.json");m.save(p)
        assert RunManifest.load(p).manifest_sha256==h
    def test_verify(self):
        m=RunManifestBuilder.create(run_id="r2",task_id="t2").finalize(RunStatus.SUCCEEDED)
        assert m.verify_hash()==(True,m.manifest_sha256)
    def test_tampered(self):
        m=RunManifestBuilder.create(run_id="r3",task_id="t3").finalize(RunStatus.SUCCEEDED)
        m.manifest_sha256="0"*64;assert m.verify_hash()==(False,m.compute_manifest_hash())
