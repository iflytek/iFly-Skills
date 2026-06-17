# Overview

**iFly-Skills** is the official collection of [iFLYTEK (科大讯飞)](https://www.xfyun.cn/) skills for
agent ecosystems and developer workflows. It packages iFLYTEK AI capabilities — speech, OCR,
translation, proofreading, and multimodal understanding — into self-contained, reusable skills that
are easy to install, combine, and evolve.

## What is a "skill"?

A skill is a single top-level directory in the repository that bundles everything an agent needs to
use one capability:

```
ifly-hyper-tts/
├── SKILL.md        # trigger description, API docs, usage examples
├── scripts/        # runnable scripts (Python, stdlib-first)
└── _meta.json      # metadata
```

The `SKILL.md` frontmatter tells an agent *when* to invoke the skill (the `description` and
`user_instructions`), and the body documents *how* to call it. Most skills are pure-Python and
depend only on the standard library, so there is little to install.

## Two kinds of skills

- **Atomic skills** wrap a single model capability — text-to-speech, OCR, translation, and so on.
- **Solution skills** chain several capabilities into one scenario-level task flow, such as
  [Contract Intelligence Review](/skills/#solutions) (OCR → clause analysis → risk detection →
  proofreading → summary).

The collection will keep expanding toward more scenario-oriented packages: document processing,
content production, intelligent review, multimodal analysis, and other integrated task chains.

## Next steps

- [**Quick Start**](/guide/quick-start) — get credentials and run your first skill.
- [**Skill Catalog**](/skills/) — browse everything available today.
- [**Contributing**](/CONTRIBUTING) — add a skill, a recipe, a translation, or an FAQ entry.
