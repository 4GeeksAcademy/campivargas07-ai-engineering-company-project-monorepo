"""Fail closed when opt-in development monitoring has no credentials."""
import os

if __name__ == "__main__":
    credentials = os.environ.get("FLOWER_BASIC_AUTH", "")
    if ":" not in credentials or not all(credentials.split(":", 1)):
        raise SystemExit("Set FLOWER_BASIC_AUTH=user:password before starting Flower")
    os.execvp("celery", ["celery", "-A", "app.worker.celery_app:celery_app", "flower",
                         "--port=5555", "--persistent=True", "--db=/var/lib/flower/flower"])
