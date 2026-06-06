from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from jinja2 import Template

from dashsys_agent.api.sanitize import redact_payload
from dashsys_agent.config import Settings
from dashsys_agent.runtime.trajectory import validate_trajectory
from dashsys_agent.utils import has_secret, stable_slug, write_json


class ArtifactWriter:
    def __init__(self, settings: Settings) -> None:
        self.settings = settings
        self.template_path = settings.repo_root / "prompts" / "system_prompt_template.md.j2"

    def artifact_id(self, query: str, sample_id: str | None = None) -> str:
        return sample_id or stable_slug(query)

    def write(
        self,
        query: str,
        metadata: dict[str, Any],
        trajectory: dict[str, Any],
        answer: str,
        sample_id: str | None = None,
    ) -> dict[str, Path]:
        metadata = redact_payload(metadata, self.settings)
        trajectory = redact_payload(trajectory, self.settings)
        answer = str(redact_payload(answer, self.settings))
        validate_trajectory(trajectory)
        artifact_id = self.artifact_id(query, sample_id)
        prompt_template = Template(self.template_path.read_text(encoding="utf-8"))
        prompt = prompt_template.render(
            query=query,
            metadata_json=json.dumps(metadata, indent=2, ensure_ascii=False),
        )
        if has_secret(prompt) or has_secret(json.dumps(trajectory, ensure_ascii=False)):
            raise ValueError("Refusing to write artifacts with secret-like content")
        output = self.settings.output_dir
        paths = {
            "metadata": output / "metadata" / f"{artifact_id}.json",
            "prompt": output / "prompts" / f"{artifact_id}.md",
            "trajectory": output / "trajectories" / f"{artifact_id}.json",
            "answer": output / "answers" / f"{artifact_id}.txt",
        }
        write_json(paths["metadata"], metadata)
        paths["prompt"].parent.mkdir(parents=True, exist_ok=True)
        paths["prompt"].write_text(prompt, encoding="utf-8")
        write_json(paths["trajectory"], trajectory)
        paths["answer"].parent.mkdir(parents=True, exist_ok=True)
        paths["answer"].write_text(answer, encoding="utf-8")
        return paths
