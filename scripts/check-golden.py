#!/usr/bin/env python3
from pathlib import Path

from fastrag.evaluation import load_golden

load_golden(Path("eval/golden.jsonl"), minimum_items=200)
print("golden dataset schema and coverage checks passed")
