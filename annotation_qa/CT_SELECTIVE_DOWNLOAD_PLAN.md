# Selective CT download plan for visual validation

Date: 2026-11-07
Status: plan only; no CT content has been downloaded.

## Scope and source verification

This plan covers the 38 unique case IDs in `D:\PanTS_data\component_study\visual_validation_case_inventory.csv`. All 38 corresponding organ labelmaps were present in the inventory. The local inventory found no CT for these selected cases. Repository findings are recorded in `CT_DATA_SOURCE_FINDINGS.md`.

The selected CT objects are in the public Hugging Face dataset repository `BodyMaps/iPanTSMini`, at `image_only/<case_id>/ct.nii.gz`. Metadata was retrieved without authentication at pinned revision `0254c148f3c05fd3913e42d16982b010a048167c`. Each returned path exactly matched its requested case ID. This avoids fetching the much larger sharded archives in `BodyMaps/PanTSMini`.

## Per-case object manifest

Sizes below are exact repository metadata byte sizes at the pinned revision. SHA-256 values are the available LFS content checksums for verifying completed downloads.

| Case ID | Hugging Face object path | Bytes | SHA-256 |
|---|---|---:|---|
| `PanTS_00000281` | `image_only/PanTS_00000281/ct.nii.gz` | 38,422,712 | `c7105e7c377204a66ac933db63a174466141b7b1be38006994045311b4bce164` |
| `PanTS_00000520` | `image_only/PanTS_00000520/ct.nii.gz` | 20,821,772 | `4aa0c4ac95e6054e19d29fcaa614aeedf4134c907de09d33a4e7178f4b43972b` |
| `PanTS_00000539` | `image_only/PanTS_00000539/ct.nii.gz` | 54,866,970 | `fb62b73ca3ccf4d62b301cc6e1a05e9ec779cd26a82f20ecc5dbf1417a0463eb` |
| `PanTS_00000728` | `image_only/PanTS_00000728/ct.nii.gz` | 44,880,152 | `39efacf811dc34d25cdfda1d6654581938d96efd9b871238ab0b9660e48e7eb8` |
| `PanTS_00000761` | `image_only/PanTS_00000761/ct.nii.gz` | 42,563,531 | `009a756c56ce53099dc4b3361b6ed0d743e432535b4ac5ee76c5f3c2b2b46786` |
| `PanTS_00001535` | `image_only/PanTS_00001535/ct.nii.gz` | 58,703,938 | `31c7362b1988047db3056c044304e68c978d8702b0135dc12598513cdedc674c` |
| `PanTS_00001840` | `image_only/PanTS_00001840/ct.nii.gz` | 6,617,199 | `e8ca573e735240d45d6269c47ec43b6f655ab029a40a4123c4f400a5af6cf5e2` |
| `PanTS_00002315` | `image_only/PanTS_00002315/ct.nii.gz` | 50,696,110 | `f9b9d08c3260e0dee60baf505c36e2773037aba76dd0d3f7ff25132fd6842283` |
| `PanTS_00002456` | `image_only/PanTS_00002456/ct.nii.gz` | 5,694,160 | `e27de82a900cd509ca1fbd429ad59c232b656202f4ec28740e94dee034cad4ee` |
| `PanTS_00002831` | `image_only/PanTS_00002831/ct.nii.gz` | 3,213,844 | `4c3171c6fedc7c176356248617b737ce697f8572c2e393d79859ff1b550b3e28` |
| `PanTS_00003014` | `image_only/PanTS_00003014/ct.nii.gz` | 45,191,647 | `2982fe9e4b3ab459055797384b9c720bb215e41ba0b7b981c55464985d508a35` |
| `PanTS_00003021` | `image_only/PanTS_00003021/ct.nii.gz` | 50,918,069 | `f94bfbd5e6d01e62986caaa87a5122fef863447797780af033ce832e1e5ec3b5` |
| `PanTS_00003510` | `image_only/PanTS_00003510/ct.nii.gz` | 64,663,637 | `b4e7584ef133f52f995385f5c92bf70db8b5275f12178acb4656af874a740fd5` |
| `PanTS_00003537` | `image_only/PanTS_00003537/ct.nii.gz` | 27,682,337 | `51c840fc3f43a9105d0e48bc7412e683536b4e6d1a4672cae74651c541338f09` |
| `PanTS_00003580` | `image_only/PanTS_00003580/ct.nii.gz` | 62,105,648 | `8202a2d77f0f0154c47421523b3e9ed9afe6db8c46c88eec2b03dc6c8c5472c1` |
| `PanTS_00003617` | `image_only/PanTS_00003617/ct.nii.gz` | 4,102,259 | `695555f988322ff8c0e9aa4832fe4f043f3ebbf400a2074d04e02bf648d841e7` |
| `PanTS_00003668` | `image_only/PanTS_00003668/ct.nii.gz` | 4,595,911 | `ecca3602c8ced936dab91c9e5c496ba0d43c602bf70d493899d3046386807799` |
| `PanTS_00003717` | `image_only/PanTS_00003717/ct.nii.gz` | 4,203,296 | `1375a3d35ad4792915a52d094851ada57afb9189bd2489beaec8dee16c3791f6` |
| `PanTS_00004497` | `image_only/PanTS_00004497/ct.nii.gz` | 34,450,136 | `acac9ad7f1ea644c83fce4754e530e44e36a83522faddf0e6287f5f4c74b3d5c` |
| `PanTS_00004934` | `image_only/PanTS_00004934/ct.nii.gz` | 54,953,307 | `6120f598d428498e991dc5d1565a1eddd22890d26b505be8e1e24ceee2e678cc` |
| `PanTS_00004937` | `image_only/PanTS_00004937/ct.nii.gz` | 10,417,536 | `f0a12717ec33017ee5a05ff607413f49428d5ab7d4b54591b0ff6b33fbe85149` |
| `PanTS_00004990` | `image_only/PanTS_00004990/ct.nii.gz` | 57,903,086 | `f42ebdb2b9b6e0a857506e6e709671ad17105ebc0ba4cd941dbd3d9ca4dd256f` |
| `PanTS_00005098` | `image_only/PanTS_00005098/ct.nii.gz` | 15,112,147 | `7ec91ef61ca5046aa86a210cb40a7dd9ccf11e929046b0fd7553cccf16a59797` |
| `PanTS_00005255` | `image_only/PanTS_00005255/ct.nii.gz` | 44,483,987 | `9976abd798b317d1d7a6e7a56d2119aa67894136b857e0b7c1e9933f2d7b5937` |
| `PanTS_00006127` | `image_only/PanTS_00006127/ct.nii.gz` | 11,646,162 | `2d4badaafa2f72fe61ff1f4342641720f205ac0ced7751b538977dd508f90ca0` |
| `PanTS_00006145` | `image_only/PanTS_00006145/ct.nii.gz` | 17,656,526 | `f08d50043118e1c2e1fc8b484946b1fd7af953dbf79ac136c643cfd12fae156b` |
| `PanTS_00006329` | `image_only/PanTS_00006329/ct.nii.gz` | 10,925,150 | `8687977b012ef60260e308dedb2af00bd7cc1090078bcdf5ffaf193a6b3a8477` |
| `PanTS_00006362` | `image_only/PanTS_00006362/ct.nii.gz` | 40,913,170 | `fea04521f0f36438624cc15586666b58baa58742fdbc6791f2cdf6495542a475` |
| `PanTS_00006444` | `image_only/PanTS_00006444/ct.nii.gz` | 50,771,085 | `af34efd96d5ff55692af0760b7b3414c7d729f47dce7d390d7b94e43855808f2` |
| `PanTS_00006787` | `image_only/PanTS_00006787/ct.nii.gz` | 20,010,257 | `096d901ef95959bf27c7f50f6bfb4225938c009810c728941b715afaede47436` |
| `PanTS_00006884` | `image_only/PanTS_00006884/ct.nii.gz` | 39,032,886 | `870789d824ce18eccf7db38ad6a2b0b63b96672f645d58c01561d4791d25d432` |
| `PanTS_00007468` | `image_only/PanTS_00007468/ct.nii.gz` | 6,903,203 | `9daccde2eae9fb29ecf61bf7d65e7f2fdd473b819ccfdc25b85c291f396cfbff` |
| `PanTS_00007508` | `image_only/PanTS_00007508/ct.nii.gz` | 1,852,082 | `d34933edb18c837caa2a446e7a95a014bf188aef1b0e4125a44cbd6009480983` |
| `PanTS_00007897` | `image_only/PanTS_00007897/ct.nii.gz` | 11,703,366 | `fef532f39fc75946e7961f5c1d4b4231273b0d490d4fb2a3516ef29844b35681` |
| `PanTS_00008113` | `image_only/PanTS_00008113/ct.nii.gz` | 133,941,343 | `c1cfd0e1d4beaa15d7bf469ca74d88cec68142073dfda6713975a6ca0667c938` |
| `PanTS_00008833` | `image_only/PanTS_00008833/ct.nii.gz` | 55,003,055 | `94bbb05cfea9e8dc7fceafb96209d522ff7788039ed36926d9118fee6b05373a` |
| `PanTS_00009275` | `image_only/PanTS_00009275/ct.nii.gz` | 7,064,916 | `faf07ac3fd2916b49f7a5dc00ee9304ecb68975da741398e34269114699f9c68` |
| `PanTS_00009742` | `image_only/PanTS_00009742/ct.nii.gz` | 54,379,488 | `70c593d10c079d4a7ef6245210e710a853b9458a76fd3cb8158979360abb2311` |

