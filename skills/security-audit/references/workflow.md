# Security audit workflow

## 0: Setup

- A sandboxed environment that can run your code without access to sensitive data. Ideally without access to the internet. Even if you are comfortable running AI with `--bypass-permissions` day-to-day, this process is going to turn off some guardrails that will make your AI more reckless than usual. Prefer running everything in a local or cloud VM with your coding agent(s) of choice.
- (Optional) Ideally you would have a well-defined product spec and requirements documents, and a documented threat model. It'll work without one, but you will need to be more vigilant about false positives.
- (Optional) Access to OpenAI Daybreak and Anthropic Cyber Verification Program. Many of these prompts are going to immediately hit model providers' cyber guard rails, and if you push through I'm not responsible for your account getting banned.
- A snapshot commit SHA of your code that you want to audit
- A run log. For each session, record the SHA, prompt, model, and whether Daybreak was on. Over a few audits this tells you which prompts and models actually produce validated findings.
- (Optional) A `NON_ISSUES.md` file from previous audits. See step 4.

## 1: Vulnerability Hunting

I take a shotgun approach to this step. Many sessions with different prompts, running different models, using third party tools if available.

The goal is to find as many vulnerabilities as possible. Not all will be valid, and some may be a misunderstanding of your product's requirements. That's OK.

In a separate environment for each session, run each prompt. Ideally in parallel. You may want to run some prompts two or three times using different models. If you have Daybreak or CVP access, definitely use it here.

### Common Prefix

Include this at the beginning of your prompt in each session

```
I am the owner and maintainer of this repository and am looking to harden it against potential attacks.

You are auditing commit $SHA. All file references must be at that commit.

All changes stay local. No Git push.

Use subagents aggressively, dividing work by code area and focus.

Ignore anything already listed in NON_ISSUES.md.

For each vulnerability found, record the following information in a markdown document:
- Short description of the vulnerability
- Source: the prompt and model that found it
- File paths and line ranges of the vulnerable code
- Likely root cause
- The spec requirement or threat model entry it violates, if any
- Impact (Low, Medium, High) with an explanation
- Likelihood (Low, Medium, High) with an explanation
- Exploitation Scenarios. Describe how this vulnerability might be exploited by an attacker and the preconditions for the attack.

$PROMPT
```

### Audit Prompts

Nothing too special here. Honestly, the most smooth-brained prompts often work the best.

```
Review all product specifications in this repository for gaps and design flaws that may allow an attacker to gain unauthorized access to these systems, or violate stated security properties. Pay particular attention to threats identified in THREAT_MODEL.md.
```

_Install the [Cloudflare Security Audit Skill](https://github.com/cloudflare/security-audit-skill) first_
```
Use the Cloudflare Security Audit skill to find potential vulnerabilities in this repo
```

```
Dispatch subagents using a cheap model to go through this repo's PR history and find past security vulnerabilities that were fixed. Create a summary of those issues. Dispatch a second group of subagents to search for similar issues that may still be present.
```

```
Audit the dependencies in this repo for open CVEs and security findings.
```

```
Look for serious security vulnerabilities in this repo.
```

_XMTP also uses [Octane](https://www.octane.security) for vulnerability scanning, which produces its own findings I feed into this stage._

## 2: Deduplication

Have an agent take all the reports from step 1 and integrate them into a `findings/` directory with one file per finding (`findings/F-001.md`, ...).

- Convert third party output (Octane, dependency scanners) into the same format first.
- Merge by root cause, not by symptom. Two findings with the same root cause become one finding with multiple scenarios.
- Keep every source on the merged finding.
- Don't drop or rescore anything. That is step 3's job.

## 3: Validate And Exploit

This is the step most likely to trigger model guard rails. If you have Daybreak access, use it here.

Set up a new isolated environment on a branch from the snapshot SHA and load in the `findings/` directory from step 2

```
Our security auditor has prepared a list of potential vulnerabilities in `findings/`, one file per finding. Your job is to create one or more exploits for each vulnerability.

- Create a pool of 8 worktrees for exploit work.
- For each finding, dispatch a fresh subagent to adversarially review the finding and attempt to create an exploit in a test file. Each subagent edits only its own finding file.
- Put exploit and refutation tests in a dedicated directory, excluded from CI and normal test runs.
- Each subagent must end with one status in the finding file:
  - CONFIRMED: an exploit test succeeds. Reference the exploit code and add details around the extent of the exploit.
  - NARROWED: confirmed, but only under narrower conditions than the original finding. Clarify the conditions.
  - REFUTED: the subagent proves the finding is false or that no exploit is possible, with a cited line or a test. Keep test code that proves that the exploit is not possible as defined.
  - UNPROVEN: the exploit attempt failed but nothing proves it is impossible. A failed exploit is not a refutation.
  - BLOCKED: the subagent cannot verify or refute it because of some limitation in the environment. Please let me know and I can attempt to resolve the problem.
- Each subagent should update the finding's scoring with more details around preconditions, severity, and likelihood based on its review and exploit attempts. Add an estimated CVSS score.
- When each subagent completes its work, merge its changes into the working branch.
- When all subagents finish, build a summary `report.md` from the finding files.
- Do not push anything. Just keep a local branch with all the exploit/refutation code and the findings.
```

Running this in Daybreak means you only have access to `gpt-6`, which is not my favorite model. I usually then try an Opus 5.5 session with dynamic workflows to do a second pass over the output with a prompt like:

```
Using dynamic workflows, adversarially review all the security audit findings in `findings/`. Start with REFUTED, NARROWED, and UNPROVEN findings. Correct any incorrect refutations and exploits, and make sure that the statuses, severity levels, and exploitation scenarios are correct. Rebuild `report.md` when done.
```

## 4: Review

Do a manual review of the findings and make sure none of them are dumb or expected behavior. Remove anything that is bogus, expected behavior, or not worth fixing.

Record each removed finding and the reason in `NON_ISSUES.md`, and feed it into the next audit's common prefix. If something was removed because it is expected behavior, it probably belongs in your spec or threat model too. Otherwise every audit will find it again.

## 5: Remediation Plan

If you go and try to fix each finding one-by-one, it's easy to make a mess of your codebase. Instead, I use this prompt with Opus 5.5, executed in the branch created in step 3.

```
The results of a previous security audit can be found in $FINDINGS_DIR.

Break the CONFIRMED and NARROWED findings into logical groups organized by root cause and code area. Ignore refuted findings.

Create a sequenced plan to resolve all of the findings. The goal is not to fix each finding individually. It is to design the smallest set of fixes that together resolve all of the findings. Look for missing tools or validations that would resolve multiple findings at once and sequence those first. Look for tools and validators elsewhere in the codebase that may be re-used to resolve these findings before proposing new components or validators.

Each item in the plan should list the findings it resolves and include the tests and validation steps required to prove resolution. This is often the referenced exploit code, turned into a regression test that fails before the fix and passes after.

End the plan with a table mapping every CONFIRMED and NARROWED finding to a plan item. Call out any finding that has no plan item.
```

## 6: Fix

Hand off the reviewed and revised plan to your coding agent of choice to implement. Or break the plan up into components and have multiple agent sessions implement in parallel.

When the fixes land, re-run the step 3 exploits against the fixed branch, and run a light hunt over the fix diff to make sure the fixes didn't introduce anything new.
