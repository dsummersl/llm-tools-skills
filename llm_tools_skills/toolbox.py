import llm
from pathlib import Path
from collections.abc import Callable
from pydantic import BaseModel, Field



def parse_frontmatter(content: str) -> tuple[dict[str, str], str]:
    """
    Parse YAML frontmatter from skill content.

    Returns:
        Tuple of (frontmatter dict, remaining content)
    """
    # Check for frontmatter delimiter
    if not content.startswith("---"):
        return {}, content

    # Find the closing delimiter
    parts = content.split("---", 2)
    if len(parts) < 3:
        return {}, content

    # Parse frontmatter (simple key: value pairs)
    frontmatter = {}
    frontmatter_text = parts[1].strip()
    for line in frontmatter_text.split("\n"):
        line = line.strip()
        if ":" in line:
            key, value = line.split(":", 1)
            frontmatter[key.strip()] = value.strip()

    # Return frontmatter and remaining content
    remaining_content = parts[2]
    return frontmatter, remaining_content


def discover_skills(path: Path) -> dict[str, Path]:
    """
    Discover skills from a given path.

    Args:
        path: Path to a skill directory, bundle of skills

    Returns:
        Dictionary mapping skill names to their directory paths
    """
    skills: dict[str, Path] = {}

    if not path.exists():
        return skills

    # Check if the path itself contains a SKILL.md
    skill_file = path / "SKILL.md"
    if skill_file.exists():
        # Single skill directory
        content = skill_file.read_text()
        frontmatter, _ = parse_frontmatter(content)
        if "name" in frontmatter:
            skills[frontmatter["name"]] = path
    else:
        # Look for subdirectories with SKILL.md
        if path.is_dir():
            for subdir in path.iterdir():
                if subdir.is_dir():
                    skill_file = subdir / "SKILL.md"
                    if skill_file.exists():
                        content = skill_file.read_text()
                        frontmatter, _ = parse_frontmatter(content)
                        if "name" in frontmatter:
                            skills[frontmatter["name"]] = subdir

    return skills


def build_skill_tool_names(skill_name: str) -> tuple[str, str]:
    initialize_tool_name = skill_name
    load_file_tool_name = f"{skill_name}_load_file"
    return initialize_tool_name, load_file_tool_name


def make_skill_handlers(
    skill_name: str,
    skill_dir: Path,
    loaded_skills: set[str],
) -> tuple[str, Callable[[], str], Callable[[str], str]]:
    skill_file = skill_dir / "SKILL.md"
    content = skill_file.read_text()
    frontmatter, _ = parse_frontmatter(content)
    base_description = frontmatter.get("description", f"Load the {skill_name} skill")

    initialize_tool_name, load_file_tool_name = build_skill_tool_names(skill_name)

    def list_available_files() -> str:
        """List all markdown files in the skill directory."""
        files = []
        for file in skill_dir.iterdir():
            if file.is_file() and file.suffix == ".md" and file.name != "SKILL.md":
                files.append(file.name)

        if files:
            return "\n\nAvailable additional files:\n" + "\n".join(f"  - {f}" for f in sorted(files))
        return "\n\nNo additional files available in this skill."

    def load_skill() -> str:
        """Load the main SKILL.md file and list available files."""
        if skill_name in loaded_skills:
            return (
                f"Skill '{skill_name}' is already loaded. "
                f"Use {load_file_tool_name} to load additional files."
            )

        loaded_skills.add(skill_name)
        skill_content = skill_file.read_text()
        files_list = list_available_files()
        return skill_content + files_list

    def load_file(filename: str) -> str:
        """
        Load a specific file from the skill directory.

        Args:
            filename: The filename to load from the skill directory.

        Returns:
            The content of the requested file, with warnings if applicable.
        """
        output_parts = []

        if skill_name not in loaded_skills:
            output_parts.append("⚠️  WARNING: You did not load the skill first. Here is the skill data:\n")
            output_parts.append("-" * 80)
            loaded_skills.add(skill_name)
            skill_content = skill_file.read_text()
            files_list = list_available_files()
            output_parts.append(skill_content + files_list)
            output_parts.append("-" * 80)
            output_parts.append("")

        file_path = skill_dir / filename

        try:
            file_path.resolve().relative_to(skill_dir.resolve())
        except ValueError:
            output_parts.append(f"⚠️  ERROR: Path '{filename}' is outside the skill directory")
            return "\n".join(output_parts)

        if not file_path.exists():
            output_parts.append(f"⚠️  WARNING: File '{filename}' not found in skill '{skill_name}'")
            return "\n".join(output_parts)

        if output_parts:
            output_parts.append(f"Requested file '{filename}':\n")

        output_parts.append(file_path.read_text())
        return "\n".join(output_parts)

    return base_description, load_skill, load_file


