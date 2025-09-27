import io
import logging
import os
import random
import uuid
from enum import Enum
from pathlib import Path
from urllib.parse import quote_plus, urlparse

import gevent
from dotenv import load_dotenv
from locust import HttpUser, tag, task
from locust.env import Environment
from locust.stats import stats_history


logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
env_path = Path(__file__).resolve().parent.parent / ".env.template"
load_dotenv(env_path, override=True)

class LoadType(Enum):
    MEDIA = "media"
    HOME_TIMELINE = "home_timeline"
    COMPOSE_POST = "compose_post"

class LoadLevel(Enum):
    # users, spawn_rate, duration(s)
    LOW    = (50,  50,  30)
    MEDIUM = (200, 200, 30)
    HIGH   = (600, 600, 30)
    @property
    def users(self): return self.value[0]
    @property
    def spawn_rate(self): return self.value[1]
    @property
    def duration(self):   return self.value[2]

class BaseDSBUser(HttpUser):

    def on_start(self):
        self.client.headers.update({"Accept": "application/json"})

        uname_suffix = uuid.uuid4().hex[:10]
        self.username = f"chomp_{uname_suffix}"
        self.password = uuid.uuid4().hex

        first_names = ["Ada", "Linus", "Grace", "Guido", "Edsger", "Hedy", "Ken"]
        last_names  = ["Turing", "Knuth", "Hopper", "Lovelace", "Ritchie", "Lamport", "Torvalds"]

        signup_form = {
            "first_name": random.choice(first_names),
            "last_name":  random.choice(last_names),
            "username":   self.username,
            "password":   self.password,
            "signup":     "Sign Up",
        }
        r_signup = self.client.post(
            "/api/user/register",
            data=signup_form,
            name="POST /user/register",
            allow_redirects=True,
        )

        login_form = {"username": self.username, "password": self.password, "login": "Login"}
        r_login = self.client.post(
            "/api/user/login",
            data=login_form,
            name="POST /user/login",
            allow_redirects=True,
        )


class HomeTimelineUser(BaseDSBUser):
    @task
    @tag("home")
    def get_home_timeline(self):
        self.client.get(
            "/api/home-timeline/read",
            params={"start": 0, "stop": 100},
            name="GET /home-timeline/read",
        )


class ComposePostUser(BaseDSBUser):
    @task
    @tag("compose")
    def compose_post(self):
        text = _random_post_text()

        form_resp = self.client.post(
            "/api/post/compose",
            data={"post_type": "0", "text": text},
            name="POST /compose_post (form)",
            allow_redirects=False,
        )


class MediaUser(BaseDSBUser):
    def on_start(self):
        super().on_start()

        script_dir = Path(__file__).resolve().parent
        self.jpg_path = script_dir.parent / "media" / "rabbit.jpg"
        self.rabbit_bytes = self.jpg_path.read_bytes()
        self.media_ext = (self.jpg_path.suffix or ".jpg").lstrip(".").lower()

        # media service lives on port 8081
        p = urlparse(self.host)
        media_port = int(os.getenv("MEDIA_SERVICE_PORT", "8081"))
        self.media_base = f"{(p.scheme or 'http')}://{p.hostname}:{media_port}"

    @task
    @tag("media")
    def upload_media(self):
        # 1) Upload the image with field name 'media'
        files = {"media": ("rabbit.jpg", io.BytesIO(self.rabbit_bytes), "image/jpeg")}
        r = self.client.post(f"{self.media_base}/upload-media", files=files, name="POST /upload-media")
        r.raise_for_status()
        data = r.json()
        media_id = str(data["media_id"])
        media_type = data.get("media_type", self.media_ext)

        # 2) Compose on the main app
        text = _random_post_text()
        body = (
            f"post_type=0"
            f"&text={quote_plus(text)}"
            f"&media_ids=[\"{media_id}\"]"
            f"&media_types=[\"{media_type}\"]"
        )
        headers = {"Content-Type": "text/plain;charset=UTF-8"}
        self.client.post("/api/post/compose", data=body, headers=headers, name="POST /compose_with_media")


def _random_post_text():
    words = [
        "lorem","ipsum","dolor","sit","amet","consectetur","elit","dsb","social",
        "locust","load","test","compose","timeline","scale","perf","tweet","post"
    ]
    n = random.randint(6, 18)
    return " ".join(random.choices(words, k=n)) + f" #{uuid.uuid4().hex[:6]}"


class WorkloadGenerator:
    APPLICATION_IP = os.getenv("APPLICATION_IP")
    APPLICATION_PORT = int(os.getenv("APPLICATION_PORT"))

    def __init__(self):
        pass

    def fire_load(self, load_type: LoadType, load_level: LoadLevel):
        if load_type == LoadType.MEDIA:
            return self._run_locust(MediaUser, load_level)
        elif load_type == LoadType.HOME_TIMELINE:
            return self._run_locust(HomeTimelineUser, load_level)
        elif load_type == LoadType.COMPOSE_POST:
            return self._run_locust(ComposePostUser, load_level)
        else:
            raise ValueError(f"Unsupported load type: {load_type}")


    def _host(self) -> str:
        return f"http://{self.APPLICATION_IP}:{self.APPLICATION_PORT}"

    def _run_locust(self, user_class, level: LoadLevel):
        host = self._host()
        logging.info("Starting %s users against %s (spawn_rate=%s, duration=%ss)",
                     level.users, host, level.spawn_rate, level.duration)

        env = Environment(user_classes=[user_class], host=host)
        env.create_local_runner()
        env.runner.start(user_count=level.users, spawn_rate=level.spawn_rate)
        gevent.spawn(stats_history, env.runner)
        gevent.sleep(level.duration)
        env.runner.quit()

        # Summarize
        s = env.stats.total
        logging.info(
            "Done. Requests=%s, Failures=%s, RPS=%.2f, p95=%d ms, p99=%d ms",
            s.num_requests, s.num_failures, s.total_rps,
            s.get_response_time_percentile(0.95),
            s.get_response_time_percentile(0.99),
        )
        return s


if __name__ == "__main__":
    wg = WorkloadGenerator()
    wg.fire_load(LoadType.MEDIA, LoadLevel.LOW)