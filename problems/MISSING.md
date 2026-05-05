# Missing Components for Problems

This document outlines the missing components for the problems in the `problems/` directory. 
Currently, only the base structure, problem statement (PDF), and public sample test cases have been generated from the initial PDF.

For a problem to be fully complete and ready for a competitive programming contest in DOMjudge, you should add the following missing elements to each problem directory (`a`, `b`, `c`, `d`, `e`, `f`, `g`):

### 1. Secret Test Cases (`data/secret/`)
**Status: MISSING for ALL problems.**
*   **What it is:** The actual test cases used to evaluate the submissions and give points.
*   **Action:** Create a `data/secret/` directory inside each problem folder. Add your test files following the naming convention: `1.in`, `1.ans`, `2.in`, `2.ans`, etc.

### 2. Jury Solutions (`submissions/`)
**Status: MISSING for ALL problems.**
*   **What it is:** Working code (e.g., C++, Python, Java) written by the contest creators that solves the problem correctly.
*   **Why it's needed:** DOMjudge automatically runs these solutions against your test cases when you upload the problem. This acts as a sanity check to guarantee your test cases and time limits are valid. (DOMjudge raised a warning during upload: `"No jury solutions added"`).
*   **Action:** Create a `submissions/accepted/` directory inside each problem folder and place a working solution file inside (e.g., `solution.cpp` or `solution.py`).

### 3. Output Validators (Optional, but often necessary)
**Status: UNKNOWN (Review required per problem)**
*   **What it is:** A script that checks if a user's output is correct, rather than doing a strict byte-for-byte comparison with the `.ans` file. 
*   **When you need it:** If a problem has multiple valid correct answers (e.g., "print ANY valid path", or floating-point answers where a tolerance of 10^-6 is allowed).
*   **Action:** Review each problem statement. If the output format is not strictly unique, you must add an `output_validators/` directory with a custom validator script.

---

### Summary Checklist for Each Problem (`a` through `g`):
- [x] `problem.yaml` (Basic limits and name)
- [x] `problem.pdf` (Problem statement)
- [x] `data/sample/*.in` and `*.ans` (Public test cases)
- [ ] `data/secret/*.in` and `*.ans` (Hidden test cases)
- [ ] `submissions/accepted/solution.*` (Jury solution to verify limits)
- [ ] `output_validators/` (Only if the problem has multiple valid outputs)
