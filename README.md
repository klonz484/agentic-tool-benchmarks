# Agentic Tool Benchmarks

Controlled, repeatable evaluation of code-intelligence tools against the owner's public projects.

## Safety boundaries

- Benchmark clones are read-only inputs. No checkout, branch, commit, issue, PR, workflow, secret, or setting changes are made in `klonz484/examforge` or `klonz484/trading-vault`.
- All generated indexes and caches live in the temporary GitHub Actions runner and are discarded when the job ends.
- No production credentials, Supabase keys, model-provider keys, or paid APIs are used.
- Third-party tools are installed at pinned versions. Telemetry is disabled where supported.
- The benchmark repository stores only scripts, metadata, and sanitized result artifacts.

## First experiment

The first phase is a **structural retrieval benchmark**, not a claim about end-to-end AI-agent quality. It compares:

1. Baseline repository inspection using deterministic filesystem search.
2. Codebase Memory MCP indexing and graph queries.
3. Graft structural map generation and deterministic queries.

Targets are pinned to the source commits recorded in `benchmarks/targets.json`. The workflow records wall time, exit status, index/map output size, indexed files/nodes where available, and retrieval evidence. A tool that cannot complete a task is recorded as a failure, not silently excluded.

A later phase can test agent answer quality, token use, and correctness only after an approved model/runtime is available. No API key is required for this first phase.

## Run

1. Open **Actions** in this repository.
2. Select **Agentic Tool Benchmark**.
3. Choose **Run workflow** on `main`.
4. Download the `benchmark-results` artifact after completion.

The runner uses Ubuntu 24.04 x86-64. It does not require your laptop.

## Interpreting results

Structural retrieval timings are not equivalent to LLM-agent task completion times. Do not compare our measurements directly with vendor-published benchmarks unless task sets, model, prompts, hardware, caching, and scoring are identical. The report must distinguish measured values from tool self-reported metadata and failures.

## Licence and provenance

This harness is original benchmark glue. Tool licences and source links are recorded in `benchmarks/targets.json`. The tools are not vendored into this repository.
