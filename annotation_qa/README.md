# Annotation QA Stage 0
Install Python 3.10+ and run pip install -r requirements.txt.
Masks use <root>/mask_only/PanTS_########/combined_labels.nii.gz; images are not read.
Run: python run_stage0.py --root C:\PanTS_local --out features.csv --workers 2.
Select cases with --cases 1-10 909; ranges include both endpoints.
Override ids with --label-id stomach=25; repeat for other ids as needed.
Use --resume to skip cases with both organ rows already in the CSV.
Feature extraction flushes every row; unreadable masks go to errors.log.
The first readable case prints all label ids present, including background.
Score: python score_stage0.py --input features.csv --out scored.csv.
Volume is in ml; bbox and centroid lengths are in mm.
Components, fragments, holes, and edge flags describe mask shape.
Contact columns are surface fractions; compactness is area cubed / volume squared.
Scores a and z are per-organ morphology and Isolation Forest anomaly scores.
Small cohorts warn and skip percentile cutoffs; guesses are review hints only.
