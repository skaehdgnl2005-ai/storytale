"""S1 — 모노레포 초기화 & 개발환경 검증 테스트.

이 테스트는 모노레포의 기본 구조와 설정 파일이 올바르게
구성되었는지 확인합니다.
"""

import importlib
from pathlib import Path

import pytest

# 프로젝트 루트 (storytale-harness/)
ROOT = Path(__file__).resolve().parents[3]


class TestMonorepoFolderStructure:
    """모노레포 폴더 구조가 올바른지 확인."""

    @pytest.mark.parametrize(
        "dir_path",
        [
            "packages/backend",
            "packages/backend/src",
            "packages/backend/tests",
            "packages/shared",
            "packages/shared/src",
            "packages/shared/src/types",
            "packages/mobile",
            "packages/admin-web",
            "docs",
            "docs/contracts",
            "docs/prompts",
            "docs/guardrail-seeds",
        ],
    )
    def test_directory_exists(self, dir_path: str) -> None:
        assert (ROOT / dir_path).is_dir(), f"디렉토리 없음: {dir_path}"


class TestConfigFiles:
    """필수 설정 파일이 존재하는지 확인."""

    @pytest.mark.parametrize(
        "file_path",
        [
            "package.json",
            "packages/backend/pyproject.toml",
            "packages/shared/package.json",
            "packages/shared/tsconfig.json",
            "packages/mobile/package.json",
            "packages/admin-web/package.json",
            "docker-compose.yml",
            ".env.example",
            ".gitignore",
        ],
    )
    def test_config_file_exists(self, file_path: str) -> None:
        assert (ROOT / file_path).is_file(), f"파일 없음: {file_path}"


class TestPythonBackend:
    """백엔드 Python 패키지 검증."""

    def test_backend_package_importable(self) -> None:
        """pip install -e . 후 storytale 패키지를 import 할 수 있는지."""
        mod = importlib.import_module("storytale")
        assert hasattr(mod, "__version__")

    def test_fastapi_app_importable(self) -> None:
        """FastAPI app 객체를 import 할 수 있는지."""
        from storytale.app import app

        assert app is not None

    def test_health_endpoint_exists(self) -> None:
        """헬스체크 라우트가 등록되어 있는지."""
        from fastapi.testclient import TestClient

        from storytale.app import app

        client = TestClient(app)
        response = client.get("/health")
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "ok"


class TestDockerCompose:
    """Docker Compose 파일 검증."""

    def test_docker_compose_has_required_services(self) -> None:
        """PostgreSQL과 Redis 서비스가 정의되어 있는지."""
        import yaml

        compose_path = ROOT / "docker-compose.yml"
        with open(compose_path) as f:
            compose = yaml.safe_load(f)

        services = compose.get("services", {})
        assert "postgres" in services, "postgres 서비스 없음"
        assert "redis" in services, "redis 서비스 없음"


class TestEnvExample:
    """환경변수 예제 파일 검증."""

    @pytest.mark.parametrize(
        "var_name",
        [
            "DATABASE_URL",
            "REDIS_URL",
            "CLAUDE_API_KEY",
            "REPLICATE_API_TOKEN",
            "AWS_S3_BUCKET",
        ],
    )
    def test_env_example_contains_var(self, var_name: str) -> None:
        env_path = ROOT / ".env.example"
        content = env_path.read_text(encoding="utf-8")
        assert var_name in content, f".env.example에 {var_name} 없음"
