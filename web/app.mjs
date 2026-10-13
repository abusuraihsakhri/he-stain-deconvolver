import {deconvolvePixels, MAX_PIXELS} from "./deconvolution.mjs";

const $ = id => document.getElementById(id);
const form = $("form");
const input = $("file");
const original = $("original");
const processButton = $("process");
let sourceName = "";
let sequence = 0;
let lastStats = null;

function message(text, type = "") {
  $("status").textContent = text;
  $("status").className = "message" + (type ? " " + type : "");
}

function safeStem(name) {
  return (name.replace(/\.[^.]+$/, "").replace(/[^a-zA-Z0-9_-]/g, "_").slice(0,80) || "histology");
}

function clearResults() {
  $("results").hidden = true;
  $("channels").replaceChildren();
  lastStats = null;
}

async function showFile(file) {
  const token = ++sequence;
  clearResults();
  processButton.disabled = true;
  original.style.display = "none";
  $("placeholder").hidden = false;
  $("dimensions").textContent = "Images remain in your browser; no server connection is required.";
  if (!file) {
    message("Select an image to begin.");
    return;
  }
  if (file.size > 50 * 1024 * 1024) {
    message("File exceeds the 50 MB input limit.", "error");
    return;
  }
  message("Reading image…");
  let bitmap;
  try {
    bitmap = await createImageBitmap(file);
    if (token !== sequence) return;
    if (bitmap.width * bitmap.height > MAX_PIXELS) throw new Error("Image exceeds the 12-megapixel limit.");
    const ctx = original.getContext("2d", {willReadFrequently:true});
    if (!ctx) throw new Error("Unable to initialize image canvas.");
    original.width = bitmap.width;
    original.height = bitmap.height;
    ctx.fillStyle = "#ffffff";
    ctx.fillRect(0,0,original.width,original.height);
    ctx.drawImage(bitmap,0,0);
    original.style.display = "block";
    $("placeholder").hidden = true;
    $("dimensions").textContent = bitmap.width + " × " + bitmap.height + " pixels · " + file.name;
    sourceName = safeStem(file.name);
    processButton.disabled = false;
    message("Image loaded. Choose settings and deconvolve.", "success");
  } catch (error) {
    message("Cannot open image: " + error.message, "error");
  } finally {
    if (bitmap) bitmap.close();
  }
}

function parseReference(value) {
  if (!value.trim()) return null;
  const parts = value.split(",").map(x => Number(x.trim()));
  if (parts.length !== 3 || parts.some(v => !Number.isFinite(v) || v < 1 || v > 255)) {
    throw new Error("Enter a white reference as three values from 1 to 255, such as 240,240,240.");
  }
  return parts;
}

function downloadBlob(blob, filename) {
  if (!blob) {
    message("Could not create the download.", "error");
    return;
  }
  const url = URL.createObjectURL(blob);
  const anchor = document.createElement("a");
  anchor.href = url;
  anchor.download = filename;
  document.body.append(anchor);
  anchor.click();
  anchor.remove();
  setTimeout(() => URL.revokeObjectURL(url), 1000);
}

function downloadCanvas(canvas, filename) {
  canvas.toBlob(blob => downloadBlob(blob, filename), "image/png");
}

function makeResultCard(name, pixels, stats, width, height) {
  const card = document.createElement("article");
  card.className = "result-card";
  const title = document.createElement("h3");
  title.textContent = name;
  const canvas = document.createElement("canvas");
  canvas.width = width;
  canvas.height = height;
  canvas.setAttribute("aria-label", name + " stain reconstruction");
  const ctx = canvas.getContext("2d");
  if (!ctx) throw new Error("Canvas rendering is unavailable.");
  const img = ctx.createImageData(width,height);
  img.data.set(pixels);
  ctx.putImageData(img,0,0);
  const details = document.createElement("p");
  details.className = "stats";
  details.textContent = "Mean OD: " + stats.mean_od.toFixed(4) + " · Positive: " +
    stats.percent_positive_area.toFixed(2) + "% · Range: [" +
    stats.min_od.toFixed(3) + ", " + stats.max_od.toFixed(3) + "]";
  const button = document.createElement("button");
  button.type = "button";
  button.className = "secondary";
  button.textContent = "Download PNG";
  button.addEventListener("click", () => downloadCanvas(canvas, sourceName + "_" + name + ".png"));
  card.append(title,canvas,details,button);
  return card;
}

function quoteCsv(value) {
  return '"' + String(value).replace(/"/g,'""') + '"';
}

function downloadStatistics() {
  if (!lastStats) return;
  const lines = ["image,stain,mean_od,percent_positive_area,max_od,min_od"];
  for (const [name,s] of Object.entries(lastStats)) {
    lines.push([sourceName,name,s.mean_od,s.percent_positive_area,s.max_od,s.min_od].map(quoteCsv).join(","));
  }
  downloadBlob(new Blob([lines.join("\r\n")+"\r\n"],{type:"text/csv;charset=utf-8"}),sourceName+"_stain_statistics.csv");
}

input.addEventListener("change", () => void showFile(input.files?.[0]));
form.addEventListener("submit", async event => {
  event.preventDefault();
  if (processButton.disabled) return;
  processButton.disabled = true;
  clearResults();
  message("Computing optical densities and separated channels…");
  // Give the browser an opportunity to update its status before processing.
  await new Promise(resolve => requestAnimationFrame(() => requestAnimationFrame(resolve)));
  try {
    const threshold = Number($("threshold").value);
    const whiteRef = parseReference($("white").value);
    const image = original.getContext("2d", {willReadFrequently:true}).getImageData(0,0,original.width,original.height);
    const result = deconvolvePixels(image,{
      preset:$("preset").value, mode:$("mode").value, threshold, whiteRef
    });
    const frag = document.createDocumentFragment();
    result.names.forEach((name,i) =>
      frag.append(makeResultCard(name,result.channels[i],result.statistics[name],image.width,image.height))
    );
    $("channels").replaceChildren(frag);
    lastStats = result.statistics;
    $("results").hidden = false;
    message("Deconvolution complete. Export individual PNG channels or the statistics CSV.", "success");
  } catch (error) {
    message("Processing failed: " + error.message, "error");
  } finally {
    processButton.disabled = !input.files?.length || original.style.display === "none";
  }
});
$("download-csv").addEventListener("click", downloadStatistics);
form.addEventListener("reset", () => {
  sequence++;
  clearResults();
  original.width = original.height = 0;
  original.style.display = "none";
  $("placeholder").hidden = false;
  $("dimensions").textContent = "Images remain in your browser; no server connection is required.";
  processButton.disabled = true;
  sourceName = "";
  message("Select an image to begin.");
});
