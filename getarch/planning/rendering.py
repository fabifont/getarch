"""Rendering of an InstallPlan to human text and machine JSON."""

from __future__ import annotations

import json

from getarch.domain.plan import InstallPlan, PlannedStep


def render_text(plan: InstallPlan) -> str:
    lines: list[str] = [f"Install plan (schema {plan.version})", ""]
    for i, step in enumerate(plan.steps, start=1):
        flag = " [DESTRUCTIVE]" if step.destructive else ""
        lines.append(f"{i:>2}. [{step.phase.value}] {step.title}{flag}")
        lines.append(f"     {step.description}")
        for cmd in step.commands:
            lines.append(f"     $ {cmd.describe()}")
        lines.append("")
    return "\n".join(lines)


def render_json(plan: InstallPlan) -> str:
    return json.dumps(_plan_to_dict(plan), indent=2, sort_keys=False)


def _plan_to_dict(plan: InstallPlan) -> dict[str, object]:
    return {
        "version": plan.version,
        "destructive": plan.has_destructive_steps,
        "steps": [_step_to_dict(s) for s in plan.steps],
    }


def _step_to_dict(step: PlannedStep) -> dict[str, object]:
    return {
        "id": step.id,
        "title": step.title,
        "phase": step.phase.value,
        "destructive": step.destructive,
        "description": step.description,
        "commands": [
            {
                "argv": list(c.argv),
                "chroot": c.chroot,
                "sensitive": c.sensitive,
                "input": "***" if c.sensitive and c.input else c.input,
                "description": c.description,
            }
            for c in step.commands
        ],
    }
