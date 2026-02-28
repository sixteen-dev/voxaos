---
name: file-ops
description: Bulk file operations — rename, move, organize, or transform multiple
  files at once. Use when users want to batch rename, reorganize directories, or
  apply operations across many files.
---

## Bulk File Operations

### Step 1: Understand the Operation
Clarify what the user wants:
- Rename pattern (e.g., "add prefix", "change extension", "snake_case")
- Move/organize rule (e.g., "by date", "by extension", "by size")
- Which files/directory to operate on

### Step 2: Preview
Before executing, list what WILL change:
- Show source → destination for each file
- Count total files affected
- Ask for confirmation if more than 10 files

### Step 3: Execute
Run the operations. For each file:
- Check if destination already exists (don't overwrite without asking)
- Report success/failure per file
- Summarize total: "Renamed 15 files, 0 errors"

### Safety
- Never operate on system directories (/etc, /usr, /bin)
- Always preview before bulk operations
- Keep a dry-run log of what was done
