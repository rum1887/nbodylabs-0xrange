# 🛠️ Challenge 0x00: Environment Setup & Pre-flight

Before diving into adversarial attacks, every security researcher needs a solid, reliable testing ground. **Challenge 0x00** guides you through setting up the NBody Labs Range, eliminating hardware friction, and verifying model tool-calling fidelity.

---

### Step 1: System Prerequisites
Ensure you have the core tools installed:
* **Docker & Docker Compose** (running)
* **Git**
* **Python 3.9+** (recommended for running verification scripts)

---

### Step 2: Clone & Configuration
```bash
# Clone the repository
git clone https://github.com/rum1887/nbodylabs-0xrange.git
cd nbodylabs-0xrange

# Copy the example environment configuration
cp .env.example .env
```

---

### Step 3: Choose Your LLM Runtime (Zero Hardware Friction)

Running a local model on CPU-only laptops can take 45–120s per turn and drain battery. For the best experience, configure Orbit to use any hosted OpenAI-compatible endpoint in your `.env`:

#### Option A: Hosted Fast Cloud (Recommended)
```bash
# Groq (Ultra-fast, generous free tier)
NBODY_OPENAI_BASE_URL=https://api.groq.com/openai/v1
OPENAI_API_KEY=gsk_...
NBODY_MODEL=llama-3.3-70b-versatile

# OR OpenAI (High tool fidelity)
NBODY_OPENAI_BASE_URL=https://api.openai.com/v1
OPENAI_API_KEY=sk-...
NBODY_MODEL=gpt-4o-mini
```

#### Option B: Fully Local (Default)
If you prefer 100% offline local testing, no API keys are required:
```bash
NBODY_MODEL=qwen3:4b
```
*(The model downloads automatically into Docker on first launch).*

*See [`../../docs/MODEL_GUIDE.md`](../../docs/MODEL_GUIDE.md) for full benchmarks and hardware recommendations.*

---

### Step 4: Verify Range Setup
Confirm your range is ready:
```bash
# Run the pre-flight check
./range setup
```

---

### Next Step: Launch Challenge 0x01
Once your environment is configured, proceed to the first active security challenge:
```bash
./range up 0x01
```

*Read the [Challenge 0x01 Guide](../01-goal-hijacking/README.md) to review the target scenario and begin your assessment.*
