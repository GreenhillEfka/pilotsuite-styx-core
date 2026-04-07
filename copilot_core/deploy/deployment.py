"""P7-005: Deployment Automation — K8s, Docker, HACS, One-Click Deploy."""
from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional
from pathlib import Path
from enum import Enum

logger = logging.getLogger(__name__)


class DeployTarget(Enum):
    """Deployment targets."""
    DOCKER = "docker"
    KUBERNETES = "kubernetes"
    HACS = "hacs"
    BARE_METAL = "bare_metal"


@dataclass
class DeployConfig:
    """Deployment configuration."""
    target: DeployTarget
    version: str
    replicas: int = 1
    resources: Dict[str, str] = field(default_factory=dict)
    env_vars: Dict[str, str] = field(default_factory=dict)
    volumes: List[str] = field(default_factory=list)


class DeploymentAutomation:
    """Automated deployment for PilotSuite."""

    def __init__(self):
        self._deployments: Dict[str, Dict] = {}
        self._templates: Dict[DeployTarget, str] = {}
        self._register_templates()

    def _register_templates(self):
        """Register deployment templates."""
        # Docker Compose
        self._templates[DeployTarget.DOCKER] = '''
version: '3.8'
services:
  pilotsuite-core:
    image: pilotsuite/core:{version}
    container_name: pilotsuite-core
    restart: unless-stopped
    ports:
      - "8123:8123"
    environment:
      - HA_URL={ha_url}
      - HA_TOKEN={ha_token}
      - OLLAMA_URL={ollama_url}
    volumes:
      - ./data:/app/data
      - ./config:/app/config
    healthcheck:
      test: ["CMD", "curl", "-f", "http://localhost:8123/api/v1/health"]
      interval: 30s
      timeout: 10s
      retries: 3
'''

        # Kubernetes
        self._templates[DeployTarget.KUBERNETES] = '''
apiVersion: apps/v1
kind: Deployment
metadata:
  name: pilotsuite-core
  labels:
    app: pilotsuite-core
    version: {version}
spec:
  replicas: {replicas}
  selector:
    matchLabels:
      app: pilotsuite-core
  template:
    metadata:
      labels:
        app: pilotsuite-core
    spec:
      containers:
      - name: core
        image: pilotsuite/core:{version}
        ports:
        - containerPort: 8123
        resources:
          requests:
            memory: "512Mi"
            cpu: "250m"
          limits:
            memory: "1Gi"
            cpu: "500m"
        env:
        - name: HA_URL
          value: "{ha_url}"
        - name: HA_TOKEN
          valueFrom:
            secretKeyRef:
              name: pilotsuite-secrets
              key: ha-token
        livenessProbe:
          httpGet:
            path: /api/v1/health
            port: 8123
          initialDelaySeconds: 30
          periodSeconds: 10
---
apiVersion: v1
kind: Service
metadata:
  name: pilotsuite-core
spec:
  selector:
    app: pilotsuite-core
  ports:
  - port: 80
    targetPort: 8123
  type: ClusterIP
'''

        # HACS manifest
        self._templates[DeployTarget.HACS] = '''
{{
  "name": "PilotSuite Core",
  "version": "{version}",
  "description": "AI-powered smart home automation",
  "url": "https://github.com/GreenhillEfka/pilotsuite-styx-ha",
  "requirements": ["aiohttp>=3.8", "numpy>=1.24"],
  "dependencies": ["http"],
  "codeowners": ["@GreenhillEfka"],
  "iot_class": "local_polling"
}}
'''

    def generate_deployment(self, config: DeployConfig) -> str:
        """Generate deployment configuration."""
        template = self._templates.get(config.target)
        if not template:
            raise ValueError(f"Unknown target: {config.target}")
        
        # Format template
        rendered = template.format(
            version=config.version,
            replicas=config.replicas,
            ha_url=config.env_vars.get("HA_URL", "http://homeassistant.local:8123"),
            ha_token=config.env_vars.get("HA_TOKEN", ""),
            ollama_url=config.env_vars.get("OLLAMA_URL", "http://localhost:11434"),
        )
        
        return rendered

    def save_deployment(self, config: DeployConfig, output_path: str):
        """Save deployment configuration to file."""
        rendered = self.generate_deployment(config)
        
        path = Path(output_path)
        path.parent.mkdir(parents=True, exist_ok=True)
        
        with open(path, 'w') as f:
            f.write(rendered)
        
        logger.info(f"Saved {config.target.value} deployment to {path}")

    def deploy_docker(self, version: str, output_dir: str = "deploy/docker") -> str:
        """Generate Docker deployment."""
        config = DeployConfig(
            target=DeployTarget.DOCKER,
            version=version,
            env_vars={
                "HA_URL": "http://homeassistant.local:8123",
                "HA_TOKEN": "your_token_here",
                "OLLAMA_URL": "http://localhost:11434",
            },
            volumes=["./data:/app/data", "./config:/app/config"]
        )
        
        output = f"{output_dir}/docker-compose.yml"
        self.save_deployment(config, output)
        return output

    def deploy_kubernetes(self, version: str, replicas: int = 2, output_dir: str = "deploy/k8s") -> str:
        """Generate Kubernetes deployment."""
        config = DeployConfig(
            target=DeployTarget.KUBERNETES,
            version=version,
            replicas=replicas,
            resources={"memory": "1Gi", "cpu": "500m"},
            env_vars={
                "HA_URL": "http://homeassistant.default.svc:8123",
            }
        )
        
        output = f"{output_dir}/deployment.yaml"
        self.save_deployment(config, output)
        return output

    def deploy_hacs(self, version: str, output_dir: str = "deploy/hacs") -> str:
        """Generate HACS manifest."""
        config = DeployConfig(
            target=DeployTarget.HACS,
            version=version
        )
        
        output = f"{output_dir}/hacs.json"
        self.save_deployment(config, output)
        return output

    def one_click_deploy(self, target: str, version: str) -> bool:
        """Execute one-click deployment."""
        try:
            if target == "docker":
                output = self.deploy_docker(version)
                logger.info(f"Docker deployment ready: {output}")
                # Would execute: docker-compose up -d
                return True
            
            elif target == "kubernetes":
                output = self.deploy_kubernetes(version)
                logger.info(f"Kubernetes deployment ready: {output}")
                # Would execute: kubectl apply -f {output}
                return True
            
            elif target == "hacs":
                output = self.deploy_hacs(version)
                logger.info(f"HACS manifest ready: {output}")
                return True
            
            return False
            
        except Exception as e:
            logger.error(f"Deployment failed: {e}")
            return False

    def get_stats(self) -> Dict[str, Any]:
        """Get deployment statistics."""
        return {
            "supported_targets": [t.value for t in DeployTarget],
            "templates_registered": len(self._templates),
            "deployments_created": len(self._deployments),
        }


# Global default deployment automation
default_deployment: Optional[DeploymentAutomation] = None


def init_deployment_automation() -> DeploymentAutomation:
    """Initialize global deployment automation."""
    global default_deployment
    default_deployment = DeploymentAutomation()
    return default_deployment
