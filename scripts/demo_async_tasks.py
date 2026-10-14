"""Real DEV-55 Docker demonstration with isolated PostgreSQL, Redis and users.

Run from the repository root: python scripts/demo_async_tasks.py
Requires Docker Compose >=2.24.4. No Python packages outside the stdlib needed.
The demo stops/removes only its own project; existing data is never used.
"""
import base64
import json
import os
from pathlib import Path
import secrets
import subprocess
import tempfile
import time
import urllib.error
import urllib.request

ROOT = Path(__file__).resolve().parents[1]
EVIDENCE = ROOT / "docs" / "pr-assets" / "dev55"


def main():
    EVIDENCE.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix="brasaland-dev55-demo-") as temp:
        directory = Path(temp)
        override = directory / "compose.yml"
        env = dict(os.environ, DATABASE_URL="postgresql://demo:demo@postgres-demo:5432/dev55",
                   SECRET_KEY=secrets.token_urlsafe(32), REDIS_URL="redis://redis:6379/0",
                   FLOWER_BASIC_AUTH="demo:" + secrets.token_urlsafe(24))
        override.write_text(f"""services:
  postgres-demo:
    image: postgres:16-alpine
    environment:
      POSTGRES_USER: demo
      POSTGRES_PASSWORD: demo
      POSTGRES_DB: dev55
    healthcheck:
      test: [CMD-SHELL, pg_isready -U demo -d dev55]
      interval: 2s
      timeout: 2s
      retries: 30
    networks: [brasaland-dev]
  backend:
    container_name: brasaland-dev55-demo-api
    command: [uvicorn, app.main:app, --host, 0.0.0.0, --port, "8000"]
    ports: !override ["127.0.0.1:18055:8000"]
    environment:
      SUPPLIERS_DB_PATH: /demo-control/users.json
    volumes:
      - {temp}:/demo-control
    depends_on:
      postgres-demo:
        condition: service_healthy
  worker:
    command: [python, /demo/demo_async_worker.py]
    volumes:
      - {ROOT / 'scripts'}:/demo:ro
      - {temp}:/demo-control:ro
    depends_on:
      postgres-demo:
        condition: service_healthy
  flower:
    ports: !override ["127.0.0.1:15555:5555"]
  redis:
    ports: !override ["127.0.0.1:16355:6379"]
networks:
  brasaland-dev:
    name: brasaland-dev55-demo
""")
        compose = ["docker", "compose", "--env-file", "/dev/null", "-p", "brasaland-dev55-demo",
                   "-f", str(ROOT / "docker-compose.yml"), "-f", str(override), "--profile", "monitoring"]

        def dc(*args, stdin=None):
            result = subprocess.run(compose + list(args), input=stdin, text=True,
                                    capture_output=True, env=env, cwd=ROOT)
            if result.returncode:
                # Docker operational errors only; never print environment/tokens.
                raise RuntimeError(f"Docker command failed: {args[:2]}\n{result.stderr[-2500:]}")
            return result.stdout

        def api(path, body=None, token=None, flower=False):
            url = ("http://127.0.0.1:15555" if flower else "http://127.0.0.1:18055") + path
            headers = {"Content-Type": "application/json"}
            if token:
                headers["Authorization"] = "Bearer " + token
            if flower:
                headers["Authorization"] = "Basic " + base64.b64encode(env["FLOWER_BASIC_AUTH"].encode()).decode()
            req = urllib.request.Request(url, json.dumps(body).encode() if body is not None else None, headers)
            try:
                with urllib.request.urlopen(req, timeout=10) as response:
                    return response.status, response.read().decode()
            except urllib.error.HTTPError as error:
                return error.code, error.read().decode()

        def wait_for(check, seconds=300):
            deadline = time.monotonic() + seconds
            while time.monotonic() < deadline:
                try:
                    value = check()
                    if value:
                        return value
                except (urllib.error.URLError, ConnectionError, TimeoutError):
                    pass
                time.sleep(1)
            raise TimeoutError("Demo condition did not complete")

        report = {}
        try:
            print("Building API, worker and Flower images...", flush=True)
            dc("build", "backend", "worker", "flower")
            dc("up", "-d", "postgres-demo", "redis", "backend", "flower")
            wait_for(lambda: api("/health")[0] == 200)
            admin_password = secrets.token_urlsafe(20)
            seed = f"""import os, uuid
from pathlib import Path
from sqlalchemy import text
from app.database import get_db_engine, users_table
from app.domains.auth.service import hash_password
engine = get_db_engine()
with engine.begin() as conn:
    for name in ('001_create_telemetry_events.sql', '002_create_inventory_health_reporting.sql', '004_create_async_tasks.sql'):
        conn.execute(text((Path('migrations') / name).read_text()))
    conn.execute(text("INSERT INTO ingredient (id,sku,name,category,unit_of_measure,minimum_stock,perishable,created_at) VALUES (:id,'DEV55-DEMO','Demo ingredient','carne','kg',20,true,CURRENT_TIMESTAMP)"), {{'id': uuid.uuid4()}})
    conn.execute(text("INSERT INTO ingredient_entry (id,ingredient_id,local_id,quantity,user_uuid,created_at) SELECT :id,id,'MED-001',15,:user_id,CURRENT_TIMESTAMP FROM ingredient WHERE sku='DEV55-DEMO'"), {{'id': uuid.uuid4(), 'user_id': uuid.uuid4()}})
users_table.insert({{'uuid': str(uuid.uuid4()), 'email': 'dev55-demo@example.test', 'hashed_password': hash_password({admin_password!r}), 'role': 'admin', 'is_active': True, 'created_at': '2026-10-09T00:00:00Z'}})
print('Isolated demo data ready')
"""
            dc("exec", "-T", "backend", "python", "-", stdin=seed)
            code, login = api("/auth/login", {"email": "dev55-demo@example.test", "password": admin_password})
            assert code == 200, "Demo login failed"
            token = json.loads(login)["access_token"]
            assert api("/tasks/00000000-0000-0000-0000-000000000001")[0] == 401
            assert api("/tasks/00000000-0000-0000-0000-000000000001", token=token)[0] == 404
            # Worker is absent. A 202 proves the HTTP response does not wait for it.
            start = time.monotonic()
            code, body = api("/reporting/inventory-health/runs", {}, token)
            response_seconds = round(time.monotonic() - start, 3)
            success = json.loads(body)
            assert code == 202 and success["task_id"] == success["flow_run_id"]
            success_id = success["task_id"]
            assert json.loads(api(f"/tasks/{success_id}", token=token)[1])["status"] == "pending"
            # Decode the real Redis queue envelope and verify UUID-only arguments.
            envelope = json.loads(dc("exec", "-T", "redis", "redis-cli", "--raw", "LINDEX", "inventory-health", "0"))
            arguments = json.loads(base64.b64decode(envelope["body"]))
            assert arguments[0] == [success_id] and arguments[1] == {}
            dc("stop", "backend")
            dc("up", "-d", "worker")
            print(f"POST returned 202 in {response_seconds}s; API stopped, worker executing real pipeline...", flush=True)
            def worker_success():
                state = dc("exec", "-T", "worker", "python", "-c",
                           f"from app.worker.celery_app import celery_app; print(celery_app.AsyncResult('{success_id}').state)")
                if state.strip() == "FAILURE":
                    raise RuntimeError("Real pipeline failed; inspect sanitized worker.log")
                return state.strip() == "SUCCESS"
            wait_for(worker_success)
            dc("up", "-d", "backend")
            wait_for(lambda: api("/health")[0] == 200)
            success_status = json.loads(api(f"/tasks/{success_id}", token=token)[1])
            assert success_status["status"] == "success" and success_status["result"]["status"] == "COMPLETED"
            assert success_status["result"]["snapshots_loaded"] >= 1
            report["success"] = dict(success_status, response_seconds=response_seconds, api_stopped_during_execution=True,
                                     redis_arguments=arguments[:2])
            # Stop worker before posting failure so its UUID is selected atomically.
            dc("stop", "worker")
            code, body = api("/reporting/inventory-health/runs", {}, token)
            assert code == 202
            failure_id = json.loads(body)["task_id"]
            (directory / "failure-id").write_text(failure_id)
            dc("up", "-d", "worker")
            print("Injecting real PostgreSQL SQLSTATE 40001 to verify retries and final DLQ...", flush=True)
            def failed():
                code, body = api(f"/tasks/{failure_id}", token=token)
                return json.loads(body) if code == 200 and json.loads(body)["status"] == "failure" else None
            failure_status = wait_for(failed)
            report["failure"] = failure_status
            dlq = dc("exec", "-T", "backend", "python", "-c",
                     f"import json; from sqlalchemy import text; from app.database import get_db_engine; c=get_db_engine().connect(); r=c.execute(text(\"SELECT task_id,attempt,error,failed_at FROM task_dead_letters WHERE task_id='{failure_id}'\")).mappings().one(); print(json.dumps(dict(r),default=str))")
            report["dlq"] = json.loads(dlq)
            assert report["dlq"]["attempt"] == 4
            report["flower"] = {}
            for task_id, expected in ((success_id, "SUCCESS"), (failure_id, "FAILURE")):
                info = wait_for(lambda: flower_info(api, task_id, expected))
                report["flower"][task_id] = {k: info.get(k) for k in ("uuid", "name", "state", "retries", "runtime", "result", "exception")}
                code, html = api(f"/task/{task_id}", flower=True)
                assert code == 200 and expected in html
                (EVIDENCE / f"flower-{expected.lower()}.html").write_text(html)
            if env.get("DEV55_PLAYWRIGHT_MODULE"):
                subprocess.run(["node", str(ROOT / "scripts/demo_async_flower.cjs")], check=True, env=dict(
                    env, DEV55_SUCCESS_ID=success_id, DEV55_FAILURE_ID=failure_id,
                    DEV55_EVIDENCE_DIR=str(EVIDENCE)), cwd=ROOT)
            # Broker outage must fail honestly and update the scheduled run.
            dc("stop", "redis")
            code, body = api("/reporting/inventory-health/runs", {}, token)
            assert code == 503
            report["broker_unavailable"] = {"http_status": code, "response": json.loads(body)}
            failed_publication = dc("exec", "-T", "backend", "python", "-c",
                "import json; from sqlalchemy import text; from app.database import get_db_engine; c=get_db_engine().connect(); r=c.execute(text(\"SELECT a.status, p.pipeline_run_status FROM async_tasks a JOIN reporting.pipeline_execution_logs p ON p.pipeline_run_id=a.task_id WHERE a.attempt=0 AND a.status='FAILURE'\")).mappings().one(); print(json.dumps(dict(r)))")
            report["broker_unavailable"]["durable_states"] = json.loads(failed_publication)
            assert report["broker_unavailable"]["durable_states"] == {"status": "FAILURE", "pipeline_run_status": "FAILED"}
            logs = dc("logs", "--no-color", "worker")
            lines = [line for line in logs.splitlines() if "task_id=" in line]
            (EVIDENCE / "worker.log").write_text("\n".join(lines) + "\n")
            assert all(f"retry_in_seconds={delay}" in "\n".join(lines) for delay in (5, 10, 20))
            (EVIDENCE / "results.json").write_text(json.dumps(report, indent=2) + "\n")
            print(json.dumps(report, indent=2), flush=True)
        finally:
            # Preserve own logs if an assertion fails, then remove only demo volumes.
            logs = dc("logs", "--no-color", "worker")
            (EVIDENCE / "worker.log").write_text("\n".join(line for line in logs.splitlines() if "task_id=" in line) + "\n")
            dc("down", "--volumes", "--remove-orphans")


def flower_info(api, task_id, expected):
    code, body = api(f"/api/task/info/{task_id}", flower=True)
    if code != 200:
        return None
    info = json.loads(body)
    return info if info.get("state") == expected else None


if __name__ == "__main__":
    main()
