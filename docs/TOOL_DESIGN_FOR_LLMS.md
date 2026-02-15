# Tool Design for LLMs: Skills vs Raw Tools vs Resources

When giving an LLM agent access to tools, how you present them matters. This doc compares three approaches and their trade-offs from the LLM's perspective.

## What the LLM sees

### 1. Raw function-call tools

Each tool appears directly in the LLM's tool list with a name, description, and typed JSON Schema.

```
Tool: generate_report
  description: "Generate a quarterly report"
  schema: { "quarter": "string (required)", "format": "enum: pdf|csv" }
```

The LLM picks the tool and calls it in **one step**. The schema constrains what the LLM can output — it can't invent invalid parameters.

### 2. Skill server (list/get/run pattern)

The LLM sees four generic tools: `list_skills`, `get_skill`, `run_skill`, `refresh_skills`. To use any skill, it must:

1. `list_skills` — discover what's available
2. `get_skill(name)` — read the full schema and documentation (from SKILL.md)
3. `run_skill(name, command, parameters)` — execute with a freeform parameters dict

The `run_skill` schema is intentionally underspecified (`"additionalProperties": true`), which forces the LLM to call `get_skill` first to learn the real parameters. The SKILL.md content — usage examples, detailed explanations — is only loaded on-demand during the `get_skill` step.

### 3. MCP resource + raw tool

Each tool is a normal raw tool with a typed schema and short description. Rich documentation lives in a separate MCP resource (e.g., `skill://generate-report/docs`).

```
Tool:     generate_report — short description + full typed schema
Resource: skill://generate-report/docs — rich markdown documentation
```

The idea: the LLM reads the resource for context, then calls the tool with precise parameters.

## Trade-off comparison

| Factor | Raw tools | Skill server | Resource + tool |
|---|---|---|---|
| Tool calls to execute | 1 | 2–3 | 1–2 |
| Parameter accuracy | High (schema-constrained) | Lower (freeform dict) | High (schema-constrained) |
| Token cost per request | High if descriptions are long | Low (docs loaded on-demand) | Low (docs loaded on-demand) |
| Tool list scaling (20+ tools) | Degrades (LLM confuses similar tools) | Constant (always 4 tools) | Degrades (same as raw) |
| Rich documentation | Limited (single description string) | Full markdown via `get_skill` | Full markdown via resource |
| Forces "read before act" | No | Yes (schema is intentionally vague) | No (LLM can skip resource) |
| Language flexibility | Locked to server language | Any (subprocess) | Locked to server language |
| Isolation | In-process | Subprocess (can't crash server) | In-process |

## Key insights

**Concise descriptions help tool selection; rich docs help tool execution.** These are two different moments in the LLM's reasoning. Cramming everything into the tool description hurts selection accuracy and wastes tokens on every request.

**LLMs skip optional steps.** If the tool schema already has enough information to make a call, the LLM will skip reading additional documentation (whether via `get_skill` or a resource fetch). The skill server's intentionally vague `run_skill` schema is a forcing function — the LLM *must* read the docs to know the parameters. This is a feature, not a bug.

**Tool list size affects LLM performance.** As the number of tools grows past ~15–20, LLMs start confusing similar tools, hallucinating tool names, and making worse selections. The skill server keeps the list fixed at 4 tools regardless of how many skills exist, trading direct access for a discovery step.

**The ideal hybrid:** Use raw tools for a small number of stable, well-defined operations. Use the skill pattern for complex, evolving, or numerous capabilities where rich documentation and isolation matter.

## FAQ

### Why not cram the full documentation into the tool description?

Tool descriptions are injected into **every API request** as part of the system prompt. With 10 tools each carrying 500 tokens of markdown docs, that's 5,000 tokens per request — even when the user is chatting and not using any tools. You pay for those tokens on every round-trip, and they come directly out of your context window, leaving less room for conversation history and reasoning.

Beyond cost, LLM attention degrades with long tool descriptions. Models are weakest at retrieving information from the middle of long contexts. Bloated descriptions lower the signal-to-noise ratio in the tool list, making the LLM more likely to confuse similar tools or skim past critical details. Concise descriptions are better for *picking the right tool*. Rich docs are better for *using it correctly*. Separating these two moments is the key design insight.

### What about using MCP resources instead of `get_skill`?

This is architecturally cleaner than the skill server — you get typed schemas (raw tool advantage) plus on-demand documentation (skill advantage) using standard MCP primitives. In theory, it's the best of both worlds.

The major difference: **nothing forces the LLM to read the resource first.** Since the tool already has a complete typed schema, the LLM can — and typically will — skip the resource fetch and call the tool directly based on the short description alone. With the skill server, `run_skill` has an intentionally vague schema (`"additionalProperties": true`), so the LLM literally cannot succeed without calling `get_skill` first. The underspecified schema is the forcing function.

To make the resource approach work, you'd have to **degrade the tool schema on purpose** — strip the real parameters and replace them with a generic object:

```
Tool:     generate_report
            description: "Generate a report. Read skill://generate-report/docs first."
            schema: { "params": "object" }   ← intentionally vague

Resource: skill://generate-report/docs        ← has the real parameter details
```

This forces the LLM to fetch the resource to learn the parameters — but at that point, you've rebuilt `get_skill` / `run_skill` with extra steps. The skill server's "dumb" generic interface turns out to be a deliberate design choice: it makes reading the docs a **prerequisite**, not an option.
