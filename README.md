# MARI: Motion-Aware Adaptive Range Index

This repository contains the Week 1 implementation of **MARI**, a Motion-Aware Adaptive Range Index for exact range queries over moving 1-D integer keys.

## Files

- `mari.py`  
  Reference implementation, workload generator, brute-force oracle, MARI baseline experiment, and ordered-index baseline.

- `mari_v2.py`  
  Improved MARI local index with stable/delta tiers, in-place updates, migration, instrumentation counters, and comparisons with multiple baselines.

- `requirements.txt`  
  Python dependency list.

## Main Idea

MARI divides the key space into guarded buckets. Each bucket has a core range and an extended guard range. If a key changes slightly but remains inside its guard, it is updated in place. If it leaves the guard, it migrates to another bucket.

Query results are verified using an authoritative table, so the final answer remains exact.

## Installation

```bash
pip install -r requirements.txt
```

## Run

```bash
python mari.py
python mari_v2.py
```

## Expected Output

The experiments compare MARI's range-query results with a brute-force oracle. A mismatch count of zero means the range query answers are exact.

Generated result files:

- `mari_results.json`
- `mari_efficiency.json`

These files are ignored by `.gitignore` because they are generated outputs.
