# Model weights

The deployable checkpoint is the **trained `best.pt`** produced by the Kaggle run `underwater_gate_bin_yolo26`.

## Important: do not use the root `yolo26n.pt` as the deployed model

The Kaggle output contains two different checkpoints:

- `yolo26n.pt` — the base/pretrained model used to start training
- `runs/detect/underwater_gate_bin_yolo26/weights/best.pt` — the trained checkpoint selected from the run

For the AUV, we need the **trained `best.pt`**, because it contains the learned gate/bin detector.

Use this deployment filename:

```text
AUV/src/auv_vision/weights/yolo26n.pt
```

The deployed file should therefore be a copy of Kaggle's trained `best.pt`, renamed to `yolo26n.pt` so the existing detector configuration does not need to change.

### Verified Kaggle artifact

Source:
- Run: `underwater_gate_bin_yolo26`
- Classes: `0 = gate`, `1 = bin`
- Training image size: `640`
- Epochs: `200` (best checkpoint from the completed run)
- `best.pt` size: `5,405,765` bytes
- `best.pt` SHA-256: `e214e42e66389969bc87736c991f9fa529ebf1b289618af23ca2fd07acf5b2ad`

The same Kaggle output reports final-epoch metrics around:
- Precision: `0.98708`
- Recall: `0.99194`
- mAP50: `0.99401`
- mAP50-95: `0.92844`

### Install locally

Copy **Kaggle's `runs/detect/underwater_gate_bin_yolo26/weights/best.pt`** into this repo and rename it:

```bash
cp /path/to/best.pt AUV/src/auv_vision/weights/yolo26n.pt
```

Verify it:

```bash
sha256sum AUV/src/auv_vision/weights/yolo26n.pt
```

Expected SHA-256:

```text
e214e42e66389969bc87736c991f9fa529ebf1b289618af23ca2fd07acf5b2ad
```

Then build:

```bash
cd AUV
colcon build --symlink-install
source install/setup.bash
```
