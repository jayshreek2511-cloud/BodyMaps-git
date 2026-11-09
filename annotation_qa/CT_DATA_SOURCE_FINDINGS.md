# CT data source findings

Date: 2026-11-07

## Summary

The 38 selected labelmaps have corresponding CT objects in the public Hugging Face mirror `BodyMaps/iPanTSMini`, but those CTs are not present in the current local `D:\PanTS_data` tree. An unauthenticated metadata lookup returned an object record and size for all 38 expected per-case CT paths. No CT content was downloaded or opened, so metadata presence does not verify archive integrity or image-label geometry.

## 1. Original/local storage convention

The BodyMaps backend expects PanTS images at:

`<PANTS_PATH>/image_only/PanTS_########/ct.nii.gz`

and combined masks at:

`<PANTS_PATH>/mask_only/PanTS_########/combined_labels.nii.gz`.

`flask-server/constants.py` defines `PANTS_PATH`, `ct.nii.gz`, and `combined_labels.nii.gz` (lines 30, 53, 55). The API constructs the same per-case image path (for example `flask-server/api/api_blueprint.py`, lines 861 and 875-885). The repository README describes `PANTS_PATH` as the local PanTS data root; the annotation QA README describes the mask layout and says Stage 0 does not read images.

On this laptop, `D:\PanTS_data\labels` contains the shortlisted organ labelmaps. Searching `D:\PanTS_data` found CT files only in `ct_review` for case numbers 1, 4, 40, 43, 112, and 170; none is among the 38 selected case IDs. `C:\PanTS_local` is absent. The local `PanTSMini_Label.tar.gz` is a label archive, not a CT archive.

## 2. Hugging Face and archive availability

The public dataset repository `BodyMaps/PanTSMini` has 13 listed files: ten CT archive shards, a README, metadata workbook, and repository attributes. The image shards are:

- `PanTSMini_ImageTr_00000001_00001000.tar.gz`
- `PanTSMini_ImageTr_00001001_00002000.tar.gz`
- `PanTSMini_ImageTr_00002001_00003000.tar.gz`
- `PanTSMini_ImageTr_00003001_00004000.tar.gz`
- `PanTSMini_ImageTr_00004001_00005000.tar.gz`
- `PanTSMini_ImageTr_00005001_00006000.tar.gz`
- `PanTSMini_ImageTr_00006001_00007000.tar.gz`
- `PanTSMini_ImageTr_00007001_00008000.tar.gz`
- `PanTSMini_ImageTr_00008001_00009000.tar.gz`
- `PanTSMini_ImageTe_00009001_00009901.tar.gz`

The archive repository is about 346 GB in total; individual 1,000-case training shards are roughly 34-37 GB and the final test shard is about 28 GB. These are archives, so fetching one case from that repository would require handling its containing shard.

There is also a per-case mirror, `BodyMaps/iPanTSMini`, with paths of the form `image_only/PanTS_########/ct.nii.gz`. The existing `flask-server/scripts/stage_quiz_dataset.py` sets this as its default dataset repository (line 41), inventories its files (lines 92-102 and 399-410), and constructs individual image paths (line 364). The backend also has a per-case Hugging Face fallback (lines 875-885 of `api_blueprint.py`).

A metadata-only `HfApi.get_paths_info` query with authentication explicitly disabled returned records for all 38 shortlist paths. Reported individual object sizes ranged from about 0.002 to 0.134 GB. No bytes were downloaded. Thus the mirror supports case-ID-to-file lookup for every selected case; the exact naming rule is `image_only/<case_id>/ct.nii.gz`.

## 3. Manifest

No existing local manifest mapping these 38 case IDs to CT filenames or paths was found under `D:\PanTS_data` or in the repository's dataset scripts/configuration. A separate case-quality manifest setting in the backend is for ranking metadata, not a CT file map. The staging script can write `quiz/staging_manifest.v1.json` for a staged cohort, but that is an output of cohort staging, not a pre-existing full-dataset CT manifest. For the individual mirror, the case ID maps deterministically to the path above; the Hugging Face repository inventory supplies the object list.

## 4. Access and credentials

The `BodyMaps/PanTSMini` file listing and all 38 `BodyMaps/iPanTSMini` path metadata lookups succeeded with Hugging Face authentication disabled. The staging downloader uses ordinary HTTPS requests and does not configure a token. No credential requirement was observed for public repository metadata or path lookup. Actual file transfer was not tested, so this finding does not guarantee transfer speed or availability. The Hugging Face dataset card lists the license as CC-BY-NC-SA-4.0; use must follow that license. The BodyMaps website viewer is a separate service and may require an account to open a case.

## Conclusion

All 38 requested CTs are discoverable individually through the per-case Hugging Face mirror, with large sharded CT archives as an alternative. The next retrieval step can target only those 38 exact files; this inspection did not download anything and did not inspect any CT content.

## Evidence

- Repository: `flask-server/constants.py:30,53,55`; `flask-server/scripts/stage_quiz_dataset.py:41,92-102,105-110,176,364,386-410`; `flask-server/api/api_blueprint.py:861,875-885`; `README.md`; `annotation_qa/README.md`.
- Hugging Face public dataset pages: [BodyMaps/PanTSMini](https://huggingface.co/datasets/BodyMaps/PanTSMini) and [BodyMaps/iPanTSMini](https://huggingface.co/datasets/BodyMaps/iPanTSMini).
- Local checks: metadata listings only; no download performed.
