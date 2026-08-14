# Model weights

The trained YOLO checkpoint is the only runtime artifact not stored in this branch.

Place the Kaggle `best.pt` checkpoint here and rename it:

```text
AUV/src/auv_vision/weights/gate_detector_v2.pt
```

Expected checkpoint:
- Source: Kaggle run `underwater_gate_bin_yolo26`
- File: `best.pt`
- SHA-256: `565980e76b727960188a4368fa031323fb22a7f2946c3841faa595c77c2cba93`
- Size: 5,380,064 bytes in the extracted workspace copy

The detector resolves the configured model path relative to the installed
`auv_vision` package share directory. The `.pt` file is deliberately not
tracked by Git because the branch's `.gitignore` excludes model binaries.

Before building:

```bash
cp /path/to/best.pt AUV/src/auv_vision/weights/gate_detector_v2.pt
cd AUV
colcon build --symlink-install
source install/setup.bash
```
