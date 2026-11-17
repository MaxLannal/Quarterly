"""Print the OpenAPI document as JSON (used by `make api-client`)."""

import json
import os
import sys

# Only prints the schema and never serves, so it needs no deployment settings.
os.environ["ENVIRONMENT"] = "development"

from api.main import create_app


def main() -> None:
    json.dump(create_app().openapi(), sys.stdout, indent=2, sort_keys=True)
    sys.stdout.write("\n")


if __name__ == "__main__":
    main()
