<div align="right">

English | **[中文](README.md)**

</div>

![darwin.skill](assets/banner-en.svg)

<div align="center">

# darwin.skill

**Optimize your Agent Skills the way you train models.**

Inspired by [Karpathy's autoresearch](https://github.com/karpathy/autoresearch). Autonomous experiment loops, applied to skill optimization. A ratchet that only turns forward.

[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)
[![Agent Skill](https://img.shields.io/badge/Agent%20Skill-Compatible-blueviolet)](https://skills.sh)
[![Skills](https://img.shields.io/badge/skills.sh-Compatible-green)](https://skills.sh)

```
npx skills add alchaincyf/darwin-skill
```

</div>

---

## The Core Loop

![Core Loop](assets/chart-loop-en.png)

Evaluate → Improve → Test → Human Confirm → Keep or Revert. Repeat.

---

## Why This Exists

Agent skill ecosystems are expanding fast. Claude Code, Codex, OpenClaw, Trae, CodeBuddy and more all support the SKILL.md format. When you have 10 skills, you can maintain them by hand. When you have 60+, you need a system.

Traditional skill review is purely structural: does the frontmatter look right? Are the steps numbered? Do the file paths exist? But a perfectly formatted skill can still produce terrible output.

darwin.skill evaluates both **structure** and **real-world effectiveness**, then keeps only the changes that actually improve things.

---

## From autoresearch to Skill Optimization

This project maps Karpathy's autoresearch directly onto skill optimization:

| autoresearch | darwin.skill | Why |
|:---|:---|:---|
| `program.md` | This SKILL.md | Defines evaluation criteria and constraints |
| `train.py` | Each target SKILL.md | The single editable asset per experiment |
| `val_bpb` | 8-dimension weighted score (max 100) | Quantifiable optimization target |
| `git ratchet` | keep / revert mechanism | Keep evidence-backed improvements; Git actions follow task authorization |
| `test set` | test-prompts.json | Validates whether improvements are real |
| Fully autonomous | **Human in the loop** | Skill quality is more subjective than loss |

Skill quality requires evidence and sometimes human judgment. When the user chooses staged review, darwin.skill waits after test prompts, baseline evaluation, and each skill. An authorized continuous optimization proceeds across these stages without repeated confirmation. Plan-first requests and separate publication, payment, or Git approvals remain binding.

---

## Five Core Principles

| # | Principle | Details |
|:---|:---|:---|
| 01 | **Single editable asset** | One SKILL.md per experiment. One change, one measurement, one decision |
| 02 | **Dual evaluation** | Structure scoring (static analysis) + effectiveness scoring (live test execution) |
| 03 | **Ratchet mechanism** | Score can only go up. Regressions are auto-reverted |
| 04 | **Independent scoring** | Prefer available independent review; when unavailable, label dry_run and never present self-review as an independent live test |
| 05 | **Human in the loop** | Preserve user-selected review gates; do not repeat approval during authorized continuous work |

---

## 8-Dimension Evaluation Rubric

Total: 100 points. Structure (60) + Effectiveness (40).

![Evaluation Rubric](assets/chart-rubric-en.png)

> Live test performance has the highest weight (25 points). A beautifully written skill that produces bad output is still a bad skill.

---

## The Optimization Cycle

Five phases. Only one is the core. The diagram shows stage relationships; review gates follow the selected staged or continuous mode.

![Optimization Lifecycle](assets/chart-phases-en.png)

**Phase 2 (the heart):**

1. Find the lowest-scoring dimension
2. Generate one targeted improvement
3. Edit SKILL.md; stage exact paths and commit only with existing Git authorization
4. Re-score with available independent review; otherwise record dry_run and its limitations
5. Keep evidence-backed improvements without capability, correctness, or permission regressions; otherwise restore only this task's changes, respecting Git authorization for committed changes
6. Show the diff, outcome evidence, and score delta; wait in staged review mode or continue within existing continuous-work authorization

---

## The Ratchet

Scores can only go up. Failed experiments are cleanly reverted. No regressions accumulate over time.

![Ratchet Mechanism](assets/chart-ratchet-en.png)

Round 2 scored 75, below the current best of 78. Auto-reverted. Effective baseline stays at 78. Subsequent improvements build from 78, not 75.

---

## Quick Start

```bash
npx skills add alchaincyf/darwin-skill
```

After installation, tell your agent: "optimize all skills" or "optimize [skill-name]". Works with any tool that supports the SKILL.md format.

For offline installation, use an acquired and reviewed complete Skill directory, retaining `SKILL.md`, `references/`, `scripts/`, and required assets. Place it in the current agent's configured Skill directory; do not assume a Claude path or a particular operating system. Copying only `SKILL.md` loses referenced guidance and executable capabilities.

---

## Design Inspiration

Directly inspired by **Andrej Karpathy's [autoresearch](https://github.com/karpathy/autoresearch)**.

The core mechanism is identical: **keep only measurable improvements, revert everything else.**

---

## About the Author

| | |
|:---|:---|
| 🌐 Website | [bookai.top](https://bookai.top) · [huasheng.ai](https://www.huasheng.ai) |
| 𝕏 Twitter | [@AlchainHust](https://x.com/AlchainHust) |
| 📺 Bilibili | [花叔](https://space.bilibili.com/14097567) |
| ▶️ YouTube | [@Alchain](https://www.youtube.com/@Alchain) |
| 📕 Xiaohongshu | [花叔](https://www.xiaohongshu.com/user/profile/5abc6f17e8ac2b109179dfdf) |
| 💬 WeChat | Search "花叔" |

---

## License

MIT

---

<div align="center">

**[Nuwa](https://github.com/alchaincyf/nuwa-skill)** creates skills.<br>
**Darwin** makes them evolve.<br><br>
*Keep only improvements. Time is on your side.*

<br>

MIT License © [花叔 Huashu](https://github.com/alchaincyf)

</div>
