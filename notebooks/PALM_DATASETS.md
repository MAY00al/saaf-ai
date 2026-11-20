# Aerial date palm dataset audit

The Phase 6 investigation selected the Al Ain release for a research-only, image-level experiment. The Roboflow assessments below are findings from the team's dataset inspection.

| Candidate | Documented imagery and labels | Size, splits, and permissions | Assessment |
| --- | --- | --- | --- |
| [Roboflow Date Palm Crown v4](https://universe.roboflow.com/sharif-btsla/date-palm-crown/dataset/4) | One crown bounding-box class. The investigation attributed 94.6% of images to three candidate recording sessions. | 1,731 images. The investigation confirmed source-level leakage across splits and found third-party image rights uncertain. | Rejected. |
| [Roboflow Dat Palm Fx v1](https://universe.roboflow.com/palm-oil-vj5ii/dat-palm-fx-vfhm6) | Inspected imagery appears to represent oil palms. | 4,802 images. Candidate source groups overlap across splits. | Rejected. |
| [Al Ain Palm-Tree Dataset](https://github.com/NourO93/Palm-Tree-Dataset) | Al Ain Municipality, UAE. Aerial TIFFs at 256 × 256 px with Pascal VOC boxes in a single `palmtree` class. Visual imagery and annotation review passed. No georeferencing was available in the inspected image. | 1,078 TIFFs, 922 matching XML files, 156 excluded unlabeled images, and 9,874 boxes. Exact duplicate groups and pHash pairs at Hamming distance ≤ 5 both numbered zero. The original test directory had no usable images. Research and educational use only. Commercial use is prohibited. | Selected for an experimental image-level split, subject to confirmation that the intended hackathon use complies. Geographic independence remains unverified. |
| [Saudi UAV counting study](https://www.mdpi.com/2073-4395/11/8/1458) | Study describes drone imagery from two Saudi regions with roughly 11,000 annotated palm instances. | Authors make the data available on request because of privacy issues. Public export, dataset license and usable split manifests were not verified. | Relevant for future local validation if the authors grant access. |

[ESA's Sentinel‑2 instrument specification](https://www.esa.int/media/sentinel-2-en-339395) lists its finest native bands at 10 m. A 10 m pixel covers a larger area than the 1 m pixel used in the Al Ain aerial study. SAAF has no evidence that Sentinel‑2 can reliably separate individual neighboring palm crowns in this workflow. Use high-resolution authorized aerial imagery for per-crown boxes. Any Sentinel‑2 plantation-cover analysis would be a separate coarse-scale product with its own validation.

## Experimental evaluation

The [Colab notebook](train_palm_yolo_colab.ipynb) downloads the [pinned public revision](https://github.com/NourO93/Palm-Tree-Dataset/tree/593352ae5f0e8fa460ad30afd13cc95c01bcc056) after the user confirms permitted hackathon use. It preserves the archive, pairs TIFF/XML by stem, and rechecks inventory, image dimensions, class, box validity, and duplicates. It writes derived PNG images and YOLO labels with a single `palm_tree` class, then splits the sorted paired images with seed 2026 into 737 training, 92 validation, and 93 test images. The split manifest records exact membership.

The split supports evaluation on this Al Ain release only. Duplicate checks leave open the possibility of overlapping imagery and shared geographic sources. Geographic generalization requires an independently sourced, labeled test set. Select settings on validation data and freeze them before scoring the test split. No trained SAAF metrics are available yet.
