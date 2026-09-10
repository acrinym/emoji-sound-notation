"use strict";

(function (root, factory) {
  const api = factory();
  if (typeof module !== "undefined" && module.exports) module.exports = api;
  else root.EsnSoundPackDomain = api;
})(typeof globalThis !== "undefined" ? globalThis : this, function () {
  const PACK_KEYS = new Set(["format","id","name","version","license","provenance","fallback","bindings"]);
  const LICENSE_KEYS = new Set(["name","spdx","url"]);
  const PROVENANCE_KEYS = new Set(["creator","source","notes"]);
  const BINDING_KEYS = new Set(["source","gesture","asset","gain","loop","root_note","credit"]);

  function object(value, label, allowed, required) {
    if (!value || typeof value !== "object" || Array.isArray(value)) throw new Error(`${label} must be an object.`);
    const extras = Object.keys(value).filter(key => !allowed.has(key));
    if (extras.length) throw new Error(`${label} contains unknown fields: ${extras.join(", ")}.`);
    const missing = [...required].filter(key => !(key in value));
    if (missing.length) throw new Error(`${label} is missing required fields: ${missing.join(", ")}.`);
    return value;
  }

  function nonempty(value, label) {
    if (typeof value !== "string" || !value.trim()) throw new Error(`${label} must be a non-empty string.`);
    return value;
  }

  function normalizeAsset(value, label) {
    const asset = nonempty(value, label).replaceAll("\\", "/");
    const parts = asset.split("/");
    if (asset.startsWith("/") || /^[A-Za-z]:/.test(asset) || parts.includes("..") || !asset.toLowerCase().endsWith(".wav")) {
      throw new Error(`${label} must be a relative .wav path without traversal.`);
    }
    return parts.filter(part => part && part !== ".").join("/");
  }

  function validatePack(doc, registryDoc, noteToMidi = null) {
    object(doc, "Sound pack", PACK_KEYS, PACK_KEYS);
    if (doc.format !== "esn-sound-pack/1") throw new Error("Sound pack format must be esn-sound-pack/1.");
    for (const key of ["id","name","version"]) nonempty(doc[key], `Sound pack ${key}`);
    if (doc.fallback !== "reference_synth") throw new Error("Sound pack fallback must be reference_synth.");

    const license = object(doc.license, "Sound pack license", LICENSE_KEYS, new Set(["name"]));
    nonempty(license.name, "Sound pack license name");
    for (const key of Object.keys(license).filter(key => key !== "name")) nonempty(license[key], `Sound pack license ${key}`);
    const provenance = object(doc.provenance, "Sound pack provenance", PROVENANCE_KEYS, new Set(["creator"]));
    nonempty(provenance.creator, "Sound pack provenance creator");
    if ("source" in provenance) nonempty(provenance.source, "Sound pack provenance source");
    if ("notes" in provenance && typeof provenance.notes !== "string") throw new Error("Sound pack provenance notes must be text.");
    if (!Array.isArray(doc.bindings)) throw new Error("Sound pack bindings must be an array.");

    const sources = new Map(registryDoc.sources.map(source => [source.id, source]));
    const seen = new Set();
    doc.bindings.forEach((binding, index) => {
      const where = `Sound pack binding ${index + 1}`;
      object(binding, where, BINDING_KEYS, new Set(["source","gesture","asset"]));
      const source = sources.get(binding.source);
      if (!source) throw new Error(`${where} uses an unknown source: ${binding.source}.`);
      if (binding.gesture !== "*" && !source.gestures.includes(binding.gesture)) throw new Error(`${where} has an invalid action for ${binding.source}.`);
      binding.asset = normalizeAsset(binding.asset, `${where} asset`);
      if ("gain" in binding && (typeof binding.gain !== "number" || !Number.isFinite(binding.gain) || binding.gain < 0 || binding.gain > 4)) throw new Error(`${where} gain must be between 0 and 4.`);
      if ("loop" in binding && typeof binding.loop !== "boolean") throw new Error(`${where} loop must be true or false.`);
      if ("root_note" in binding && (!noteToMidi || noteToMidi(binding.root_note) === null)) throw new Error(`${where} root note is invalid.`);
      if ("credit" in binding && typeof binding.credit !== "string") throw new Error(`${where} credit must be text.`);
      const key = `${binding.source}/${binding.gesture}`;
      if (seen.has(key)) throw new Error(`Duplicate sound-pack binding for ${key}.`);
      seen.add(key);
    });
    return doc;
  }

  function resolveBinding(doc, event) {
    return doc.bindings.find(binding => binding.source === event.source && binding.gesture === event.gesture)
      || doc.bindings.find(binding => binding.source === event.source && binding.gesture === "*")
      || null;
  }

  function fileKeyFor(manifestRelativePath, asset) {
    const normalizedManifest = String(manifestRelativePath || "pack.json").replaceAll("\\", "/");
    const slash = normalizedManifest.lastIndexOf("/");
    const prefix = slash < 0 ? "" : normalizedManifest.slice(0, slash + 1);
    return `${prefix}${normalizeAsset(asset, "Sound pack asset")}`;
  }

  function describePack(doc) {
    const spdx = doc.license.spdx && doc.license.spdx !== doc.license.name ? ` · ${doc.license.spdx}` : "";
    return `${doc.name} ${doc.version} · ${doc.provenance.creator} · ${doc.license.name}${spdx}`;
  }

  return {validatePack, resolveBinding, fileKeyFor, describePack};
});
