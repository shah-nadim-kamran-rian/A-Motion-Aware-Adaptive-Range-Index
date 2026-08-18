#!/bin/bash
# Fair benchmark per CSE511 protocol: same language, same machine, fixed CPU freq.
# Measures peak memory (RSS=%M, in KB) and CPU time (user+sys = %U+%S, NOT elapsed).
# 1) First fix CPU frequency 99-100% (e.g. CPU Power Manager) BEFORE running.
# 2) Then:
set -e
for M in MARI ART PGM Bx; do
  /usr/bin/time -o time_$M.txt -f "RSS=%M KB   TIME=%S+%U s" python3 run_method.py "$M" > out_$M.json
  printf "%-6s  " "$M"; cat time_$M.txt
done
echo "Per-method perf (reloc/exact) is in out_<M>.json ; memory/time is in time_<M>.txt"
