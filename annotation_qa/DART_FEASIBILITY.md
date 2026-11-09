# DART feasibility: segmentation vs diffusion correction

Checked 2026-11-08. No model files were downloaded; no inference, dependency installation, or GPU use was performed.

## Finding

There are two different models in this work:

- **DART-Seg** is the promptable 3D segmentation model. It takes a CT and a text prompt and predicts an organ mask. The paper describes it as a free-text promptable 3D segmentation model, using the VoxTell architecture, trained on labels corrected by DART.
- **DART (diffusion corrector)** is a separate shape-correction model. It takes an existing segmentation **probability map** plus a text description; it does not take the CT image. Its output is a corrected probability map that is thresholded to produce a mask.

The paper is clear about this separation: corrected labels are subsequently used to train DART-Seg, and the DART correction path operates on probabilities without medical images. [DART paper](https://arxiv.org/abs/2610.27605)

**Availability verdict:** I verified a Hugging Face model reference for DART-Seg, but could not verify from readable primary repository files that the actual diffusion corrector implementation, checkpoint, and per-class `t*` table are downloadable and usable. The paper states these assets “will be released”; that does not prove the release is available now. [DART paper, reproducibility statement](https://arxiv.org/abs/2610.27605)

A Hugging Face model-search result lists DART-Seg under `Koushik45048545309/DART-Seg` (39.3M parameters), while the paper links `Koushik45/DART-Seg`. I could not open either repository's file tree or source through the read-only web inspection. Treat this account/name difference and file availability as unresolved. [Hugging Face model search](https://huggingface.co/models?hardware=rx-5700&p=83&sort=trending)

## Requested implementation checks

| Check | Finding |
|---|---|
| Repository files and `dart_seg.py` | The linked HF repo's file tree and source were not readable. A secondary catalog describes an importable `dartseg.py`, but does not verify the exact file list or revision. I make no claim about `dart_seg.py` contents. [Secondary model catalog](https://savrn.com/models/licenses/cc-by-nc-sa-4-0) |
| Model architecture | The paper identifies DART-Seg as the VoxTell free-text promptable 3D segmentation architecture, trained on DART-corrected labels. The DART-10K card describes its DART-Seg v1 predictions as a residual 3D U-Net, channels 32-320, on 64-cubed patches at 2 mm, conditioned on Qwen3-Embedding-4B. These may describe different release/version details; the exact relationship is uncertain without the target source. [Paper](https://arxiv.org/abs/2610.27605) · [DART-10K card](https://huggingface.co/datasets/Koushik45048545309/Dart-10K) |
| `prompts.txt`: colon | **Not verified.** The paper gives a colon description for the diffusion corrector, but that does not prove DART-Seg's prompt file contains colon. |
| `prompts.txt`: stomach | **Not verified.** The paper mentions stomach as context in a pancreas description, not as proof of a stomach target prompt in DART-Seg. |
| Probability maps vs binary masks | DART correction consumes probabilities and thresholds its corrected result to a mask. DART-Seg's model description says it produces masks. Since inference source was unavailable, whether its API also exposes logits/probabilities or only a final mask is **unverified**. A hard binary labelmap is not the information-preserving input described for DART correction. [DART paper](https://arxiv.org/abs/2610.27605) |
| Corrector code, checkpoint, `t*` | Not verified as publicly accessible. The paper specifies DDPM ancestral sampling and per-class `t*` selected from `{50, 150, 250, 350, 450, 550, 650}`; it says code, weights, descriptions and per-class `t*` will be released. Do not assume these files are present. [DART paper](https://arxiv.org/abs/2610.27605) |
| Dependencies | The model repository's dependency manifest was not readable, so no exact install list can be stated. The paper describes a MONAI 3D diffusion U-Net and frozen all-MiniLM-L6-v2 encoder for the corrector; PyTorch, MONAI and the text encoder/tokenizer stack are likely requirements, to be confirmed against the released requirements. DART-Seg dependencies must be checked separately. [DART paper](https://arxiv.org/abs/2610.27605) |
| CPU/GPU | No official CPU support or CPU timing was verified. The paper reports corrector timing on an AMD MI250X GPU (0.59 s per 128-cubed probability map); corpus processing and training also used GPUs. This establishes a GPU-tested path, not that CPU execution is impossible. CPU speed/support remains unconfirmed. [DART paper, implementation details](https://arxiv.org/abs/2610.27605) |

## Minimal one-case inference plan (not executed)

Use a **copy** of one local CT and a new output directory; never point output at the source CT or labels.

1. Inspect the readable DART-Seg model card/source revision. Verify the organ prompt and exact command, checkpoint loading, preprocessing and output options.
2. Run segmentation on one CT and one verified prompt only, writing to a new path. A secondary catalog mentions `--image` and `--prompts`, but the entrypoint and remaining options were not verified. This is therefore a template, not a runnable command:
   ```text
   python <verified DART-Seg entrypoint> --image <CT-copy.nii.gz> --prompts "<verified prompt>" <documented output arguments>
   ```
3. For the separate diffusion corrector, provide an upstream probability map, the matching anatomy description, and that class's released `t*`. A hard labelmap alone is not the specified input. Do not use the corrector until its source, weights, descriptions and `t*` are verified.
4. Check output geometry and review it visually against the CT. Keep original CT and labels read-only.

I did not run either model. There is not enough verified repository documentation to give a safe exact inference command or claim that the current DART-Seg release supports stomach and colon prompts.

## Sources checked

- Primary paper and appendices: [arXiv:2610.27605](https://arxiv.org/abs/2610.27605)
- Model reference named by the paper: [Koushik45/DART-Seg](https://huggingface.co/Koushik45/DART-Seg) (file tree not readable through the inspection interface)
- Similar model entry in HF search: [Hugging Face model search](https://huggingface.co/models?hardware=rx-5700&p=83&sort=trending)
- DART-Seg v1 architecture summary: [Koushik45048545309/Dart-10K dataset card](https://huggingface.co/datasets/Koushik45048545309/Dart-10K)
- Secondary interface summary only: [Savrn catalog](https://savrn.com/models/licenses/cc-by-nc-sa-4-0)
