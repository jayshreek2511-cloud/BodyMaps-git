import { Niivue, NVImage } from "../PanTS-Demo/node_modules/@niivue/niivue/build/niivue/index.js";

const canvas = document.getElementById("viewer");
const ctInput = document.getElementById("ct-file");
const maskInput = document.getElementById("mask-file");
const loadButton = document.getElementById("load-pair");
const maskToggle = document.getElementById("mask-visible");
const opacityInput = document.getElementById("mask-opacity");
const status = document.getElementById("status");
const details = document.getElementById("details");

const nv = new Niivue({
  backColor: [0.035, 0.043, 0.055, 1],
  show3Dcrosshair: true,
  dragAndDropEnabled: false,
});
let loaded = false;
let overlayOpacity = Number(opacityInput.value) / 100;

function say(message, isError = false) {
  status.textContent = message;
  status.classList.toggle("error", isError);
}

function getSpatialDims(image) {
  const dims = image.hdr?.dims;
  const rank = Number(dims?.[0] ?? 0);
  if (!dims || !Number.isInteger(rank) || rank < 3 || dims.length < 4) return null;
  const spatialDims = Array.from(dims).slice(1, 4).map(Number);
  return spatialDims.every((n) => Number.isInteger(n) && n > 0) ? spatialDims : null;
}

function sameGrid(ct, mask) {
  // NiiVue 0.62 stores NIfTI dimensions in hdr.dims as [rank, x, y, z, ...].
  const ctDims = getSpatialDims(ct);
  const maskDims = getSpatialDims(mask);
  if (!ctDims || !maskDims) {
    return { ok: false, reason: "NiiVue did not expose valid 3D NIfTI dimensions. No overlay was drawn." };
  }
  if (ctDims.some((n, i) => n !== maskDims[i])) {
    return { ok: false, reason: `The CT grid ${ctDims.join(" × ")} and colon mask grid ${maskDims.join(" × ")} differ. No overlay was drawn.` };
  }
  const a = ct.matRAS ? Array.from(ct.matRAS) : [];
  const b = mask.matRAS ? Array.from(mask.matRAS) : [];
  if (a.length !== 16 || b.length !== 16 || a.some((n, i) => Math.abs(n - b[i]) > 0.001)) {
    return { ok: false, reason: "The CT and colon mask affine matrices differ. No overlay was drawn." };
  }
  return { ok: true, dims: ctDims };
}

function updateLoadButton() {
  loadButton.disabled = loaded || !ctInput.files?.length || !maskInput.files?.length;
}
ctInput.addEventListener("change", updateLoadButton);
maskInput.addEventListener("change", updateLoadButton);

maskToggle.addEventListener("change", () => {
  if (!loaded) return;
  nv.setOpacity(1, maskToggle.checked ? overlayOpacity : 0);
});
opacityInput.addEventListener("input", () => {
  overlayOpacity = Number(opacityInput.value) / 100;
  if (loaded && maskToggle.checked) nv.setOpacity(1, overlayOpacity);
});

loadButton.addEventListener("click", async () => {
  const ctFile = ctInput.files?.[0];
  const maskFile = maskInput.files?.[0];
  if (!ctFile || !maskFile) return;
  if (!ctFile.name.toLowerCase().endsWith(".nii.gz") || !maskFile.name.toLowerCase().endsWith(".nii.gz")) {
    say("Choose the .nii.gz CT and colon files shown above.", true);
    return;
  }
  loadButton.disabled = true;
  say("Reading the two local NIfTI files in this browser…");
  try {
    const [ct, mask] = await Promise.all([
      NVImage.loadFromFile({
        file: ctFile,
        name: ctFile.name,
        colormap: "gray",
        opacity: 1,
        cal_min: -160,
        cal_max: 240,
        trustCalMinMax: true,
      }),
      NVImage.loadFromFile({
        file: maskFile,
        name: maskFile.name,
        colormap: "red",
        opacity: overlayOpacity,
        cal_min: 0.5,
        cal_max: 1.5,
        ignoreZeroVoxels: true,
      }),
    ]);
    const grid = sameGrid(ct, mask);
    if (!grid.ok) throw new Error(grid.reason);

    await nv.attachToCanvas(canvas);
    nv.addVolume(ct);
    nv.addVolume(mask);
    nv.setSliceType(nv.sliceTypeMultiplanar);
    nv.setCustomLayout([
      { sliceType: nv.sliceTypeAxial, position: [0, 0, 0.5, 0.5] },
      { sliceType: nv.sliceTypeCoronal, position: [0.5, 0, 0.5, 0.5] },
      { sliceType: nv.sliceTypeSagittal, position: [0, 0.5, 0.5, 0.5] },
      { sliceType: nv.sliceTypeRender, position: [0.5, 0.5, 0.5, 0.5] },
    ]);
    nv.setOpacity(1, maskToggle.checked ? overlayOpacity : 0);
    nv.drawScene();
    loaded = true;
    maskToggle.disabled = false;
    opacityInput.disabled = false;
    details.textContent = `Grid ${grid.dims.join(" × ")} voxels | CT ${ctFile.name} | colon ${maskFile.name}`;
    say("Loaded. Scroll over an axial, coronal, or sagittal panel to move through slices; the 3D panel can be rotated and zoomed.");
    updateLoadButton();
  } catch (error) {
    say(error instanceof Error ? error.message : String(error), true);
    updateLoadButton();
  }
});