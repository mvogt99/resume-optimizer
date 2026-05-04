"""Wave 12.7: Docker deployment artifact validation tests.

Tests validate Docker configuration files exist and are properly structured.
No containers are started — pure file inspection.
"""

import json
import pathlib

import pytest
import yaml

PROJECT_ROOT = pathlib.Path(__file__).resolve().parent.parent.parent


class TestDockerArtifacts:
    """Validate all Docker deployment files exist and are well-formed."""

    def test_backend_dockerfile_exists(self):
        dockerfile = PROJECT_ROOT / "backend" / "Dockerfile"
        assert dockerfile.exists(), "backend/Dockerfile missing"
        content = dockerfile.read_text()
        assert "FROM python:" in content
        assert "EXPOSE 5000" in content

    def test_frontend_dockerfile_exists(self):
        dockerfile = PROJECT_ROOT / "frontend" / "Dockerfile"
        assert dockerfile.exists(), "frontend/Dockerfile missing"
        content = dockerfile.read_text()
        assert "FROM node:" in content
        assert "npm run build" in content

    def test_docker_compose_exists(self):
        compose = PROJECT_ROOT / "docker-compose.yml"
        assert compose.exists(), "docker-compose.yml missing"

    def test_compose_has_5_services(self):
        compose = PROJECT_ROOT / "docker-compose.yml"
        data = yaml.safe_load(compose.read_text())
        services = list(data.get("services", {}).keys())
        assert "backend" in services
        assert "frontend" in services
        assert "arangodb" in services
        assert "qdrant" in services
        assert "artemis" in services
        assert len(services) == 5

    def test_compose_has_healthchecks(self):
        compose = PROJECT_ROOT / "docker-compose.yml"
        data = yaml.safe_load(compose.read_text())
        services_with_healthcheck = [
            name for name, cfg in data["services"].items() if "healthcheck" in cfg
        ]
        # At minimum arangodb and qdrant have healthchecks (backend depends on them)
        assert "arangodb" in services_with_healthcheck
        assert "qdrant" in services_with_healthcheck

    def test_compose_has_volumes(self):
        compose = PROJECT_ROOT / "docker-compose.yml"
        data = yaml.safe_load(compose.read_text())
        volumes = list(data.get("volumes", {}).keys())
        assert len(volumes) >= 3, f"Expected >=3 volumes, got {volumes}"
        assert "db-data" in volumes
        assert "uploads" in volumes

    def test_compose_has_network(self):
        compose = PROJECT_ROOT / "docker-compose.yml"
        data = yaml.safe_load(compose.read_text())
        networks = list(data.get("networks", {}).keys())
        assert "ro-network" in networks

    def test_dockerignore_excludes_db(self):
        dockerignore = PROJECT_ROOT / ".dockerignore"
        assert dockerignore.exists(), ".dockerignore missing"
        content = dockerignore.read_text()
        assert "*.db" in content
        assert "node_modules" in content
        assert "__pycache__" in content

    def test_env_example_exists(self):
        env_example = PROJECT_ROOT / ".env.example"
        assert env_example.exists(), ".env.example missing"
        content = env_example.read_text()
        assert "FLASK_DEBUG" in content
        assert "ARANGO_ENABLED" in content

    def test_nginx_config_proxies_api(self):
        nginx_conf = PROJECT_ROOT / "frontend" / "nginx.conf"
        assert nginx_conf.exists(), "frontend/nginx.conf missing"
        content = nginx_conf.read_text()
        assert "proxy_pass http://backend:5000" in content
        assert "location /api/" in content
        assert "try_files $uri $uri/ /index.html" in content

    def test_backend_dockerfile_has_healthcheck(self):
        dockerfile = PROJECT_ROOT / "backend" / "Dockerfile"
        content = dockerfile.read_text()
        assert "HEALTHCHECK" in content

    def test_frontend_dockerfile_has_healthcheck(self):
        dockerfile = PROJECT_ROOT / "frontend" / "Dockerfile"
        content = dockerfile.read_text()
        assert "HEALTHCHECK" in content