**Estimated payload total:** 1,269,066,080 bytes = 1.269066080 GB (decimal) = 1.181909889 GiB. This is the sum of the 38 object sizes and excludes protocol/cache overhead.

## Official individual-file download method

Use Hugging Face's supported `huggingface_hub.hf_hub_download` for each file, setting `repo_type="dataset"`, the exact object `filename`, pinned `revision`, and `token=False`. The returned cached file can then be copied to the requested destination after checks. The same library supports the `hf download` CLI, but a small Python loop is preferable for per-case validation and failure logging. Official references: [download guide](https://huggingface.co/docs/huggingface_hub/en/guides/download), [file-download API](https://huggingface.co/docs/huggingface_hub/en/package_reference/file_download), and [authentication guide](https://huggingface.co/docs/huggingface_hub/en/quick-start#authentication).

Example retrieval call (not executed):

```python
from huggingface_hub import hf_hub_download
cached_path = hf_hub_download(
    repo_id="BodyMaps/iPanTSMini",
    filename=f"image_only/{case_id}/ct.nii.gz",
    repo_type="dataset",
    revision="0254c148f3c05fd3913e42d16982b010a048167c",
    token=False,
)
```

## Destination, format, and extraction

Final destination for case `PanTS_########`:

`D:\PanTS_data\ct_review\shortlist_38\PanTS_########\ct.nii.gz`

