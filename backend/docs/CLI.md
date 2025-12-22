# MGX CLI Documentation

The MGX Command Line Interface (CLI) is the primary way to interact with the MGX Agent for tasks, project management, and configuration.

## Installation

### Python (PyPI)
```bash
pip install mgx-cli
```

### Node.js (npm)
```bash
npm install -g @mgxai/cli
```

## Verification
```bash
mgx --version
```

## Quick Start

1. **Initialize a new project**
   ```bash
   mkdir my-new-app
   cd my-new-app
   mgx init .
   ```

2. **Run a task**
   ```bash
   mgx task "Create a simple Flask API with one endpoint"
   ```

3. **Check status**
   ```bash
   mgx list
   ```

## Command Reference

### `mgx init <path>`
Initializes a new MGX project in the specified path. Creates a `mgx.yaml` configuration file.

### `mgx task`
Runs a task using the MGX Agent.

- **Usage**: `mgx task [OPTIONS] [DESCRIPTION]`
- **Options**:
  - `--json <file>`: Load task definition from a JSON file.
  - `--project-path <path>`: Specify the project path (defaults to current).

**Example:**
```bash
mgx task --json task_def.json
```

### `mgx list`
Lists all tasks (history or active).

### `mgx status <task-id>`
Get the status of a specific task.

### `mgx logs <task-id>`
View execution logs for a task.

### `mgx config`
Manage global configuration.

- `mgx config get <key>`
- `mgx config set <key> <value>`
- `mgx config list`

### `mgx workspace`
Manage workspaces.

- `mgx workspace list`

### `mgx project`
Manage projects.

- `mgx project list`

## Configuration

Global configuration is stored in `~/.mgx/config.yaml`.
Project configuration is stored in `mgx.yaml`.

## Examples

### Scenario 1: Creating a React App
```bash
mgx task "Create a React application using Vite that displays a list of users from an API"
```

### Scenario 2: Fixing a Bug
```bash
mgx task "Fix the CORS error in the backend/main.py file" --project-path ./backend
```

### Scenario 3: Using a JSON Definition
Create `task.json`:
```json
{
  "task": "Build a CLI tool for file compression",
  "target_stack": "python",
  "constraints": ["use-click"]
}
```
Run:
```bash
mgx task --json task.json
```

### Scenario 4: Workspace Management
Listing available workspaces to switch context (e.g. for different teams).
```bash
mgx workspace list
# Output:
# - default (current)
# - engineering-team
# - marketing-ops
```

### Scenario 5: Debugging Task Execution
If a task fails or you need to inspect what happened, check the logs.
```bash
mgx logs task-12345
```
Or check status:
```bash
mgx status task-12345
```
