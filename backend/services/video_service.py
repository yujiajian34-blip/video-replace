import json
import mimetypes
import subprocess
import time
import uuid
from pathlib import Path
from urllib.parse import urlparse

import boto3
import requests
from botocore.client import Config as BotoConfig

from config import AppConfig, BASE_DIR, TEMP_DIR


class VideoManager:
    MAX_DURATION_SECONDS = 15.0

    def __init__(self, temp_dir=None):
        self.temp_dir = Path(temp_dir or TEMP_DIR)
        self.temp_dir.mkdir(parents=True, exist_ok=True)
        self._s3_client = None

    @staticmethod
    def is_url(source):
        parsed = urlparse(str(source or "").strip())
        return parsed.scheme in {"http", "https"}

    def prepare_source(self, source):
        local_path, was_downloaded = self._resolve_source(source)
        original_meta = self.probe_video(local_path)

        processed_path = local_path
        speed_factor = 1.0
        was_accelerated = False

        if original_meta["duration_seconds"] > self.MAX_DURATION_SECONDS:
            speed_factor = original_meta["duration_seconds"] / self.MAX_DURATION_SECONDS
            processed_path = self.speed_up_video(
                local_path,
                speed_factor=speed_factor,
                has_audio=original_meta["has_audio"],
            )
            was_accelerated = True

        processed_meta = self.probe_video(processed_path)
        object_name = self._build_object_name(processed_path)
        public_url = self.upload_to_r2(processed_path, object_name=object_name)

        return {
            "source": str(source),
            "local_path": str(local_path),
            "processed_path": str(processed_path),
            "public_url": public_url,
            "uploaded_filename": object_name,
            "duration_seconds": original_meta["duration_seconds"],
            "processed_duration_seconds": processed_meta["duration_seconds"],
            "speed_factor": speed_factor,
            "was_downloaded": was_downloaded,
            "was_accelerated": was_accelerated,
            "has_audio": original_meta["has_audio"],
        }

    def _resolve_source(self, source):
        source = str(source or "").strip()
        if not source:
            raise ValueError("缺少视频 source 参数")

        if self.is_url(source):
            return self.download_to_temp(source), True

        local_path = Path(source).expanduser()
        if not local_path.is_absolute():
            local_path = (BASE_DIR / local_path).resolve()
        else:
            local_path = local_path.resolve()

        if not local_path.exists():
            raise FileNotFoundError(f"本地视频不存在: {local_path}")

        return local_path, False

    def download_to_temp(self, source_url):
        suffix = self._guess_suffix_from_url(source_url)
        filename = f"download_{int(time.time() * 1000)}_{uuid.uuid4().hex[:8]}{suffix}"
        save_path = self.temp_dir / filename

        with requests.Session() as session:
            session.trust_env = False
            response = session.get(source_url, stream=True, timeout=300)
            response.raise_for_status()
            with open(save_path, "wb") as handle:
                for chunk in response.iter_content(chunk_size=1024 * 1024):
                    if chunk:
                        handle.write(chunk)

        return save_path

    def probe_video(self, file_path):
        cmd = [
            "ffprobe",
            "-v",
            "error",
            "-show_entries",
            "format=duration",
            "-show_streams",
            "-of",
            "json",
            str(file_path),
        ]
        result = self._run_command(cmd, "ffprobe 获取视频信息失败")
        payload = json.loads(result.stdout or "{}")
        duration = float(payload.get("format", {}).get("duration") or 0.0)
        has_audio = any(
            stream.get("codec_type") == "audio"
            for stream in payload.get("streams", [])
        )

        if duration <= 0:
            raise ValueError(f"无法识别视频时长: {file_path}")

        return {"duration_seconds": duration, "has_audio": has_audio}

    def speed_up_video(self, input_path, speed_factor, has_audio):
        output_path = self.temp_dir / (
            f"{Path(input_path).stem}_x{speed_factor:.3f}_{uuid.uuid4().hex[:8]}.mp4"
        )

        cmd = [
            "ffmpeg",
            "-y",
            "-i",
            str(input_path),
            "-filter:v",
            f"setpts=PTS/{speed_factor:.6f}",
        ]

        if has_audio:
            cmd.extend(["-filter:a", self._build_atempo_chain(speed_factor)])
        else:
            cmd.append("-an")

        cmd.extend(
            [
                "-c:v",
                "libx264",
                "-preset",
                "veryfast",
                "-movflags",
                "+faststart",
            ]
        )

        if has_audio:
            cmd.extend(["-c:a", "aac"])

        cmd.append(str(output_path))
        self._run_command(cmd, "ffmpeg 视频加速失败")
        return output_path

    def upload_to_r2(self, file_path, object_name=None):
        self._validate_r2_config()
        file_path = Path(file_path)
        object_name = object_name or self._build_object_name(file_path)
        content_type = mimetypes.guess_type(str(file_path))[0] or "video/mp4"

        self.s3_client.upload_file(
            str(file_path),
            AppConfig.R2_BUCKET,
            object_name,
            ExtraArgs={"ContentType": content_type},
        )

        return f"{AppConfig.R2_PUBLIC_BASE_URL.rstrip('/')}/{object_name}"

    @property
    def s3_client(self):
        if self._s3_client is None:
            self._s3_client = boto3.client(
                "s3",
                endpoint_url=AppConfig.R2_ENDPOINT,
                aws_access_key_id=AppConfig.R2_ACCESS_KEY_ID,
                aws_secret_access_key=AppConfig.R2_SECRET_ACCESS_KEY,
                region_name=AppConfig.R2_REGION,
                config=BotoConfig(signature_version="s3v4"),
            )
        return self._s3_client

    def _validate_r2_config(self):
        if (
            not AppConfig.R2_ACCESS_KEY_ID
            or not AppConfig.R2_SECRET_ACCESS_KEY
            or AppConfig.R2_ACCESS_KEY_ID == "YOUR_R2_ACCESS_KEY_ID"
            or AppConfig.R2_SECRET_ACCESS_KEY == "YOUR_R2_SECRET_ACCESS_KEY"
        ):
            raise ValueError("请先在 backend/config.py 或环境变量中配置 R2 Access Key 和 Secret Key")

    @staticmethod
    def _build_atempo_chain(speed_factor):
        filters = []
        remaining = float(speed_factor)

        while remaining > 2.0 + 1e-6:
            filters.append("atempo=2.0")
            remaining /= 2.0

        if remaining > 1.0 + 1e-6:
            filters.append(f"atempo={remaining:.6f}")

        return ",".join(filters) or "atempo=1.0"

    @staticmethod
    def _guess_suffix_from_url(source_url):
        suffix = Path(urlparse(source_url).path).suffix.lower()
        return suffix or ".mp4"

    @staticmethod
    def _build_object_name(file_path):
        file_path = Path(file_path)
        stem = "".join(
            char if char.isalnum() or char in {"-", "_"} else "_"
            for char in file_path.stem
        ).strip("_") or "video"
        suffix = file_path.suffix or ".mp4"
        return f"{stem}_{int(time.time() * 1000)}_{uuid.uuid4().hex[:8]}{suffix}"

    @staticmethod
    def _run_command(command, error_message):
        result = subprocess.run(
            command,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            check=False,
        )
        if result.returncode != 0:
            detail = (result.stderr or result.stdout or "").strip()
            raise RuntimeError(f"{error_message}: {detail}")
        return result
