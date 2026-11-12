"""Print the OpenAPI document as JSON (used by `make api-client`)."""

import json
import sys

from api.main import create_app


def main() -> None:
    json.dump(create_app().openapi(), sys.stdout, indent=2, sort_keys=True)
    sys.stdout.write("\n")


if __name__ == "__main__":
    main()
