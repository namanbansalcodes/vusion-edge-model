"""
Converts COCO bbox annotations into grid-zone text labels for PaliGemma fine-tuning.
Each image gets a prompt/response pair like:
  prompt: "detect stock out"
  response: "stock out detected at top-left, middle-center"

Output: a JSONL file + copies images into a clean folder.
"""

import json
import os
import shutil

ANNO_PATH = "Empty Spaces Detection in Shelf Data.coco/train/_annotations.coco.json"
IMG_DIR = "Empty Spaces Detection in Shelf Data.coco/train"
OUT_DIR = "paligemma_dataset"
OUT_JSONL = os.path.join(OUT_DIR, "dataset.jsonl")
OUT_IMG_DIR = os.path.join(OUT_DIR, "images")

PROMPT = "detect stock out"

# 3x3 grid zone names
COL_NAMES = ["left", "center", "right"]
ROW_NAMES = ["top", "middle", "bottom"]


def bbox_to_zone(bbox, img_w, img_h):
    """Convert a COCO bbox [x, y, w, h] to a grid zone string."""
    x, y, w, h = [float(v) for v in bbox]
    cx = (x + w / 2) / img_w
    cy = (y + h / 2) / img_h
    col = min(int(cx * 3), 2)
    row = min(int(cy * 3), 2)
    return f"{ROW_NAMES[row]}-{COL_NAMES[col]}"


def main():
    with open(ANNO_PATH) as f:
        data = json.load(f)

    img_lookup = {img["id"]: img for img in data["images"]}

    # Group annotations by image
    anns_by_img = {}
    for a in data["annotations"]:
        anns_by_img.setdefault(a["image_id"], []).append(a)

    os.makedirs(OUT_IMG_DIR, exist_ok=True)

    entries = []
    for img_id, img_info in img_lookup.items():
        anns = anns_by_img.get(img_id, [])
        fname = img_info["file_name"]
        w, h = img_info["width"], img_info["height"]

        if anns:
            # Get unique zones (deduplicate)
            zones = sorted(set(bbox_to_zone(a["bbox"], w, h) for a in anns))
            response = "stock out detected at " + ", ".join(zones)
        else:
            response = "no stock out detected"

        # Copy image
        src = os.path.join(IMG_DIR, fname)
        dst = os.path.join(OUT_IMG_DIR, fname)
        if os.path.exists(src):
            shutil.copy2(src, dst)

        entries.append({
            "image": fname,
            "prompt": PROMPT,
            "response": response,
            "num_stockouts": len(anns),
            "zones": zones if anns else [],
        })

    # Write JSONL
    with open(OUT_JSONL, "w") as f:
        for e in entries:
            f.write(json.dumps(e) + "\n")

    print(f"Dataset created: {len(entries)} samples")
    print(f"  Images -> {OUT_IMG_DIR}")
    print(f"  Labels -> {OUT_JSONL}")

    # Quick stats
    from collections import Counter
    zone_counts = Counter()
    for e in entries:
        for z in e["zones"]:
            zone_counts[z] += 1
    print(f"\nZone distribution:")
    for z, c in zone_counts.most_common():
        print(f"  {z}: {c}")

    # Show a few samples
    print(f"\nSample entries:")
    for e in entries[:5]:
        print(f"  [{e['image'][:30]}...] -> {e['response']}")


if __name__ == "__main__":
    main()
