#!/bin/bash
# Bifrost Workspace Cleanup Script
# Removes unnecessary files and models

echo "=== Bifrost Cleanup ==="
echo ""

# Create backup list
echo "Creating backup list of deleted files..."
cat > deleted_files.txt <<EOF
# Files deleted on $(date)

## Large Model (5.5GB saved)
paligemma-keras-pali_gemma_3b_224-v4/

## Duplicate/Test Inference Scripts
fast_inference.py
inference_local.py
inference.py
quick_finetuned_inference.py
quick_inference.py
run_local.py
test_paligemma_4bit.py
test_paligemma_inference.py

## VM Automation Scripts (32 files)
vm_check_size.sh
vm_check.sh
vm_download_adapter.sh
vm_download_model.sh
vm_fix_and_train.sh
vm_infer.sh
vm_prep_keras.sh
vm_quick_inference.sh
vm_quick_test.sh
vm_run_train.sh
vm_run_v2.sh
vm_setup_and_train.sh
vm_start_server.sh
vm_test_specific_images.sh
vm_train.sh
vm_train2.sh
vm_upload_model.sh
vm_upload_script.sh
vm_upload.sh

## Utility Scripts
monitor_inference.sh
setup_local.sh
analyze_dataset.py
EOF

echo "✓ Backup list saved to deleted_files.txt"
echo ""

# Delete large Keras model
echo "[1/4] Deleting Keras model (5.5GB)..."
rm -rf paligemma-keras-pali_gemma_3b_224-v4/
echo "✓ Deleted paligemma-keras-pali_gemma_3b_224-v4/"

# Delete duplicate inference scripts
echo ""
echo "[2/4] Deleting duplicate/test inference scripts..."
rm -f fast_inference.py inference_local.py inference.py
rm -f quick_finetuned_inference.py quick_inference.py run_local.py
rm -f test_paligemma_4bit.py test_paligemma_inference.py
echo "✓ Deleted 8 duplicate inference scripts"

# Delete VM automation scripts
echo ""
echo "[3/4] Deleting VM automation scripts..."
rm -f vm_*.sh
echo "✓ Deleted all vm_*.sh scripts"

# Delete utility scripts
echo ""
echo "[4/4] Deleting utility scripts..."
rm -f monitor_inference.sh setup_local.sh analyze_dataset.py
echo "✓ Deleted utility scripts"

# Summary
echo ""
echo "=== Cleanup Complete ==="
echo ""
echo "Kept files:"
echo "  Scripts (5):"
echo "    - cpu_inference.py (CPU inference)"
echo "    - quick_test.py (MPS/GPU inference)"
echo "    - prep_paligemma_dataset.py (dataset prep)"
echo "    - finetune_paligemma.py (training)"
echo "    - train_server.py (training REPL)"
echo "    - training_logs.md (logs)"
echo ""
echo "  Models (1.0GB):"
echo "    - paligemma_stockout_model/ (fine-tuned model)"
echo ""
echo "  Datasets (224MB):"
echo "    - paligemma_dataset/ (processed)"
echo "    - Empty Spaces Detection in Shelf Data.coco/ (original)"
echo ""
echo "Space saved: ~5.5GB"
echo ""
