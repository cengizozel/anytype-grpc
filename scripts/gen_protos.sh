#!/usr/bin/env bash
# Regenerate the Python gRPC bindings from the vendored protos.
# Run this only when you update the vendored protos to match a new Anytype version.
#
#   pip install grpcio-tools
#   ./scripts/gen_protos.sh
#
set -euo pipefail
cd "$(dirname "$0")/.."

OUT="src/anytype_grpc/_pb"
rm -rf "$OUT"
mkdir -p "$OUT"

find protos -name "*.proto" | xargs python -m grpc_tools.protoc \
  -I protos \
  --python_out="$OUT" \
  --grpc_python_out="$OUT"

echo "Generated bindings into $OUT"
echo "The generated modules use absolute imports (pb.protos.*); the package adds"
echo "_pb/ to sys.path at import time so they resolve."
