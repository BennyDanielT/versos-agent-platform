"""Runnable demo. No API key, no deps -- pure stdlib.

    python run_demo.py            # one narrated episode + the metric
    python run_demo.py --kill     # same, but kill switch engaged -> agent proposes, never acts
    python run_demo.py --eval 5   # run N episodes, print the aggregate metric

In the interview you'd swap FakeLLM -> ClaudeLLM (llm.py) and FakeSim -> their sim.
The adapter and the loop don't change.
"""
from __future__ import annotations

import sys

import gate as gate_mod
from agent import run
from fake_sim import FakeSim
from llm import FakeLLM


def one_episode(kill: bool = False) -> dict:
    gate_mod.KILL_SWITCH = kill
    print(f"\n=== episode (kill_switch={kill}) ===")
    result = run(FakeSim(), FakeLLM())
    print("metric:", result["metric"])
    return result["metric"]


def evaluate(n: int) -> None:
    gate_mod.KILL_SWITCH = False
    resolved = steps = 0
    for i in range(n):
        m = run(FakeSim(seed=i), FakeLLM())["metric"]
        resolved += int(m["resolved"])
        steps += m["steps"]
    print(f"\n=== eval over {n} episodes ===")
    print(f"completion_rate = {resolved}/{n} = {resolved / n:.0%}")
    print(f"avg_steps_to_goal = {steps / n:.1f}")


if __name__ == "__main__":
    args = sys.argv[1:]
    if "--eval" in args:
        evaluate(int(args[args.index("--eval") + 1]))
    else:
        one_episode(kill="--kill" in args)
