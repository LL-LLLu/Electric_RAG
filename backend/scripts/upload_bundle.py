#!/usr/bin/env python3
"""
Upload a pre-processed bundle to the Electric RAG server.

Usage:
    python scripts/upload_bundle.py drawing_bundle.zip \
        --server https://electric-rag-backend.onrender.com \
        --api-key YOUR_KEY \
        --project-id 1
"""

import argparse
import os
import sys

try:
    import requests
except ImportError:
    print("Error: 'requests' package is required. Install with: pip install requests")
    sys.exit(1)


def upload_bundle(
    bundle_path: str,
    server: str,
    api_key: str | None = None,
    project_id: int | None = None,
) -> None:
    """Upload a zip bundle to the server's import endpoint."""
    if not os.path.exists(bundle_path):
        print(f"Error: File not found: {bundle_path}")
        sys.exit(1)

    file_size = os.path.getsize(bundle_path)
    print(f"Uploading {bundle_path} ({file_size / 1024 / 1024:.1f} MB)")

    url = f"{server.rstrip('/')}/api/documents/import"
    params = {}
    if project_id is not None:
        params["project_id"] = project_id

    headers = {}
    if api_key:
        headers["X-API-Key"] = api_key
    else:
        print("Warning: No API key provided. Request may be rejected by the server.")

    with open(bundle_path, "rb") as f:
        files = {"file": (os.path.basename(bundle_path), f, "application/zip")}

        try:
            response = requests.post(
                url,
                files=files,
                params=params,
                headers=headers,
                timeout=300,  # 5-minute timeout
            )
        except requests.ConnectionError:
            print(f"Error: Could not connect to {server}")
            sys.exit(1)
        except requests.Timeout:
            print("Error: Upload timed out (5 minute limit)")
            sys.exit(1)

    if response.status_code == 200:
        result = response.json()
        print(f"Success! Imported document ID: {result['document_id']}")
        print(f"  Filename: {result['original_filename']}")
        print(f"  Pages: {result['page_count']}")
        print(f"  Equipment: {result['equipment_count']}")
        print(f"  Relationships: {result['relationship_count']}")
        print(f"  Message: {result['message']}")
    else:
        print(f"Error {response.status_code}: {response.text}")
        sys.exit(1)


def main():
    parser = argparse.ArgumentParser(
        description="Upload a pre-processed bundle to the Electric RAG server."
    )
    parser.add_argument("bundle", help="Path to the .zip bundle file")
    parser.add_argument(
        "--server",
        default=os.environ.get("ELECTRIC_RAG_SERVER", "http://localhost:8000"),
        help="Server URL (default: $ELECTRIC_RAG_SERVER or http://localhost:8000)",
    )
    parser.add_argument(
        "--api-key",
        default=os.environ.get("ELECTRIC_RAG_API_KEY"),
        help="API key for authentication (default: $ELECTRIC_RAG_API_KEY)",
    )
    parser.add_argument(
        "--project-id",
        type=int,
        default=None,
        help="Project ID to assign the document to",
    )

    args = parser.parse_args()
    upload_bundle(args.bundle, args.server, args.api_key, args.project_id)


if __name__ == "__main__":
    main()
