# Notes

- The learner wants each lesson published as a shareable artifact. Artifacts start private; the learner shares them from the artifact page.
- Mission is to build the Product Thinking Game (`index.html`). End each lesson with a "For your game" prompt that turns the skill into a mechanic.
- Publishing: run `python3 scripts/build_artifact.py lessons/NNNN-*.html` to inline `assets/` into a copy under `build/`, then publish `build/` with any reference pages as `files`.
- Lesson order follows Module 1's "next guide" link: Understanding the Problem → Start With The Whys → Craft a Clear Problem Statement (4Cs) → Metrics → Assumptions and Risks → Customer Experience → Key Takeaways.
