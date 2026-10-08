# 🛰️ NBody Labs: Security Labs

> **The proving ground for modern security research.**  
> *Real architectures. Modern attack surfaces. Zero artificial flags.*

NBody Labs is an independent venture dedicated to building the next generation of hands-on security labs, realistic ranges, and practical playgrounds for engineers, researchers, and learners.


```bash
# Launch Challenge 01 with a single command
./range up 01
```

Once running:
* **NBody Cloud Console (Orbit Co-pilot):** [http://localhost:8080](http://localhost:8080)
* **NBody Cloud Platform API:** [http://localhost:5050](http://localhost:5050)

---

## ⚡ Running on a Laptop? Skip Local Ollama (Zero Hardware Friction)

Running a local model inside Docker on CPU-only laptops can be slow (45–120s per turn) and drain battery. **You can completely skip the local model download** by pointing Orbit to any hosted OpenAI-compatible provider (Groq, OpenAI, OpenRouter, or native host Ollama).

Simply set your `.env` before running `./range up 01`:

```bash
# Option A: Groq (Ultra-fast & free tier available)
NBODY_OPENAI_BASE_URL=https://api.groq.com/openai/v1
OPENAI_API_KEY=gsk_...
NBODY_MODEL=llama-3.3-70b-versatile

# Option B: OpenAI (Near-zero cost, high tool-calling fidelity)
NBODY_OPENAI_BASE_URL=https://api.openai.com/v1
OPENAI_API_KEY=sk-...
NBODY_MODEL=gpt-4o-mini
```

*See the [Model Reliability & Solvability Guide](docs/MODEL_GUIDE.md) for full benchmarks and setup instructions.*

---

## 🎯 Security Challenges

| ID | Challenge | Target | Attack Surface | Guide |
|:---|:---|:---|:---|:---|
| **01** | Goal Hijacking against Orbit | Orbit Co-pilot (v1.0) | Indirect Prompt Injection, Secondary Objectives, Tool Coercion | [Challenge 01 Guide](challenges/01-goal-hijacking/README.md) |

To launch Challenge 01:
```bash
./range up 01
```

*See the [Challenge 01 Guide](challenges/01-goal-hijacking/README.md) for target scenario details, asset boundaries, and exploration hints.*

---

## 📋 Program Rules of Engagement

The NBody Labs Range models realistic production cloud infrastructure. To keep testing safe and focused, participants must adhere to the following scope boundaries:

| In-Scope | Out-of-Scope |
|---|---|
| • Direct & Indirect Prompt Injection | • Network Denial of Service (DoS/DDoS) |
| • Goal Hijacking & Objective Displacement | • Brute-forcing host infrastructure ports |
| • Privilege Escalation via Agent Tool Calling | • Host breakouts / escaping Docker containers |
| • Sensitive Credential & Secret Exfiltration | • Modifying local testbed code directly |
| • Bypassing or socially engineering human approval gates | |

---

## 🏆 Submission & Triage Workflow (Pull Request Review Bot)

This lab operates with **zero artificial CTF flags or synthetic strings**. Findings are submitted and reviewed just like a professional bug bounty submission:

### 1. Write Your Bug Bounty Report
Follow standard security disclosure formatting:
* **Vulnerability Title & Classification:** Standard taxonomy (e.g. CWE-1427, OWASP Top 10 for LLM: LLM01).
* **Severity Assessment:** CVSS v3.1 vector or P1–P4 severity rating with tangible business impact.
* **Empirical Reproduction Steps:** Exact prompt sequence, model configuration, and empirical success rate measured over $N$ trials.
* **Proof of Impact & Forensic Evidence:** Clear separation of:
  - **REACHED**: Untrusted payload successfully ingested into model context.
  - **HIJACKED**: Agent deviated from intended objective or executed rogue instructions.
  - **LEAKED / MUTATED**: Impact materialized in the platform backend or stopped by security boundaries (with audit log excerpts).
* **Root Cause & Architectural Remediation:** Concrete defensive fixes (context delimiters, policy boundaries, least privilege).

### 2. Submit as a Pull Request
1. Fork the submission repository: [`nbody-labs-x-range-submissions`](https://github.com/rum1887/nbody-labs-x-range-submissions)
2. Add your report under the target challenge directory:
   ```
   submissions/<challenge-id>/<your-handle>-report.md
   ```
   *(e.g., `submissions/challenge-01/alice-report.md`)*
3. Open a Pull Request against `main`.

### 3. Automated AI Triage Bot Review
An automated AI Triage Bot evaluates your report against the **25-point NBody Labs triage rubric** (scoring taxonomy, reproducibility, output separation, threat modeling, and remediation). The bot comments directly on your PR with a structured score, detailed critique, and actionable feedback.

---

## ⚡ Single-Command Challenge Runner (`./range`)

The range provides a centralized CLI to spin up, manage, and tear down challenges:

```bash
# List all available challenges and active Orbit versions
./range list

# Spin up Challenge 01
./range up 01

# View running container health
./range status

# Reset environment state fresh
./range reset 01

# Stop and tear down all containers
./range down
```

---

## 🧩 Managing Multiple Challenges & Orbit Versions

Each challenge is housed under the `challenges/` directory with its own environment profiles and compose overrides:

```
challenges/
├── 01-goal-hijacking/
│   ├── README.md                   # Scenario, scope & submission guide
│   └── config.env                  # Challenge 01: Orbit v1 baseline
└── 02-<future-challenge>/
    ├── config.env                  # Challenge 02: ORBIT_VERSION=v2
    └── docker-compose.override.yml # Optional overrides (custom images, extra backend services)
```

*See [`challenges/README.md`](challenges/README.md) for full technical documentation on adding new challenges and bumping Orbit versions.*

---

## 🔍 Verification & Model Solvability

To verify model tool-calling reliability and confirm your setup works before manual exploration:

```bash
python3 hijack_test.py 10 240   # 10 trials, 240s timeout per turn
```

See [`docs/MODEL_GUIDE.md`](docs/MODEL_GUIDE.md) for illustrative benchmark data across local vs. hosted models.

---

> **Disclaimer:** *The simulated cloud console and Orbit co-pilot are educational security testbeds created by NBody Labs, modeled after common industry patterns in cloud platforms and AI agents. NBody Labs is an independent venture and has no affiliation with, sponsorship from, or endorsement by any commercial cloud provider.*
