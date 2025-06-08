#!/bin/bash

# This script is used to generate diagrams from Mermaid files and compare them with the existing ones.
# Usage example:
# ./generate_diagrams.sh diagram1.mmd diagram2.mmd

if [ "$#" -eq 0 ]; then
    echo "No files to handle."
    exit 0
fi

EXIT_CODE=0

for file in "$@"; do
    if [[ "$file" != *.mmd ]]; then
        continue
    fi

    svg_file="${file%.mmd}.svg"
    tmp_svg_file="${file%.mmd}.tmp.svg"

    docker run --rm -u $(id -u):$(id -g) -v "$(pwd)/$(dirname "$file"):/data" minlag/mermaid-cli \
        -i "/data/$(basename "$file")" -o "/data/$(basename "$tmp_svg_file")"

    if [[ ! -f "$svg_file" ]]; then
        echo "Create new diagram: $(basename "$svg_file")"
        mv "$tmp_svg_file" "$svg_file"
        EXIT_CODE=1
        continue
    fi

    old_hash=$(sha256sum "$svg_file" | awk '{print $1}')
    new_hash=$(sha256sum "$tmp_svg_file" | awk '{print $1}')
    if [[ "$old_hash" != "$new_hash" ]]; then
        echo "Diff found for: $(basename "$svg_file")"
        EXIT_CODE=1
    fi

    mv "$tmp_svg_file" "$svg_file"
done

exit $EXIT_CODE
