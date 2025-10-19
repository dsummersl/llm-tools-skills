# Add Skills bundles to the LLM CLI tool.

A tool for the [llm](https://llm.datasette.io/) command line that allows loading a [Claude Skill](https://www.anthropic.com/engineering/equipping-agents-for-the-real-world-with-agent-skills).

# Usage

Install for use with llm:

```sh
# install the plugin:
llm install llm-tools-skill

# see available plugins:
llm plugins

...
  {
    "name": "llm-tools-skill",
    "hooks": [
      "register_tools"
    ],
    "version": "0.1.0"
  },
...
```

Examples:

```sh
# Load my local skills, and use them against some other context (eg, a local repo):
repomix
cat repomix-output.xml | llm -T 'Skills("../my-coding-skills")' "Check this codebase against my own best practice skills"
```

This plugin supports two kinds of directory structures:
- A single skill: A directory with a single SKILL.md and supporting files.
- Multiple skills: A directory with multiple subdirectories, each containing a SKILL.md and supporting files.

# Security and Privacy

**Warning**: This tool has read-access to your entire browser history. You risk sending
this highly sensitive personal data to third-party services (like OpenAI).

See [the lethal trifecta article](https://simonw.substack.com/p/the-lethal-trifecta-for-ai-agents) for more information about the risks of using tools like this with LLMs.

## Dev setup

```bash
make setup
make test
```

