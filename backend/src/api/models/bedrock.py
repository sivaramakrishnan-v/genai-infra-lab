from __future__ import annotations

import json
import logging
import os
from typing import Any, Dict, List

import boto3

logger = logging.getLogger(__name__)


def converse_once(prompt: str, *, model_id: str = "amazon.nova-micro-v1:0", region: str | None = None) -> str:
    """
    Send a single prompt to Bedrock and return the response text.
    """
    client = boto3.client("bedrock-runtime", region_name=region or os.environ.get("AWS_REGION", "us-east-1"))
    response = client.converse(
        modelId=model_id,
        messages=[
            {
                "role": "user",
                "content": [
                    {"text": prompt}
                ]
            }
        ],
        inferenceConfig={
            "maxTokens": 100,
            "temperature": 0.2
        }
    )
    output: List[Dict[str, Any]] = response["output"]["message"]["content"]
    return output[0]["text"] if output else ""


def main() -> None:
    """
    Smoke test for Bedrock integration. Requires AWS credentials and Bedrock access.
    """

    logging.basicConfig(level=logging.INFO)
    prompt = os.environ.get("BEDROCK_PROMPT", "what is sre?")
    region = os.environ.get("AWS_REGION", "us-east-1")

    try:
        result = converse_once(prompt, region=region)
        logger.info("Bedrock response: %s", result)
    except Exception:
        logger.exception("Bedrock smoke test failed. Ensure credentials and permissions are configured.")
        raise


if __name__ == "__main__":
    main()
