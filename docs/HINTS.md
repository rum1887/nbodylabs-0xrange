# 🪜 Progressive Hints & Difficulty Ladder

Use this ladder if you feel stuck. The hints are designed to guide your investigative methodology without spoiling specific payload names or solution steps.

---

### Level 1: Reconnaissance (Understanding Orbit's Boundaries)

<details>
<summary>🔍 Hint 1.1 — Mapping Orbit's Capabilities</summary>

Orbit is an autonomous account co-pilot integrated into the cloud console. It doesn't crawl the external web; it interacts with the platform API through discrete tool definitions.
* Start by discovering what Orbit can inspect:
  * Ask Orbit about active domains, security rules, and feature entitlements.
  * Pay attention to the intermediate steps: what read tools does Orbit invoke before returning an answer?
</details>

<details>
<summary>🔍 Hint 1.2 — Inspecting Zone Configuration</summary>

When an operator asks an assistant to review a domain or zone, the assistant must pull live records into its context window.
* Ask Orbit to review or summarize the records associated with the account's domains.
* Examine the information Orbit surfaces: what types of records are present, and what values do they hold?
</details>

---

### Level 2: Identifying Untrusted Data Ingestion

<details>
<summary>⚡ Hint 2.1 — Data vs. Instructions in LLM Systems</summary>

In traditional web applications, injection occurs when untrusted data crosses a parser boundary (like SQL or HTML). In LLM systems, **Indirect Prompt Injection** occurs when external data fetched by a tool contains natural language that the model confuses with system-level operator instructions.

* When Orbit retrieves records, every field—names, types, and text values—enters the model's active message history.
* Audit the retrieved values carefully: do all records contain strictly machine-readable network configuration (IPs, verification hashes, mail servers)?
</details>

<details>
<summary>⚡ Hint 2.2 — Spotting Imperative Language</summary>

Look for records that contain natural language directives rather than passive configuration.
* Does any text attempt to address "agents", "assistants", or "operators"?
* Does any field claim that a task is "pre-approved", "mandatory", or part of "automated routine management"?
</details>

---

### Level 3: Tracing the Hijack Mechanism

<details>
<summary>🎯 Hint 3.1 — Observing Goal Deviation</summary>

When an indirect injection triggers, the model experiences **Goal Hijacking**: its primary objective (answering the user's original question) is superseded by the attacker's objective.
* If you ask Orbit a simple summarization question, watch its execution trace closely.
* Does Orbit stop at summarization, or does it begin invoking subsequent tools that you never requested?
* Which specific capabilities does Orbit attempt to exercise?
</details>

<details>
<summary>🎯 Hint 3.2 — Analyzing Defense Filters</summary>

Many production AI systems use input/output guardrails (such as substring scanners or regex pattern matching) to catch obvious injection keywords.
* If a guardrail triggers, analyze how that guardrail functions: is it a semantic AI classifier, or a static string filter?
* How might an attacker who controls external record data structure their phrasing or formatting to evade rigid heuristic filters?
</details>

---

### Level 4: The Approval Gate & Reviewer Deception

<details>
<summary>🛡️ Hint 4.1 — Verifying Real-World Impact</summary>

When assessing severity for a bug bounty report, triagers will scrutinize whether an actual breach occurred or if the model merely produced text.
* Check the **Approvals** tab in the console.
* Does Orbit have the permission to unilaterally mutate live infrastructure, or are write operations gated by human confirmation?
* Has the account state actually changed before a human clicks "Approve"?
</details>

<details>
<summary>🛡️ Hint 4.2 — The Human-in-the-Loop Attack Vector</summary>

In systems protected by an approval gate, an attacker's goal hijacking is only half of the exploit. The second half is **deceiving the human operator**:
* Compare the text of the staged proposal in the Approvals queue against what Orbit told you in the chat drawer.
* Did Orbit warn you about what it staged, or did it generate reassuring language claiming the action was routine and safe?
* Document both the technical tool deviation and the social engineering element in your report.
</details>
