# How to Create Skills

## Quick Start

### 1. Write Your Script with argparse

```python
# my_script.py
import argparse

parser = argparse.ArgumentParser(description="My analysis tool")
subparsers = parser.add_subparsers(dest='command')

# Subcommand: analyze
analyze_parser = subparsers.add_parser('analyze', help='Run analysis')
analyze_parser.add_argument('--year', type=int, required=True, help='Year to analyze')
analyze_parser.add_argument('--input-file', type=str, help='Optional input CSV')

# Subcommand: list-outputs
list_parser = subparsers.add_parser('list-outputs', help='List output files')

args = parser.parse_args()

if args.command == 'analyze':
    # Your logic here
    print(f"Analyzing year {args.year}")
    # Save to output/
    with open('output/result.csv', 'w') as f:
        f.write("results")
```

### 2. Create SKILL.md

```yaml
---
name: my-analysis
description: Analyze data for a given year. Use when analyzing yearly trends.
entry: python my_script.py
---

# My Analysis Tool

Analyzes yearly data trends.

## Usage Examples

- "Run my analysis for 2024"
- "Analyze year 2023 with custom input file"
- "List my analysis outputs"
```

### 3. Test It

```bash
# Test help parsing
python my_script.py -h
python my_script.py analyze -h

# Run the MCP server
mcp-skill-server /path/to/skills
```

## Converting Existing Scripts

### Before (Manual Parameters)
```python
# Old way - hardcoded or manual input
YEAR = 2024
INPUT_FILE = "data.csv"
```

### After (argparse)
```python
# New way - CLI arguments
parser = argparse.ArgumentParser()
parser.add_argument('--year', type=int, required=True)
parser.add_argument('--input-file', type=str)
args = parser.parse_args()
```

## Key Rules

1. **Use argparse** - Required for automatic schema discovery
2. **Subcommands for operations** - analyze, list-outputs, clean, etc.
3. **Save to output/** - Files in output/ are automatically detected
4. **Required vs Optional** - Use `required=True` in argparse
5. **Minimal YAML** - Only name, description, entry needed

## Schema Discovery

The system automatically discovers:
- ✅ Subcommands from `script.py -h`
- ✅ Parameters from `script.py <subcommand> -h`
- ✅ Required/optional from usage line brackets `[--optional]`
- ✅ Types from metavar: `YEAR` → int, `FILE` → string

## File Structure

```
my_skills/
└── my_analysis/
    ├── SKILL.md          ← Minimal frontmatter
    ├── my_script.py      ← CLI with argparse
    ├── input/            ← Input data (optional)
    └── output/           ← Generated files (auto-detected)
```

## Common Patterns

### Single Operation (No Subcommands)
```python
parser = argparse.ArgumentParser()
parser.add_argument('--year', required=True)
# No subparsers needed
```

### Multiple Operations (With Subcommands)
```python
subparsers = parser.add_subparsers(dest='command')
run_parser = subparsers.add_parser('run')
clean_parser = subparsers.add_parser('clean')
```

### Optional Parameters with Smart Types
```python
# Type inference works from metavar names:
parser.add_argument('--plan-year', type=int)     # "year" → inferred as int
parser.add_argument('--input-file', type=str)    # "file" → inferred as string
parser.add_argument('--batch-size', type=int)    # "size" → inferred as int
parser.add_argument('--threshold', type=float)   # explicit type
```

## Troubleshooting

**Skill not found:**
- Check SKILL.md location: `<skills_dir>/<skill_name>/SKILL.md`
- Verify YAML starts with `---`

**Commands not discovered:**
- Test: `python script.py -h` - should show subcommands
- Ensure subparsers.add_parser() calls exist

**Parameters wrong:**
- Test: `python script.py <subcommand> -h`
- Check usage line shows `[--optional]` vs `--required`

**Files not detected:**
- Save to `output/` directory
- Or print `OUTPUT_FILE:/path/to/file` to stdout
