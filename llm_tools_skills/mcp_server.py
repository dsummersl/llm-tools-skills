import logging
from pathlib import Path
from typing import Any, Callable, Literal, cast

import click
from mcp import types as mcp_types
from mcp.server.fastmcp import FastMCP
from pydantic import AnyUrl

from .toolbox import discover_skills, parse_frontmatter

logger = logging.getLogger(__name__)


def make_mcp(skills_path: str) -> FastMCP:
    mcp = FastMCP("skills", stateless_http=True, json_response=True)

    path = Path(skills_path).expanduser()
    if path.exists() and not path.is_dir():
        raise ValueError(f"Path must be a directory, got: {skills_path}")

    skills = discover_skills(path)
    loaded_skills: set[str] = set()
    available_resources: dict[str, set[str]] = {}
    skill_descriptions: dict[str, str] = {}

    for skill_name, skill_dir in skills.items():
        skill_file = skill_dir / "SKILL.md"
        content = skill_file.read_text()
        frontmatter, _ = parse_frontmatter(content)
        description = frontmatter.get("description")
        if description:
            skill_descriptions[skill_name] = description

    def list_skill_files(skill_dir: Path) -> set[str]:
        files: set[str] = set()
        for file in skill_dir.iterdir():
            if file.is_file() and file.suffix == ".md" and file.name != "SKILL.md":
                files.add(file.name)
        return files

    def format_valid_tool_names() -> str:
        if not skills:
            return "No skills discovered."
        lines = []
        for name in sorted(skills):
            description = skill_descriptions.get(name)
            if description:
                lines.append(f"- {name}: {description}")
            else:
                lines.append(f"- {name}")
        return "\n".join(lines)

    def load_skill(tool_name: str) -> tuple[str, list[str]]:
        """Load a skill's SKILL.md by tool name.

        Returns the contents of the SKILL.md file, and a list of available resources associated with this skill.
        """
        if tool_name not in skills:
            valid = ", ".join(sorted(skills)) or "none"
            raise ValueError(f"Unknown tool name '{tool_name}'. Valid tool names: {valid}")

        skill_dir = skills[tool_name]
        skill_file = skill_dir / "SKILL.md"
        loaded_skills.add(tool_name)
        available_resources[tool_name] = list_skill_files(skill_dir)
        return skill_file.read_text(), sorted(available_resources[tool_name])

    load_skill.__doc__ = (
        "Load a skill and return its SKILL.md contents and its available resources associated with the skill.\n"
        "Valid tool names:\n"
        f"{format_valid_tool_names()}"
    )
    mcp.tool(description=load_skill.__doc__)(load_skill)

    @mcp.resource("file://{skill}/{name}")
    def load_skill_file(skill: str, name: str) -> str:
        if skill not in skills:
            raise ValueError(f"Unknown tool name '{skill}'.")
        if skill not in loaded_skills:
            raise ValueError(f"Skill '{skill}' is not loaded. Call load_skill first.")

        skill_dir = skills[skill]
        file_path = skill_dir / name
        try:
            file_path.resolve().relative_to(skill_dir.resolve())
        except ValueError as exc:
            raise ValueError(f"Path '{name}' is outside the skill directory.") from exc

        if not file_path.exists():
            raise ValueError(f"File '{name}' not found in skill '{skill}'.")

        return file_path.read_text()

    list_resources_decorator = cast(
        Callable[[Callable[..., Any]], Callable[..., Any]],
        mcp._mcp_server.list_resources(),  # type: ignore[no-untyped-call]
    )

    @list_resources_decorator
    async def list_resources() -> list[mcp_types.Resource]:
        resources: list[mcp_types.Resource] = []
        for skill_name in sorted(available_resources):
            for filename in sorted(available_resources[skill_name]):
                uri = f"file://{skill_name}/{filename}"
                resources.append(
                    mcp_types.Resource(
                        name=f"{skill_name}/{filename}",
                        uri=AnyUrl(uri),
                        description=f"Additional file from skill '{skill_name}'.",
                    )
                )
        return resources

    return mcp


@click.command()
@click.option(
    "--transport",
    type=click.Choice(["stdio", "sse", "streamable-http"]),
    default="stdio",
    help="Specify the transport method (stdio, sse, streamable-http)",
)
@click.option(
    "--skills-path",
    type=click.Path(file_okay=False, dir_okay=True, path_type=Path),
    required=True,
    help="Path to a skill directory or a bundle of skills",
)
def cli(transport: str, skills_path: Path) -> None:
    logging.basicConfig(level=logging.INFO)
    transport_literal = cast(Literal["stdio", "sse", "streamable-http"], transport)
    make_mcp(str(skills_path)).run(transport=transport_literal)


if __name__ == "__main__":
    cli()
