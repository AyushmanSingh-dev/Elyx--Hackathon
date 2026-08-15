# Model weights

The trained YOLO checkpoint is the only runtime artifact not stored in this branch.

Place the trained `yolo26n.pt` checkpoint here:

```text
AUV/src/auv_vision/weights/yolo26n.pt
```

Expected checkpoint:
- Source: the provided Kaggle trained model
- File: `yolo26n.pt`
- Classes: `0 = gate`, `1 = bin`

Both `gate_detector_node` and `bin_detector_node` use this same two-class checkpoint. The detector resolves the configured model path relative to the installed `auv_vision` package share directory.

The `.pt` binary is not uploaded through the current GitHub integration, so copy the provided checkpoint into this directory before running the full perception simulation.

Before building:

```bash
cp /path/to/yolo26n.pt AUV/src/auv_vision/weights/yolo26n.pt
cd AUV
colcon build --symlink-install
source install/setup.bash
```
