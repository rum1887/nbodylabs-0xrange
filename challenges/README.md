# 🛰️ Managing Challenges & Orbit Chatbot Versions

This directory contains configuration profiles for each red-teaming lab in the NBody Labs Range.

## Architecture Overview

```
nbodylabs-0xrange/
├── challenges/
│   ├── 01-goal-hijacking/
│   │   └── config.env                  # Challenge 01 metadata & env
│   └── 02-<future-challenge>/
│       ├── config.env                  # Defines ORBIT_VERSION=v2, ports, etc.
│       └── docker-compose.override.yml # (Optional) Custom mounts, services, or images
├── agent/                              # Orbit Co-pilot service
├── cf-mock/                            # Mock platform API & account plane
├── docker-compose.yml                  # Base infrastructure compose
└── range                               # Single-command launcher CLI
```

---

## How to Add a New Challenge (e.g., Challenge 02)

To add Challenge 02 with a newer version of the Orbit chatbot:

### 1. Create Challenge Directory & Config
Create `challenges/02-<name>/config.env`:

```bash
CHALLENGE_ID=02
CHALLENGE_NAME="Tool Poisoning & Lateral Movement"
ORBIT_VERSION=v2
NBODY_PORT=8080
CF_MOCK_PORT=5050
```

### 2. Versioning the Chatbot (`ORBIT_VERSION`)

You can manage chatbot changes across versions in two ways:

#### Pattern A: Feature & Guardrail Versioning in Code (Recommended)
`agent/runtime.py` and `agent/mcp.py` read `os.environ.get("ORBIT_VERSION", "v1")`.
You can conditionally branch or load version-specific modules:

```python
orbit_version = os.environ.get("ORBIT_VERSION", "v1")

if orbit_version == "v2":
    # Orbit v2: Upgraded system prompt, multi-step agent chaining, or new tools
    TOOLS = {**BASE_TOOLS, **V2_TOOLS}
    SYSTEM_PROMPT = ORBIT_V2_PROMPT
else:
    # Orbit v1: Baseline configuration
    TOOLS = BASE_TOOLS
    SYSTEM_PROMPT = ORBIT_V1_PROMPT
```

#### Pattern B: Modular Compose Overrides
If Challenge 02 requires a completely different codebase or additional mock services (e.g. an external webhook listener, vector database, or dedicated container), place a `docker-compose.override.yml` inside `challenges/02-<name>/`:

```yaml
services:
  agent:
    build:
      context: ./agent
      dockerfile: Dockerfile.v2
    environment:
      - ORBIT_VERSION=v2
      - ENABLE_ADVANCED_TOOLS=true

  mock-third-party-api:
    image: python:3.11-slim
    ...
```

The `./range up 02` runner automatically detects and applies `docker-compose.override.yml` if present.

---

## Running Challenges with a Single Command

* **List all challenges:**
  ```bash
  ./range list
  ```

* **Launch Challenge 01 (Orbit v1):**
  ```bash
  ./range up 01
  ```

* **Launch Challenge 02 (Orbit v2):**
  ```bash
  ./range up 02
  ```

* **Tear down & clean state:**
  ```bash
  ./range down
  ```
