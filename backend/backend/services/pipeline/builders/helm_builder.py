# -*- coding: utf-8 -*-

import logging
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, Optional

import yaml

from backend.services.pipeline.utils import command_exists, run_command

logger = logging.getLogger(__name__)


@dataclass
class HelmChartResult:
    chart_path: str
    version: str
    validated: bool
    validation_output: Optional[str] = None


class HelmBuilder:
    """Generate a Helm chart for the application."""

    async def generate_chart(self, project_name: str, version: str, values: Dict[str, Any], *, output_dir: str) -> HelmChartResult:
        out = Path(output_dir)
        chart_dir = out / project_name
        templates_dir = chart_dir / "templates"
        templates_dir.mkdir(parents=True, exist_ok=True)

        (chart_dir / "Chart.yaml").write_text(
            yaml.safe_dump(
                {
                    "apiVersion": "v2",
                    "name": project_name,
                    "description": f"Helm chart for {project_name}",
                    "type": "application",
                    "version": version,
                    "appVersion": version,
                },
                sort_keys=False,
            ),
            encoding="utf-8",
        )

        (chart_dir / "values.yaml").write_text(
            yaml.safe_dump(values, sort_keys=False),
            encoding="utf-8",
        )

        (templates_dir / "_helpers.tpl").write_text(
            """{{- define \"app.name\" -}}\n{{ .Chart.Name }}\n{{- end -}}\n\n{{- define \"app.fullname\" -}}\n{{ printf \"%s-%s\" .Release.Name (include \"app.name\" .) | trunc 63 | trimSuffix \"-\" }}\n{{- end -}}\n""",
            encoding="utf-8",
        )

        (templates_dir / "deployment.yaml").write_text(
            """apiVersion: apps/v1\nkind: Deployment\nmetadata:\n  name: {{ include \"app.fullname\" . }}\n  labels:\n    app.kubernetes.io/name: {{ include \"app.name\" . }}\nspec:\n  replicas: {{ .Values.replicaCount }}\n  selector:\n    matchLabels:\n      app.kubernetes.io/name: {{ include \"app.name\" . }}\n  template:\n    metadata:\n      labels:\n        app.kubernetes.io/name: {{ include \"app.name\" . }}\n    spec:\n      serviceAccountName: {{ include \"app.fullname\" . }}\n      containers:\n        - name: app\n          image: \"{{ .Values.image.repository }}:{{ .Values.image.tag }}\"\n          imagePullPolicy: {{ .Values.image.pullPolicy }}\n          ports:\n            - name: http\n              containerPort: {{ .Values.service.port }}\n          envFrom:\n            - configMapRef:\n                name: {{ include \"app.fullname\" . }}\n          resources: {{- toYaml .Values.resources | nindent 12 }}\n          readinessProbe:\n            httpGet:\n              path: /health\n              port: http\n            initialDelaySeconds: 5\n            periodSeconds: 10\n          livenessProbe:\n            httpGet:\n              path: /health\n              port: http\n            initialDelaySeconds: 10\n            periodSeconds: 10\n""",
            encoding="utf-8",
        )

        (templates_dir / "service.yaml").write_text(
            """apiVersion: v1\nkind: Service\nmetadata:\n  name: {{ include \"app.fullname\" . }}\nspec:\n  type: {{ .Values.service.type }}\n  selector:\n    app.kubernetes.io/name: {{ include \"app.name\" . }}\n  ports:\n    - name: http\n      port: {{ .Values.service.port }}\n      targetPort: http\n""",
            encoding="utf-8",
        )

        (templates_dir / "configmap.yaml").write_text(
            """apiVersion: v1\nkind: ConfigMap\nmetadata:\n  name: {{ include \"app.fullname\" . }}\ndata:\n{{- range $k, $v := .Values.env }}\n  {{ $k }}: {{ $v | quote }}\n{{- end }}\n""",
            encoding="utf-8",
        )

        (templates_dir / "secret.yaml").write_text(
            """apiVersion: v1\nkind: Secret\nmetadata:\n  name: {{ include \"app.fullname\" . }}-secrets\ntype: Opaque\ndata: {}\n""",
            encoding="utf-8",
        )

        (templates_dir / "ingress.yaml").write_text(
            """{{- if .Values.ingress.enabled -}}\napiVersion: networking.k8s.io/v1\nkind: Ingress\nmetadata:\n  name: {{ include \"app.fullname\" . }}\nspec:\n  rules:\n    - host: {{ .Values.ingress.host | quote }}\n      http:\n        paths:\n          - path: /\n            pathType: Prefix\n            backend:\n              service:\n                name: {{ include \"app.fullname\" . }}\n                port:\n                  number: {{ .Values.service.port }}\n{{- end }}\n""",
            encoding="utf-8",
        )

        (templates_dir / "hpa.yaml").write_text(
            """{{- if .Values.autoscaling.enabled -}}\napiVersion: autoscaling/v2\nkind: HorizontalPodAutoscaler\nmetadata:\n  name: {{ include \"app.fullname\" . }}\nspec:\n  scaleTargetRef:\n    apiVersion: apps/v1\n    kind: Deployment\n    name: {{ include \"app.fullname\" . }}\n  minReplicas: {{ .Values.autoscaling.minReplicas }}\n  maxReplicas: {{ .Values.autoscaling.maxReplicas }}\n  metrics:\n    - type: Resource\n      resource:\n        name: cpu\n        target:\n          type: Utilization\n          averageUtilization: {{ .Values.autoscaling.targetCPUUtilizationPercentage }}\n{{- end }}\n""",
            encoding="utf-8",
        )

        (templates_dir / "rbac.yaml").write_text(
            """apiVersion: v1\nkind: ServiceAccount\nmetadata:\n  name: {{ include \"app.fullname\" . }}\n---\napiVersion: rbac.authorization.k8s.io/v1\nkind: Role\nmetadata:\n  name: {{ include \"app.fullname\" . }}\nrules:\n  - apiGroups: [\"\"]\n    resources: [\"configmaps\", \"secrets\"]\n    verbs: [\"get\"]\n---\napiVersion: rbac.authorization.k8s.io/v1\nkind: RoleBinding\nmetadata:\n  name: {{ include \"app.fullname\" . }}\nsubjects:\n  - kind: ServiceAccount\n    name: {{ include \"app.fullname\" . }}\nroleRef:\n  kind: Role\n  name: {{ include \"app.fullname\" . }}\n  apiGroup: rbac.authorization.k8s.io\n""",
            encoding="utf-8",
        )

        validated, output = await self._validate(chart_dir)

        return HelmChartResult(
            chart_path=str(chart_dir),
            version=version,
            validated=validated,
            validation_output=output,
        )

    async def _validate(self, chart_dir: Path) -> tuple[bool, Optional[str]]:
        if not command_exists("helm"):
            return False, "helm not available; chart validation skipped"

        result = await run_command(["helm", "lint", str(chart_dir)])
        return result.returncode == 0, (result.stdout + "\n" + result.stderr).strip()
