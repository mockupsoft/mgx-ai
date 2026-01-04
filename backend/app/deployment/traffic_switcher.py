# -*- coding: utf-8 -*-

from __future__ import annotations

import argparse
import json
import subprocess
from dataclasses import dataclass
from typing import Literal


Color = Literal["blue", "green"]


@dataclass(frozen=True)
class TrafficSwitchConfig:
    namespace: str = "production"
    service_name: str = "mgx-agent-lb"
    app_label: str = "mgx-agent"


class TrafficSwitcher:
    def __init__(self, config: TrafficSwitchConfig | None = None) -> None:
        self._config = config or TrafficSwitchConfig()

    def switch(self, target: Color) -> None:
        patch = {
            "spec": {
                "selector": {
                    "app": self._config.app_label,
                    "color": target,
                }
            }
        }

        self._kubectl(
            "patch",
            "service",
            self._config.service_name,
            "-n",
            self._config.namespace,
            "--type",
            "merge",
            "-p",
            json.dumps(patch),
        )

    def _kubectl(self, *args: str) -> None:
        cmd = ["kubectl", *args]
        subprocess.run(cmd, check=True)


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(prog="traffic_switcher")
    sub = parser.add_subparsers(dest="command", required=True)

    switch = sub.add_parser("switch", help="Switch production traffic")
    switch.add_argument("--target", choices=["blue", "green"], required=True)
    switch.add_argument("--namespace", default="production")
    switch.add_argument("--service", default="mgx-agent-lb")

    sub.add_parser("serve", help="Placeholder mode for running in-cluster")

    return parser.parse_args()


def main() -> None:
    args = _parse_args()

    if args.command == "serve":
        # Intentionally minimal. In-cluster HTTP API can be added if needed.
        return

    config = TrafficSwitchConfig(namespace=args.namespace, service_name=args.service)
    switcher = TrafficSwitcher(config)

    target: Color = args.target
    switcher.switch(target)


if __name__ == "__main__":
    main()
