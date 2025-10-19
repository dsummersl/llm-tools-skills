from pathlib import Path
from llm_tools_skills.toolbox import (
    parse_frontmatter,
    discover_skills,
    Skills,
)


class TestParseFrontmatter:
    """Test frontmatter parsing functionality."""

    def test_parse_simple_frontmatter(self):
        """Test parsing simple YAML frontmatter."""
        content = """---
name: test-skill
description: A test skill
---

# Content here"""
        frontmatter, remaining = parse_frontmatter(content)
        assert frontmatter == {
            "name": "test-skill",
            "description": "A test skill",
        }
        assert remaining.strip().startswith("# Content here")

    def test_parse_no_frontmatter(self):
        """Test content without frontmatter."""
        content = "# Just content"
        frontmatter, remaining = parse_frontmatter(content)
        assert frontmatter == {}
        assert remaining == "# Just content"

    def test_parse_incomplete_frontmatter(self):
        """Test content with incomplete frontmatter."""
        content = """---
name: test-skill
description: A test skill"""
        frontmatter, remaining = parse_frontmatter(content)
        assert frontmatter == {}
        assert remaining == content


class TestDiscoverSkills:
    """Test skill discovery functionality."""

    def test_discover_single_skill(self, tmp_path):
        """Test discovering a single skill in a directory."""
        skill_dir = tmp_path / "cooking-skill"
        skill_dir.mkdir()
        skill_file = skill_dir / "SKILL.md"
        skill_file.write_text("""---
name: cooking-best-practices
description: Reference for how I like to cook.
---

# Cooking Best Practices""")

        skills = discover_skills(tmp_path / "cooking-skill")
        assert len(skills) == 1
        assert "cooking-best-practices" in skills
        assert skills["cooking-best-practices"] == skill_dir

    def test_discover_skill_bundle(self, tmp_path):
        """Test discovering multiple skills in a bundle."""
        bundle_dir = tmp_path / "skill-bundle"
        bundle_dir.mkdir()

        # Create first skill
        skill1_dir = bundle_dir / "coding-skill"
        skill1_dir.mkdir()
        (skill1_dir / "SKILL.md").write_text("""---
name: coding-best-practices
description: Reference for how I like to write code.
---

# Coding""")

        # Create second skill
        skill2_dir = bundle_dir / "dancing-skill"
        skill2_dir.mkdir()
        (skill2_dir / "SKILL.md").write_text("""---
name: dance-best-practices
description: Reference for how I like to dance.
---

# Dancing""")

        skills = discover_skills(bundle_dir)
        assert len(skills) == 2
        assert "coding-best-practices" in skills
        assert "dance-best-practices" in skills

    def test_discover_nonexistent_path(self, tmp_path):
        """Test discovering skills from non-existent path."""
        skills = discover_skills(tmp_path / "nonexistent")
        assert len(skills) == 0