class LoadFileSchema(BaseModel):
    filename: str = Field(
        description="The filename to load from the skill directory (e.g., 'kitchen-layout.md')."
    )


class InitializeSchema(BaseModel):
    tool_name: str = Field(
        description="The tool name of the skill to initialize (e.g., 'cooking-best-practices')."
    )


class Skills(llm.Toolbox):  # type: ignore[no-untyped-call]
    """
    Make Claude skills available as tools.
    """

    def __init__(self, skills_path: str):
        """
        Initialize the SkillToolbox.

        Args:
            skills_path: Path to skills directory. Supports ~ for home directory.

        Raises:
            ValueError: If the path is not a directory.
        """
        super().__init__()

        self.skills: dict[str, Path] = {}
        self._loaded_skills: set[str] = set()  # Track which skills have been loaded
        self._skill_loaders: dict[str, Callable[[], str]] = {}
        self._skill_descriptions: dict[str, str] = {}

        # Expand ~ and convert to Path
        path = Path(skills_path).expanduser()

        # Validate that path is a directory
        if path.exists() and not path.is_dir():
            raise ValueError(f"Path must be a directory, got: {skills_path}")

        discovered_skills = discover_skills(path)
        for skill_name, skill_dir in discovered_skills.items():
            self.skills[skill_name] = skill_dir
            # Create two tools per skill
            load_tool, load_file_tool, load_skill, base_description = self._make_skill_tools(skill_name, skill_dir)
            self._skill_loaders[skill_name] = load_skill
            self._skill_descriptions[skill_name] = base_description
            self.add_tool(load_tool)
            self.add_tool(load_file_tool)

        if self.skills:
            self.add_tool(self._make_initialize_tool())

    def _make_skill_tools(
        self,
        skill_name: str,
        skill_dir: Path,
    ) -> tuple[llm.Tool, llm.Tool, Callable[[], str], str]:
        """
        Create two tools for a skill: one to load the skill, one to load additional files.

        Returns:
            Tuple of (load_skill_tool, load_file_tool, load_skill_handler, base_description)
        """
        base_description, load_skill, load_file = make_skill_handlers(
            skill_name,
            skill_dir,
            self._loaded_skills,
        )
        initialize_tool_name, load_file_tool_name = build_skill_tool_names(skill_name)

        # Tool 1: Initialize/load the skill
        initialize_tool = llm.Tool(
            name=initialize_tool_name,
            description=f"**CALL THIS FIRST** - {base_description} Initializes the skill by loading SKILL.md and listing available additional files. Only needs to be called once.",
            input_schema={},  # No parameters
            implementation=load_skill,
            plugin="llm_tools_skills"
        )

        # Tool 2: Load a specific file
        load_file_tool = llm.Tool(
            name=load_file_tool_name,
            description=f"Load a specific file from the {skill_name} skill directory. Must call {initialize_tool_name} first to see available files.",
            input_schema=LoadFileSchema.model_json_schema(),
            implementation=load_file,
            plugin="llm_tools_skills"
        )

        return initialize_tool, load_file_tool, load_skill, base_description

    def _make_initialize_tool(self) -> llm.Tool:
        def format_valid_tool_names() -> str:
            lines = []
            for name in sorted(self.skills):
                description = self._skill_descriptions.get(name)
                if description:
                    lines.append(f"- {name}: {description}")
                else:
                    lines.append(f"- {name}")
            return "\n".join(lines)

        def initialize(tool_name: str) -> str:
            if tool_name not in self._skill_loaders:
                valid = ", ".join(sorted(self._skill_loaders)) or "none"
                raise ValueError(f"Unknown tool name '{tool_name}'. Valid tool names: {valid}")
            return self._skill_loaders[tool_name]()

        return llm.Tool(
            name="initialize",
            description=(
                "Initialize a discovered skill by tool name and return its SKILL.md contents. "
                "Valid tool names:\n"
                f"{format_valid_tool_names()}"
            ),
            input_schema=InitializeSchema.model_json_schema(),
            implementation=initialize,
            plugin="llm_tools_skills",
        )
