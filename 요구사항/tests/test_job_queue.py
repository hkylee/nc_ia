import json
import shutil
import sys
import threading
import time
import unittest
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT / "src"))

from src import web_app


class PolicyJobQueueTest(unittest.TestCase):
    def setUp(self):
        self.original_output_root = web_app.OUTPUT_ROOT
        self.original_lock_dir = web_app.LOCK_DIR
        self.original_max_active = web_app.MAX_ACTIVE_POLICY_JOBS
        self.original_semaphore = web_app.POLICY_JOB_SEMAPHORE
        self.root = web_app.PROJECT_ROOT / ".tmp_job_queue_test"
        if self.root.exists():
            shutil.rmtree(self.root)
        self.output_root = self.root / "output"
        self.lock_dir = self.output_root / ".locks"
        self.lock_dir.mkdir(parents=True, exist_ok=True)
        web_app.OUTPUT_ROOT = self.output_root
        web_app.LOCK_DIR = self.lock_dir
        web_app.MAX_ACTIVE_POLICY_JOBS = 1
        web_app.POLICY_JOB_SEMAPHORE = threading.BoundedSemaphore(1)
        with web_app.JOBS_LOCK:
            self.original_jobs = dict(web_app.JOBS)
            web_app.JOBS.clear()

    def tearDown(self):
        with web_app.JOBS_LOCK:
            web_app.JOBS.clear()
            web_app.JOBS.update(self.original_jobs)
        web_app.OUTPUT_ROOT = self.original_output_root
        web_app.LOCK_DIR = self.original_lock_dir
        web_app.MAX_ACTIVE_POLICY_JOBS = self.original_max_active
        web_app.POLICY_JOB_SEMAPHORE = self.original_semaphore
        if self.root.exists():
            shutil.rmtree(self.root)

    def add_job(self, job_id: str = "job-1"):
        lock_path = self.lock_dir / f"{job_id}.lock"
        job = {
            "id": job_id,
            "kind": "create",
            "status": "queued",
            "message": "",
            "topic": "큐 테스트",
            "templateType": "simple",
            "createdAt": "2026-05-04T00:00:00",
            "startedAt": None,
            "finishedAt": None,
            "elapsedMs": 0,
            "currentStageKey": "",
            "cancelRequested": False,
            "activity": [],
            "stages": [],
            "lockKey": job_id,
            "lockPath": str(lock_path),
        }
        with web_app.JOBS_LOCK:
            web_app.JOBS[job_id] = job
        return job, lock_path

    def test_mark_policy_job_queued_records_queue_state(self):
        job, lock_path = self.add_job()

        web_app.mark_policy_job_queued(job["id"], "정책서 생성")
        snapshot = web_app.public_job(job)

        self.assertEqual("queued", snapshot["status"])
        self.assertEqual(1, snapshot["queueLimit"])
        self.assertIn("동시 작업 수 제한(1건)", snapshot["message"])
        self.assertNotIn("_queueNoticeRecorded", snapshot)
        self.assertEqual("job_queued", snapshot["activity"][0]["event"])
        lock_payload = json.loads(lock_path.read_text(encoding="utf-8"))
        self.assertEqual("queued", lock_payload["status"])
        self.assertIn("updated_at_epoch", lock_payload)

    def test_wait_for_policy_job_slot_waits_until_capacity_is_available(self):
        job, _ = self.add_job()
        self.assertTrue(web_app.POLICY_JOB_SEMAPHORE.acquire(timeout=1))
        result = []

        thread = threading.Thread(
            target=lambda: result.append(web_app.wait_for_policy_job_slot(job["id"], "정책서 생성")),
            daemon=True,
        )
        thread.start()
        time.sleep(0.2)

        self.assertEqual([], result)
        self.assertEqual("queued", job["status"])
        self.assertIn("실행 순서를 기다리고 있습니다", job["message"])

        web_app.POLICY_JOB_SEMAPHORE.release()
        thread.join(timeout=2)
        self.assertEqual([True], result)
        web_app.POLICY_JOB_SEMAPHORE.release()

    def test_service_queue_dashboard_includes_current_queue_and_history(self):
        queued, _ = self.add_job("queued-job")
        queued["topic"] = "대기 정책서"
        running, _ = self.add_job("running-job")
        running["topic"] = "실행 정책서"

        web_app.mark_policy_job_queued(queued["id"], "정책서 생성")
        web_app.mark_policy_job_running(running["id"], "정책서 생성을 시작했습니다.")
        jobs = web_app.summarize_service_jobs()
        queue = web_app.summarize_service_queue(jobs)

        self.assertEqual(1, queue["summary"]["limit"])
        self.assertEqual(1, queue["summary"]["queuedJobs"])
        self.assertEqual(1, queue["summary"]["runningQueueJobs"])
        self.assertEqual(0, queue["summary"]["availableSlots"])
        self.assertEqual(["대기 정책서", "실행 정책서"], [item["topic"] for item in queue["items"]])
        self.assertIn("job_queued", {item["event"] for item in queue["history"]})
        self.assertIn("job_started_from_queue", {item["event"] for item in queue["history"]})


if __name__ == "__main__":
    unittest.main()