The object is already a compressed NIfTI volume (`.nii.gz`), not a tar archive. No archive extraction is required. A NIfTI reader can read the gzip-compressed volume directly; leave it compressed on disk.

## Credentials and license

The metadata lookup for all 38 individual objects succeeded with authentication disabled (`token=False`). No credential was required for path/size/checksum metadata. Actual file transfer has not been attempted, so the plan does not claim a successful transfer test. Hugging Face's general rule is that public repositories can be accessed without login while private repositories require authentication; this repository is currently publicly listed. The dataset card identifies license `CC-BY-NC-SA-4.0`; follow its terms.

## Proposed safe download procedure

1. Read only the 38 case IDs from the inventory and reconstruct exactly `image_only/<case_id>/ct.nii.gz`; require an exact case/path match against the metadata response at the pinned revision. Never use a whole-repository snapshot or an archive download.
2. Query object size and LFS SHA-256 before transfer. Record the expected size and checksum for each case in the run log.
3. For each target path, if a file already exists, skip it only if its byte size matches, SHA-256 matches, nibabel opens it as NIfTI, and its dimensions/affine/voxel spacing are consistent with the corresponding organ labelmap. Log `skipped_valid` for these files.
4. If the target exists but fails validation, do not overwrite it. Log a failure with case ID and validation reason and leave the file for manual review. Do not write into or alter `D:\PanTS_data\labels`.
5. For a missing target, call `hf_hub_download` for that one exact file. Copy the returned cache file to a unique temporary `.part` file inside the case directory, then verify exact byte size and SHA-256. Open the temporary file with nibabel and compare dimensions and physical geometry to the existing labelmap. Only after all checks pass, atomically rename the `.part` file to `ct.nii.gz`, guarded so an already-existing target is never replaced.
6. Log each case as `downloaded_valid`, `skipped_valid`, or `failed`, including object path, expected/actual bytes, checksum result, and exception/reason. Continue after per-case failures and exit nonzero if any failed case remains, so no case is silently skipped. Preserve a final summary of all 38 outcomes.
7. Keep temporary download/cache data separate from `labels`; never move, rename, edit, or replace labelmaps.

## Limits of this plan

The per-case path, size, and SHA-256 metadata were checked. CT bytes, NIfTI readability, transfer behavior, and CT-to-label geometry remain unverified until an authorized download run. No download has been started.
