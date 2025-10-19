import llm
from pathlib import Path
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


class LoadFileSchema(BaseModel):
    filename: str = Field(
        description="The filename to load from the skill directory (e.g., 'kitchen-layout.md')."
    )

class Skills(llm.Toolbox):  # type: ignore[no-untyped-call]
    """
    Make Claude skills available as tools.
    """

    def __init__(self, skills_path: str):
        """
        Initialize the SkillToolbox.

        Args:
            skills_path: Optional path to skills directory. If not provided,
                       looks for skills in default locations.
        """
        super().__init__()

        self.skills: dict[str, Path] = {}
        self._loaded_skills: set[str] = set()  # Track which skills have been loaded

        path = Path(skills_path)
        discovered_skills = discover_skills(path)
        for skill_name, skill_dir in discovered_skills.items():
            self.skills[skill_name] = skill_dir
            # Create two tools per skill
            load_tool, load_file_tool = self._make_skill_tools(skill_name, skill_dir)
            self.add_tool(load_tool)
            self.add_tool(load_file_tool)

    def _make_skill_tools(self, skill_name: str, skill_dir: Path) -> tuple[llm.Tool, llm.Tool]:
        """
        Create two tools for a skill: one to load the skill, one to load additional files.

        Returns:
            Tuple of (load_skill_tool, load_file_tool)
        """
        # Read the frontmatter to get description
        skill_file = skill_dir / "SKILL.md"
        content = skill_file.read_text()
        frontmatter, _ = parse_frontmatter(content)
        base_description = frontmatter.get("description", f"Load the {skill_name} skill")

        # Create sanitized tool names
        tool_name = skill_name.replace('-', '_')
        initialize_tool_name = f"{tool_name}_initialize"
        load_file_tool_name = f"{tool_name}_load_file"

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
            # Check if already loaded
            if skill_name in self._loaded_skills:
                return f"Skill '{skill_name}' is already loaded. Use {load_file_tool_name} to load additional files."

            self._loaded_skills.add(skill_name)
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

            # Check if the skill has been loaded first
            if skill_name not in self._loaded_skills:
                output_parts.append("⚠️  WARNING: You did not load the skill first. Here is the skill data:\n")
                output_parts.append("-" * 80)
                self._loaded_skills.add(skill_name)
                skill_content = skill_file.read_text()
                files_list = list_available_files()
                output_parts.append(skill_content + files_list)
                output_parts.append("-" * 80)
                output_parts.append("")

            # Now try to load the requested file
            file_path = skill_dir / filename

            # Security check: ensure the file is within the skill directory
            try:
                file_path.resolve().relative_to(skill_dir.resolve())
            except ValueError:
                output_parts.append(f"⚠️  ERROR: Path '{filename}' is outside the skill directory")
                return "\n".join(output_parts)

            if not file_path.exists():
                output_parts.append(f"⚠️  WARNING: File '{filename}' not found in skill '{skill_name}'")
                return "\n".join(output_parts)

            # File exists, add it to the output
            if output_parts:
                output_parts.append(f"Requested file '{filename}':\n")

            output_parts.append(file_path.read_text())
            return "\n".join(output_parts)

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

        return initialize_tool, load_file_tool
