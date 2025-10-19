# 2. Claude Skills Integration

Date: 2025-10-19

## Status

Accepted

## Context

The LLM CLI tool (https://llm.datasette.io/) provides a toolbox system (https://llm.datasette.io/en/stable/tools.html) that allows LLMs to use tools during conversations. Anthropic has introduced Claude Skills (https://www.anthropic.com/engineering/equipping-agents-for-the-real-world-with-agent-skills), a standardized format for packaging reusable agent capabilities.

This project will create a toolbox for the LLM CLI that enables LLMs to discover and load Claude Skills dynamically.

## Decision

Create an `llm-tools-skills` toolbox plugin that provides two tools to LLMs:

### Toolbox Registration
- The toolbox registration will accept a path. The path can be a local directory, a zip file, or a remote URL.
- The path itself can contain one SKILL.md (and supporting files) or a directory of directorie(s) each with their own SKILL.md.
- We'll assume that if the path contains a SKILL.md at its root, then there is only one skill. If not, we'll look for subdirectories with SKILL.md files.

### Dynamically define load_skill names that are available
- Since we want the LLM to know at the start what skills are available, use the [Dynamic Toolbox](https://llm.datasette.io/en/stable/python-api.html#python-api-tools-dynamic) feature to wrap the `load_skill` tool with a docstring listing out all the skill frontmatter.
- This will provide the LLM the frontmatter context without loading the full skill.
- For each skill that is discovered, define a `load_skill_X` tool where `X` is the skill name from the frontmatter.

### `load_skill_X(path='SKILL.md')` Tool
- Loads the complete skill definition from `SKILL.md` for a given skill `X`.
- Optional `path` parameter allows loading additional files within a specific skill bundle
- Supports local directories, zip archives, and remote URLs

## Consequences

**Benefits:**
- LLMs can discover skills before loading them, reducing context usage
- Flexible distribution via local, zip, or remote sources
- Incremental file loading with the `path` parameter
- Compatible with Anthropic's skill format

**Challenges:**
- Security validation for remote skills
- Need caching for remote resources
- Path resolution across different loading mechanisms

**Mitigation:**
- Validate remote content before execution
- Implement local caching with TTL
- Consistent path resolution logic
