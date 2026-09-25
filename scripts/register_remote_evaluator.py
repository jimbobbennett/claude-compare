"""Register the claudism_spans remote evaluator in Arize AX through the REST API.

The ax CLI (0.35) can create a remote evaluator but not the EVALUATOR
integration it points at, which holds the endpoint URL, the auth header and
the input schema. The REST API can do both, so this calls it through the SDK
that ships inside the ax CLI, authenticated by your active ax profile. No key
is read or passed here.

Run it with the ax CLI's own Python, so the SDK and profile loader are there:

    ~/.local/share/uv/tools/arize-ax-cli/bin/python \\
        scripts/register_remote_evaluator.py https://<tunnel>.trycloudflare.com \\
        --space "<your space>"

Safe to re-run. A quick tunnel gets a new hostname each time it starts, so
after a restart run this again: it updates the endpoint on the existing
integration, and the evaluator follows because it references the integration.

Prints the integration and evaluator IDs as JSON.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

INTEGRATION_NAME = "claudism_spans endpoint"
EVALUATOR_NAME = "claudism_spans"
INPUT_SCHEMA = {
    "type": "object",
    "properties": {
        "output": {"type": "string", "description": "The blog post markdown"}
    },
    "required": ["output"],
}


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("base_url", help="https://<tunnel>.trycloudflare.com")
    parser.add_argument("--space", required=True)
    parser.add_argument(
        "--token-file", default=str(Path(__file__).resolve().parents[1] / ".eval-token")
    )
    args = parser.parse_args()

    from arize._generated import api_client as gen
    from ax.core.client_factory import make_client

    endpoint = args.base_url.rstrip("/") + "/v1/evaluate"
    token = Path(args.token_file).read_text().strip()
    headers = {"Authorization": f"Bearer {token}"}
    client, _ = make_client()
    api = client.integrations._api

    existing = api.list_integrations(type="EVALUATOR", name=INTEGRATION_NAME)
    match = next(
        (i.actual_instance for i in existing.integrations
         if i.actual_instance.name == INTEGRATION_NAME),
        None,
    )
    if match is None:
        body = gen.CreateIntegrationRequest(gen.CreateEvaluatorIntegrationRequest(
            type="EVALUATOR",
            name=INTEGRATION_NAME,
            description="v2.2 claudism span judge (blogwriter-eval-server)",
            config=gen.CreateEvaluatorIntegrationConfigInput(
                endpoint=endpoint, headers=headers, input_schema=INPUT_SCHEMA),
        ))
        integration_id = api.create_integration(create_integration_request=body) \
            .actual_instance.id
        action = "created"
    else:
        integration_id = match.id
        body = gen.UpdateIntegrationRequest(gen.UpdateEvaluatorIntegrationRequest(
            type="EVALUATOR",
            config=gen.UpdateEvaluatorIntegrationConfigInput(
                endpoint=endpoint, headers=headers, input_schema=INPUT_SCHEMA),
        ))
        api.update_integration(integration_id=integration_id,
                               update_integration_request=body)
        action = "updated"
    print(f"integration {action}: {endpoint}", file=sys.stderr)

    evaluators = client.evaluators.list(space=args.space, limit=100)
    found = next((e for e in evaluators.evaluators if e.name == EVALUATOR_NAME), None)
    if found is None:
        created = client.evaluators.create_remote_evaluator(
            name=EVALUATOR_NAME,
            space=args.space,
            integration_id=integration_id,
            commit_message="v2.2 prompt, gpt-6-luna",
            description="Claudism spans per 1000 words; explanation lists each "
            "span as start-end | category | quote",
        )
        evaluator_id = created.id
        print("evaluator created", file=sys.stderr)
    else:
        evaluator_id = found.id
        print("evaluator exists", file=sys.stderr)

    print(json.dumps({"integration_id": integration_id,
                      "evaluator_id": evaluator_id, "endpoint": endpoint}))
    return 0


if __name__ == "__main__":
    sys.exit(main())
