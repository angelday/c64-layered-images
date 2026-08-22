#!/usr/bin/env bash
set -euo pipefail

images_root="${1:-images}"
failures=0
image_count=0

fail() {
    printf 'error: %s\n' "$*" >&2
    failures=$((failures + 1))
}

if ! command -v jq >/dev/null 2>&1; then
    printf 'error: jq is required\n' >&2
    exit 2
fi

if ! command -v file >/dev/null 2>&1; then
    printf 'error: file is required\n' >&2
    exit 2
fi

if [ ! -d "$images_root" ]; then
    printf 'error: image directory not found: %s\n' "$images_root" >&2
    exit 2
fi

validate_manifest() {
    local manifest="$1"

    jq -e '
        def text: type == "string" and length > 0;
        def png: type == "string" and test("^[a-z0-9]+(-[a-z0-9]+)*\\.png$");
        def duration: type == "number" and . > 0 and floor == .;
        def frame($fallback):
            if type == "string" then
                png and ($fallback | duration)
            elif type == "object" then
                (.file | png) and ((.durationMs // $fallback) | duration)
            else
                false
            end;
        def animation:
            type == "object" and
            (.durationMs? as $fallback |
                (($fallback == null) or ($fallback | duration)) and
                (.frames | type == "array" and length > 0 and all(.[]; frame($fallback))));
        def phase:
            if (.role? | IN("phaseIntent", "phaseA", "phaseB")) then
                (.phaseGroup | text)
            else
                true
            end;
        def layer:
            type == "object" and
            ((.role? == null) or (.role | IN("background", "data", "overlay", "sprite", "phaseIntent", "phaseA", "phaseB"))) and
            (.file? as $file |
                (.animation? as $animation |
                    (($file == null) or ($file | png)) and
                    (($animation == null) or ($animation | animation)) and
                    ($file != null or $animation != null))) and
            phase;
        type == "object" and
        (.name | text) and
        (.author | text) and
        (if .layers? == null then
            ((.image? // "artwork.png") | png)
        else
            (.layers | type == "array" and length > 0 and all(.[]; layer)) and
            (.layers[1:] | all(.[]; .role? != "background"))
        end)
    ' "$manifest" >/dev/null
}

asset_files() {
    jq -r '
        if .layers? == null then
            .image // "artwork.png"
        else
            .layers[] |
            (.file? // empty),
            (.animation?.frames[]? |
                if type == "string" then . else .file // empty end)
        end
    ' "$1"
}

for folder in "$images_root"/*; do
    [ -d "$folder" ] || continue
    image_count=$((image_count + 1))
    id=$(basename "$folder")
    manifest="$folder/manifest.json"
    preview="$folder/preview.jpg"

    if [[ ! "$id" =~ ^[a-z0-9]+(-[a-z0-9]+)*$ ]]; then
        fail "$id: folder name must use lowercase kebab-case"
    fi

    if [ ! -f "$manifest" ]; then
        fail "$id: manifest.json is required"
        continue
    fi

    if ! jq empty "$manifest" >/dev/null 2>&1; then
        fail "$id: manifest.json is not valid JSON"
        continue
    fi

    if ! validate_manifest "$manifest"; then
        fail "$id: manifest.json does not meet the layered image requirements"
        continue
    fi

    if [ ! -f "$preview" ]; then
        fail "$id: preview.jpg is required"
    elif [ "$(file --brief --mime-type "$preview")" != "image/jpeg" ]; then
        fail "$id: preview.jpg must be a JPEG image"
    fi

    while IFS= read -r asset; do
        if [[ ! "$asset" =~ ^[a-z0-9]+(-[a-z0-9]+)*\.png$ ]]; then
            fail "$id: asset filename must use lowercase kebab-case: $asset"
        elif [ ! -f "$folder/$asset" ]; then
            fail "$id: manifest names missing asset: $asset"
        fi
    done < <(asset_files "$manifest")

    while IFS= read -r -d '' asset_path; do
        asset=$(basename "$asset_path")
        if [[ ! "$asset" =~ ^[a-z0-9]+(-[a-z0-9]+)*\.png$ ]]; then
            fail "$id: PNG filename must use lowercase kebab-case: $asset"
        fi
    done < <(find "$folder" -maxdepth 1 -type f -name '*.png' -print0)
done

if [ "$image_count" -eq 0 ]; then
    printf 'error: no image folders found in %s\n' "$images_root" >&2
    exit 2
fi

if [ "$failures" -gt 0 ]; then
    printf 'Validation failed with %d error(s).\n' "$failures" >&2
    exit 1
fi

printf 'Validated %d image folder(s).\n' "$image_count"
