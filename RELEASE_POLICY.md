# Release Policy

## Goal
Create clean, traceable GitHub releases with explicit gates before tagging.

## Release Criteria
A release is only considered ready when all of the following are true:
1. The release scope is clear and documented.
2. Core behavior or UI/API changes are summarized in release notes.
3. Python sources pass syntax compilation.
4. Tests that are available in the environment pass.
5. Core↔HA compatibility concerns are explicitly called out.
6. Known gaps are listed instead of silently ignored.

## Release Flow
1. Work on the current GitHub working tree.
2. Group changes into a coherent slice.
3. Run the release gate workflow.
4. Update `CHANGELOG.md`.
5. Draft release notes.
6. Tag and publish only after the gate is green.

## Notes Template
- Changed
- Checked
- Not clean / open
- Upgrade / compatibility notes
- Next step
