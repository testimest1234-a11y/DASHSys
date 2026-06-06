# DASHSys Submission Bundle

Team: 4 braincells
Track: Real-World System Track
Paper ID: 22

This bundle contains the clean DASHSys Systems Track deliverables prepared from the verified final test-set run.

## Contents

- `source_code/`: source files needed to run the DASHSys agent.
- `test_artifacts/metadata/`: metadata JSON files for the 60 official test queries.
- `test_artifacts/prompts/`: filled system prompts for the 60 official test queries.
- `test_artifacts/trajectories/`: agent output trajectory JSON files for the 60 official test queries.
- `prompt_template/system_prompt_template.md.j2`: system prompt template with placeholders.

## Credentials

`.env` and Adobe credentials are intentionally excluded. To run real Adobe API mode, provide credentials locally through a private `.env` file using `.env.example` as the template.