class TestSkillToolbox:
    """Test SkillToolbox functionality."""

    def test_init_with_single_skill(self):
        """Test initializing toolbox with a single skill."""
        fixtures_path = Path(__file__).parent / "fixtures" / "cooking-skill"
        toolbox = Skills(str(fixtures_path))

        assert len(toolbox.skills) == 1
        assert "cooking-best-practices" in toolbox.skills

    def test_init_with_skill_bundle(self):
        """Test initializing toolbox with skill bundle."""
        fixtures_path = Path(__file__).parent / "fixtures" / "skill-bundle"
        toolbox = Skills(str(fixtures_path))

        assert len(toolbox.skills) == 2
        assert "coding-best-practices" in toolbox.skills
        assert "dance-best-practices" in toolbox.skills

    def test_tools_generation(self):
        """Test dynamic tool generation from skills."""
        fixtures_path = Path(__file__).parent / "fixtures" / "cooking-skill"
        toolbox = Skills(str(fixtures_path))
        tools = list(toolbox.tools())

        assert len(tools) == 2  # Two tools per skill
        tool_names = {tool.name for tool in tools}
        assert "skills_cooking_best_practices_initialize" in tool_names
        assert "skills_cooking_best_practices_load_file" in tool_names

        # Check the initialize tool
        init_tool = next(t for t in tools if t.name == "skills_cooking_best_practices_initialize")
        assert "how I like to cook" in init_tool.description
        assert "CALL THIS FIRST" in init_tool.description
        assert "SKILL.md" in init_tool.description

    def test_tools_generation_bundle(self):
        """Test dynamic tool generation from skill bundle."""
        fixtures_path = Path(__file__).parent / "fixtures" / "skill-bundle"
        toolbox = Skills(str(fixtures_path))
        tools = list(toolbox.tools())

        assert len(tools) == 4  # Two tools per skill, 2 skills
        tool_names = {tool.name for tool in tools}
        assert "skills_coding_best_practices_initialize" in tool_names
        assert "skills_coding_best_practices_load_file" in tool_names
        assert "skills_dance_best_practices_initialize" in tool_names
        assert "skills_dance_best_practices_load_file" in tool_names

    def test_tool_execute_default(self):
        """Test executing a tool to load default SKILL.md."""
        fixtures_path = Path(__file__).parent / "fixtures" / "cooking-skill"
        toolbox = Skills(str(fixtures_path))
        tools = list(toolbox.tools())

        # Get the initialize tool
        init_tool = next(t for t in tools if t.name.endswith("_initialize"))

        result = init_tool.implementation()
        assert "Cooking Best Practices" in result
        assert "name: cooking-best-practices" in result
        assert "Available additional files" in result

    def test_tool_execute_with_path(self):
        """Test executing a tool to load a specific file."""
        fixtures_path = Path(__file__).parent / "fixtures" / "cooking-skill"
        toolbox = Skills(str(fixtures_path))
        tools = list(toolbox.tools())

        # First initialize the skill
        init_tool = next(t for t in tools if t.name.endswith("_initialize"))
        init_tool.implementation()

        # Then load a specific file
        load_file_tool = next(t for t in tools if t.name.endswith("_load_file"))
        result = load_file_tool.implementation(filename="kitchen-layout.md")
        assert "Kitchen Layout" in result
        assert "Silverware and Utensils" in result

    def test_tool_execute_nonexistent_file(self):
        """Test executing a tool with non-existent file."""
        fixtures_path = Path(__file__).parent / "fixtures" / "cooking-skill"
        toolbox = Skills(str(fixtures_path))
        tools = list(toolbox.tools())

        load_file_tool = next(t for t in tools if t.name.endswith("_load_file"))
        result = load_file_tool.implementation(filename="nonexistent.md")
        assert "WARNING" in result
        assert "not found" in result

    def test_tool_execute_path_traversal(self):
        """Test security: prevent path traversal attacks."""
        fixtures_path = Path(__file__).parent / "fixtures" / "cooking-skill"
        toolbox = Skills(str(fixtures_path))
        tools = list(toolbox.tools())

        load_file_tool = next(t for t in tools if t.name.endswith("_load_file"))
        result = load_file_tool.implementation(filename="../../../etc/passwd")
        assert "ERROR" in result
        assert "outside the skill directory" in result

    def test_tool_load_file_without_loading_skill_first(self):
        """Test that load_file shows warning when skill not loaded first."""
        fixtures_path = Path(__file__).parent / "fixtures" / "cooking-skill"
        toolbox = Skills(str(fixtures_path))
        tools = list(toolbox.tools())

        # Load a file without loading the skill first
        load_file_tool = next(t for t in tools if t.name.endswith("_load_file"))
        result = load_file_tool.implementation(filename="kitchen-layout.md")

        # Should contain warning about not loading skill first
        assert "WARNING: You did not load the skill first" in result
        # Should contain the skill data
        assert "Cooking Best Practices" in result
        assert "Available additional files" in result
        # Should also contain the requested file
        assert "Kitchen Layout" in result
        assert "Silverware and Utensils" in result

    def test_tool_parameters(self):
        """Test tool parameters are correctly defined."""
        fixtures_path = Path(__file__).parent / "fixtures" / "cooking-skill"
        toolbox = Skills(str(fixtures_path))
        tools = list(toolbox.tools())

        # Test the initialize tool (no parameters)
        init_tool = next(t for t in tools if t.name.endswith("_initialize"))
        assert isinstance(init_tool.input_schema, dict)
        assert init_tool.input_schema == {}  # No parameters

        # Test the load_file tool (has filename parameter)
        load_file_tool = next(t for t in tools if t.name.endswith("_load_file"))
        assert isinstance(load_file_tool.input_schema, dict)
        assert load_file_tool.input_schema["type"] == "object"
        assert "properties" in load_file_tool.input_schema
        assert "filename" in load_file_tool.input_schema["properties"]

        # Verify the filename field
        filename_field = load_file_tool.input_schema["properties"]["filename"]
        assert "description" in filename_field

    def test_tool_initialize_called_multiple_times(self):
        """Test that initialize tool only loads once even if called multiple times."""
        fixtures_path = Path(__file__).parent / "fixtures" / "cooking-skill"
        toolbox = Skills(str(fixtures_path))
        tools = list(toolbox.tools())

        init_tool = next(t for t in tools if t.name.endswith("_initialize"))

        # First call should load the skill
        result1 = init_tool.implementation()
        assert "Cooking Best Practices" in result1
        assert "Available additional files" in result1

        # Second call should return "already loaded" message
        result2 = init_tool.implementation()
        assert "already loaded" in result2
        assert "Cooking Best Practices" not in result2  # Should not include full content again

    def test_path_with_tilde_expansion(self, tmp_path, monkeypatch):
        """Test that ~ is expanded to home directory."""
        # Create a skill in a temp directory
        skill_dir = tmp_path / "test-skill"
        skill_dir.mkdir()
        skill_file = skill_dir / "SKILL.md"
        skill_file.write_text("""---
name: test-skill
description: A test skill
---

# Test Skill""")

        # Mock the home directory to be tmp_path
        monkeypatch.setenv("HOME", str(tmp_path))

        # Use ~ in the path
        toolbox = Skills("~/test-skill")
        assert len(toolbox.skills) == 1
        assert "test-skill" in toolbox.skills

    def test_path_not_directory_raises_error(self, tmp_path):
        """Test that passing a file path raises ValueError."""
        # Create a file instead of a directory
        file_path = tmp_path / "notadir.txt"
        file_path.write_text("some content")

        # Should raise ValueError
        import pytest
        with pytest.raises(ValueError, match="Path must be a directory"):
            Skills(str(file_path))
