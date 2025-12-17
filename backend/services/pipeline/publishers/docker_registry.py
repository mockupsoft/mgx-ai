# -*- coding: utf-8 -*-

from dataclasses import dataclass

from backend.services.pipeline.utils import command_exists, run_command


@dataclass
class DockerRegistryPublishResult:
    registry: str
    image_ref: str
    success: bool
    logs: str


class DockerRegistryPublisher:
    """Publish images to Docker registries (Docker Hub, ECR, GCR, ACR, GHCR)."""

    async def login_ecr(self, *, registry: str, region: str) -> DockerRegistryPublishResult:
        if not command_exists("aws"):
            return DockerRegistryPublishResult(
                registry=registry,
                image_ref="",
                success=False,
                logs="aws CLI not found in PATH",
            )
        if not command_exists("docker"):
            return DockerRegistryPublishResult(
                registry=registry,
                image_ref="",
                success=False,
                logs="docker CLI not found in PATH",
            )

        login = await run_command(
            [
                "sh",
                "-c",
                f"aws ecr get-login-password --region {region} | docker login --username AWS --password-stdin {registry}",
            ]
        )

        return DockerRegistryPublishResult(
            registry=registry,
            image_ref="",
            success=login.returncode == 0,
            logs=(login.stdout + "\n" + login.stderr).strip(),
        )

    async def push(self, *, image_ref: str, registry: str) -> DockerRegistryPublishResult:
        if not command_exists("docker"):
            return DockerRegistryPublishResult(
                registry=registry,
                image_ref=image_ref,
                success=False,
                logs="docker CLI not found in PATH",
            )

        full_ref = self._with_registry(image_ref, registry)

        tag = await run_command(["docker", "tag", image_ref, full_ref])
        if tag.returncode != 0:
            return DockerRegistryPublishResult(
                registry=registry,
                image_ref=full_ref,
                success=False,
                logs=(tag.stdout + "\n" + tag.stderr).strip(),
            )

        push = await run_command(["docker", "push", full_ref])

        return DockerRegistryPublishResult(
            registry=registry,
            image_ref=full_ref,
            success=push.returncode == 0,
            logs=(push.stdout + "\n" + push.stderr).strip(),
        )

    def _with_registry(self, image_ref: str, registry: str) -> str:
        if not registry:
            return image_ref
        if "/" in image_ref and image_ref.split("/")[0].count(".") > 0:
            return image_ref
        return f"{registry.rstrip('/')}/{image_ref}"

    @staticmethod
    def ecr_registry(account_id: str, region: str) -> str:
        return f"{account_id}.dkr.ecr.{region}.amazonaws.com"
