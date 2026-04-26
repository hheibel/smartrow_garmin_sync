---
name: skill-creator
description: >
  Creates, modifies, and improves Antigravity agent skills. Use when the user wants to 
  create a skill from scratch, edit or optimize an existing skill, or benchmark a skill's 
  performance and trigger accuracy.
---

# Goal
To provide the Antigravity agent with a structured, step-by-step process for generating, auditing, and refining other Agent Skills locally within the `.agent/skills/` directory.

# Instructions

## Phase 1: Context Gathering & Planning
1. **Analyze the Request**: Identify if the user wants to create a new skill, update an existing one, or run tests/benchmarks on trigger keywords.
2. **Define the Scope**: Determine the core objective of the target skill. Will it require external execution (e.g., shell scripts in a `/scripts` directory), or is it purely prompt-based context?
3. **Set the Trigger Keywords**: Formulate a strong `description` block for the target skill's YAML frontmatter. This description dictates when Antigravity's progressive disclosure model will activate the skill.

## Phase 2: Scaffolding the Skill
1. **Create the Directory**: Scaffold the new skill in `.agent/skills/<skill-name>/`.
2. **Generate the SKILL.md**: Build the file with the following required Antigravity structure:
   - **YAML Frontmatter**: Must include `name` and `description`.
   - **# Goal**: A concise one-sentence objective.
   - **# Instructions**: Step-by-step numbered logic the agent must follow when the skill is activated.
   - **# Examples**: Few-shot examples demonstrating expected inputs and outputs.
   - **# Constraints**: Strict "Do Not" boundary rules.
3. **Optional Scripts**: If the target skill requires binary execution or interacting with local system environments, scaffold a `.agent/skills/<skill-name>/scripts/` folder and place the wrapper scripts there.

## Phase 3: Review & Iterate
1. Review the generated `SKILL.md` to ensure instructions are declarative and not ambiguous.
2. Ask the user if they would like to refine the trigger keywords or add any specific constraints.

# Examples

**User**: "Create a skill that enforces our deployment checklist."
**Agent**: 
1. I will scaffold `.agent/skills/deployment-checklist/SKILL.md`.
2. I will write frontmatter with a description: "Use when the user asks to deploy, release, or push to production."
3. I will write strict instructions mapping out the deployment checklist.

# Constraints
- ALWAYS output the skill in standard markdown as `SKILL.md`.
- DO NOT grant broad `Bash(*)` tool access indiscriminately in new skills unless explicitly requested. Limit tool access scopes.
- ONLY place new skills within the `.agent/skills/` workspace directory unless the user specifies the global `~/.gemini/antigravity/skills/` path.
