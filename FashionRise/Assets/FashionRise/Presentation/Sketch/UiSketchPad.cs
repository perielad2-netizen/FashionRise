using System;
using System.Collections.Generic;
using System.IO;
using FashionRise.Application;
using FashionRise.Domain;
using UnityEngine;
using UnityEngine.EventSystems;
using UnityEngine.UI;

namespace FashionRise.Presentation.Sketch
{
    /// <summary>
    /// Dual-layer raster pad: reference (croquis / photo) underneath, ink on top. Default figures load from
    /// <c>Resources/SketchReference/</c> when present, else procedural fallback.
    /// </summary>
    [RequireComponent(typeof(RawImage))]
    [DisallowMultipleComponent]
    public sealed class UiSketchPad : MonoBehaviour, IPointerDownHandler, IPointerUpHandler, IDragHandler
    {
        [SerializeField] int textureWidth = 768;
        [SerializeField] int textureHeight = 1024;
        [SerializeField] Color brushColor = new(0.11f, 0.09f, 0.08f, 1f);
        [SerializeField] [Range(1, 50)] int brushRadius = 4;
        [SerializeField] [Range(0f, 1f)] float brushSoftness = 0f;
        [SerializeField] [Range(0.15f, 1f)] float brushOpacity = 1f;

        const int MaxUndo = 14;
        static readonly Color32 InkClear = new(0, 0, 0, 0);
        static readonly Color32 White = new(255, 255, 255, 255);

        RawImage _raw = null!;
        Texture2D _tex = null!;
        Color32[] _referencePixels = null!;
        Color32[] _inkPixels = null!;
        readonly List<Color32[]> _undo = new();
        bool _drawing;
        Vector2 _lastPixel;
        bool _eraser;
        bool _fillBucket;
        [SerializeField] [Range(0.25f, 1f)] float referenceStrength = 1f;
        Color32[] _scratchComposite = null!;

        void Awake()
        {
            _raw = GetComponent<RawImage>();
            var n = textureWidth * textureHeight;
            _referencePixels = new Color32[n];
            _inkPixels = new Color32[n];
            for (var i = 0; i < n; i++)
            {
                _referencePixels[i] = White;
                _inkPixels[i] = InkClear;
            }

            _tex = new Texture2D(textureWidth, textureHeight, TextureFormat.RGBA32, false)
            {
                filterMode = FilterMode.Point,
                wrapMode = TextureWrapMode.Clamp
            };
            _scratchComposite = new Color32[n];
            CompositeToTexture();
            _tex.Apply();
            _raw.texture = _tex;
            _raw.uvRect = new Rect(0f, 0f, 1f, 1f);
        }

        void OnDestroy()
        {
            if (_tex != null)
                Destroy(_tex);
        }

        public bool EraserActive
        {
            get => _eraser;
            set
            {
                _eraser = value;
                if (value)
                    _fillBucket = false;
            }
        }

        public bool FillBucketActive
        {
            get => _fillBucket;
            set
            {
                _fillBucket = value;
                if (value)
                    _eraser = false;
            }
        }

        /// <summary>How strongly the reference shows through (1 = full, lower = fainter for tracing).</summary>
        public float ReferenceStrength
        {
            get => referenceStrength;
            set => referenceStrength = Mathf.Clamp(value, 0.25f, 1f);
        }

        public void SetBrushRadius(int radius) =>
            brushRadius = Mathf.Clamp(radius, 1, 50);

        public int BrushRadius => brushRadius;

        /// <summary>0 = hard marker/brush, 1 = soft graphite pencil falloff.</summary>
        public void SetBrushSoftness(float softness) =>
            brushSoftness = Mathf.Clamp01(softness);

        public float BrushSoftness => brushSoftness;

        /// <summary>Per-stamp opacity for pencil layering / shading.</summary>
        public void SetBrushOpacity(float opacity) =>
            brushOpacity = Mathf.Clamp(opacity, 0.15f, 1f);

        public float BrushOpacity => brushOpacity;

        public void SetBrushColor(Color c) => brushColor = c;

        public Color BrushColor => brushColor;

        public int TextureWidth => textureWidth;

        public int TextureHeight => textureHeight;

        public float TextureAspect => textureHeight > 0 ? textureWidth / (float)textureHeight : 0.75f;

        public bool HasReferenceUnderlay => _hasFigureOrPhoto;

        bool _hasFigureOrPhoto;

        /// <summary>Apply default female/male underlay from <c>Resources/SketchReference</c> when available; else procedural croquis.</summary>
        public void ApplyDefaultFigure(SketchFigureTemplate template, int? poseIndex = null)
        {
            var pose = poseIndex ?? SketchFigurePreferences.DefaultPoseIndex;
            if (!SketchDefaultFigureGenerator.TryFillReferenceFromBundledImage(_referencePixels, textureWidth,
                    textureHeight, template, pose))
                SketchDefaultFigureGenerator.FillReference(_referencePixels, textureWidth, textureHeight, template);
            ClearInkOnly();
            _hasFigureOrPhoto = true;
            CompositeToTexture();
            _tex.Apply();
            _undo.Clear();
        }

        /// <summary>White reference, no underlay.</summary>
        public void ClearReferenceToBlank()
        {
            for (var i = 0; i < _referencePixels.Length; i++)
                _referencePixels[i] = White;
            ClearInkOnly();
            _hasFigureOrPhoto = false;
            CompositeToTexture();
            _tex.Apply();
            _undo.Clear();
        }

        void ClearInkOnly()
        {
            for (var i = 0; i < _inkPixels.Length; i++)
                _inkPixels[i] = InkClear;
        }

        public void ClearAll()
        {
            PushUndoSnapshot();
            ClearInkOnly();
            CompositeToTexture();
            _tex.Apply();
        }

        /// <summary>Load an image as the reference layer only; ink is cleared.</summary>
        public bool TryLoadUnderlayFromFile(string absolutePath, out string? errorMessage)
        {
            errorMessage = null;
            var path = (absolutePath ?? "").Trim();
            if (path.StartsWith("file:", StringComparison.OrdinalIgnoreCase))
                path = path["file:".Length..].TrimStart('/');

            if (string.IsNullOrEmpty(path) || !File.Exists(path))
            {
                errorMessage = "File not found.";
                return false;
            }

            try
            {
                var bytes = File.ReadAllBytes(path);
                var src = new Texture2D(2, 2, TextureFormat.RGBA32, false);
                if (!src.LoadImage(bytes))
                {
                    Destroy(src);
                    errorMessage = "Could not read image (PNG or JPEG).";
                    return false;
                }

                SketchDefaultFigureGenerator.BlitAspectFit(src, _referencePixels, textureWidth, textureHeight, White);
                Destroy(src);
                ClearInkOnly();
                _hasFigureOrPhoto = true;
                _undo.Clear();
                CompositeToTexture();
                _tex.Apply();
                return true;
            }
            catch (Exception ex)
            {
                errorMessage = ex.Message;
                return false;
            }
        }

        public bool UndoStroke()
        {
            if (_undo.Count == 0)
                return false;
            var prev = _undo[^1];
            _undo.RemoveAt(_undo.Count - 1);
            Array.Copy(prev, _inkPixels, _inkPixels.Length);
            CompositeToTexture();
            _tex.Apply();
            return true;
        }

        void PushUndoSnapshot()
        {
            var snap = new Color32[_inkPixels.Length];
            Array.Copy(_inkPixels, snap, _inkPixels.Length);
            _undo.Add(snap);
            while (_undo.Count > MaxUndo)
                _undo.RemoveAt(0);
        }

        void CompositeToTexture()
        {
            var n = textureWidth * textureHeight;
            for (var i = 0; i < n; i++)
            {
                var r = _referencePixels[i];
                var dimR = (byte)(White.r + (r.r - White.r) * referenceStrength);
                var dimG = (byte)(White.g + (r.g - White.g) * referenceStrength);
                var dimB = (byte)(White.b + (r.b - White.b) * referenceStrength);
                var dimA = (byte)(White.a + (r.a - White.a) * referenceStrength);
                var rd = new Color32(dimR, dimG, dimB, dimA);
                var ink = _inkPixels[i];
                if (ink.a < 8)
                {
                    _scratchComposite[i] = rd;
                    continue;
                }

                var a = ink.a / 255f;
                _scratchComposite[i] = new Color32(
                    (byte)Mathf.Clamp(Mathf.RoundToInt(ink.r * a + rd.r * (1f - a)), 0, 255),
                    (byte)Mathf.Clamp(Mathf.RoundToInt(ink.g * a + rd.g * (1f - a)), 0, 255),
                    (byte)Mathf.Clamp(Mathf.RoundToInt(ink.b * a + rd.b * (1f - a)), 0, 255),
                    255);
            }

            _tex.SetPixels32(_scratchComposite);
        }

        /// <summary>Re-run reference × ink composite (e.g. after changing reference dim).</summary>
        public void RefreshComposite()
        {
            CompositeToTexture();
            _tex.Apply();
        }

        public void OnPointerDown(PointerEventData eventData)
        {
            if (!TryPixel(eventData, out var p))
                return;

            if (_fillBucket)
            {
                PushUndoSnapshot();
                FloodFill(Mathf.RoundToInt(p.x), Mathf.RoundToInt(p.y));
                CompositeToTexture();
                _tex.Apply();
                _drawing = false;
                return;
            }

            _drawing = true;
            PushUndoSnapshot();
            _lastPixel = p;
            StampBrush(p);
            CompositeToTexture();
            _tex.Apply();
        }

        public void OnPointerUp(PointerEventData eventData) => _drawing = false;

        public void OnDrag(PointerEventData eventData)
        {
            if (_fillBucket || !_drawing || !TryPixel(eventData, out var p))
                return;
            LinePixels(_lastPixel, p);
            _lastPixel = p;
        }

        bool TryPixel(PointerEventData e, out Vector2 pixel)
        {
            pixel = default;
            if (!RectTransformUtility.ScreenPointToLocalPointInRectangle(
                    _raw.rectTransform, e.position, e.pressEventCamera, out var local))
                return false;

            var r = _raw.rectTransform.rect;
            if (r.width <= 1f || r.height <= 1f)
                return false;

            var nx = (local.x - r.xMin) / r.width;
            var ny = (local.y - r.yMin) / r.height;
            if (nx < 0f || nx > 1f || ny < 0f || ny > 1f)
                return false;

            pixel = new Vector2(nx * (textureWidth - 1), ny * (textureHeight - 1));
            return true;
        }

        void LinePixels(Vector2 a, Vector2 b)
        {
            var dist = Vector2.Distance(a, b);
            var step = Mathf.Max(0.35f, brushRadius * (brushSoftness > 0.35f ? 0.22f : 0.35f));
            var steps = Mathf.Max(1, Mathf.CeilToInt(dist / step));
            for (var i = 0; i <= steps; i++)
            {
                var p = Vector2.Lerp(a, b, i / (float)steps);
                StampBrush(p);
            }

            CompositeToTexture();
            _tex.Apply();
        }

        void StampBrush(Vector2 pixelPos)
        {
            var cx = Mathf.Clamp(Mathf.RoundToInt(pixelPos.x), 0, textureWidth - 1);
            var cy = Mathf.Clamp(Mathf.RoundToInt(pixelPos.y), 0, textureHeight - 1);
            var r = brushRadius;
            var soft = brushSoftness;
            var opacity = brushOpacity;

            if (_eraser)
            {
                for (var dy = -r; dy <= r; dy++)
                for (var dx = -r; dx <= r; dx++)
                {
                    var distSq = dx * dx + dy * dy;
                    if (distSq > r * r)
                        continue;
                    var x = cx + dx;
                    var y = cy + dy;
                    if (x < 0 || x >= textureWidth || y < 0 || y >= textureHeight)
                        continue;
                    var idx = x + y * textureWidth;
                    if (soft <= 0.01f)
                    {
                        _inkPixels[idx] = InkClear;
                        continue;
                    }

                    var dist = Mathf.Sqrt(distSq);
                    var edge = Mathf.Lerp(r * 0.35f, r, soft);
                    var fall = 1f - Mathf.SmoothStep(edge * (1f - soft), r + 0.01f, dist);
                    if (fall <= 0.02f)
                        continue;
                    var cur = _inkPixels[idx];
                    var na = (byte)Mathf.Clamp(Mathf.RoundToInt(cur.a * (1f - fall * opacity)), 0, 255);
                    if (na < 8)
                        _inkPixels[idx] = InkClear;
                    else
                        _inkPixels[idx] = new Color32(cur.r, cur.g, cur.b, na);
                }
            }
            else
            {
                var baseC = brushColor;
                for (var dy = -r; dy <= r; dy++)
                for (var dx = -r; dx <= r; dx++)
                {
                    var distSq = dx * dx + dy * dy;
                    if (distSq > r * r)
                        continue;
                    var x = cx + dx;
                    var y = cy + dy;
                    if (x < 0 || x >= textureWidth || y < 0 || y >= textureHeight)
                        continue;
                    var idx = x + y * textureWidth;

                    float cover;
                    if (soft <= 0.01f)
                        cover = 1f;
                    else
                    {
                        var dist = Mathf.Sqrt(distSq);
                        var inner = r * (1f - soft * 0.85f);
                        cover = 1f - Mathf.SmoothStep(inner, r + 0.01f, dist);
                    }

                    cover *= opacity;
                    if (cover <= 0.02f)
                        continue;

                    var dst = _inkPixels[idx];
                    if (dst.a < 8)
                    {
                        _inkPixels[idx] = new Color32(
                            (byte)Mathf.Clamp(Mathf.RoundToInt(baseC.r * 255f), 0, 255),
                            (byte)Mathf.Clamp(Mathf.RoundToInt(baseC.g * 255f), 0, 255),
                            (byte)Mathf.Clamp(Mathf.RoundToInt(baseC.b * 255f), 0, 255),
                            (byte)Mathf.Clamp(Mathf.RoundToInt(cover * 255f), 0, 255));
                        continue;
                    }

                    // Alpha-over blend so pencil strokes layer like graphite
                    var srcA = cover;
                    var dstA = dst.a / 255f;
                    var outA = srcA + dstA * (1f - srcA);
                    if (outA < 0.01f)
                    {
                        _inkPixels[idx] = InkClear;
                        continue;
                    }

                    var sr = baseC.r;
                    var sg = baseC.g;
                    var sb = baseC.b;
                    var dr = dst.r / 255f;
                    var dg = dst.g / 255f;
                    var db = dst.b / 255f;
                    _inkPixels[idx] = new Color32(
                        (byte)Mathf.Clamp(Mathf.RoundToInt((sr * srcA + dr * dstA * (1f - srcA)) / outA * 255f), 0, 255),
                        (byte)Mathf.Clamp(Mathf.RoundToInt((sg * srcA + dg * dstA * (1f - srcA)) / outA * 255f), 0, 255),
                        (byte)Mathf.Clamp(Mathf.RoundToInt((sb * srcA + db * dstA * (1f - srcA)) / outA * 255f), 0, 255),
                        (byte)Mathf.Clamp(Mathf.RoundToInt(outA * 255f), 0, 255));
                }
            }
        }

        /// <summary>
        /// Paint-bucket fill: flood connected pixels similar to the tap (empty pockets or same color).
        /// Stops at different ink / outlines so closed garment areas fill cleanly.
        /// </summary>
        void FloodFill(int startX, int startY)
        {
            startX = Mathf.Clamp(startX, 0, textureWidth - 1);
            startY = Mathf.Clamp(startY, 0, textureHeight - 1);
            var target = _inkPixels[startX + startY * textureWidth];
            var fill = (Color32)brushColor;
            fill.a = 255;
            if (ColorsMatch(target, fill, 8))
                return;

            // Cap work so a tap on open background can't freeze the device.
            var maxPixels = textureWidth * textureHeight;
            var visited = new bool[maxPixels];
            var queue = new Queue<int>(4096);
            var start = startX + startY * textureWidth;
            queue.Enqueue(start);
            visited[start] = true;
            var painted = 0;

            while (queue.Count > 0 && painted < maxPixels)
            {
                var i = queue.Dequeue();
                if (!ColorsMatch(_inkPixels[i], target, 28))
                    continue;

                _inkPixels[i] = fill;
                painted++;

                var x = i % textureWidth;
                var y = i / textureWidth;
                TryEnqueue(x + 1, y);
                TryEnqueue(x - 1, y);
                TryEnqueue(x, y + 1);
                TryEnqueue(x, y - 1);
            }

            void TryEnqueue(int x, int y)
            {
                if (x < 0 || y < 0 || x >= textureWidth || y >= textureHeight)
                    return;
                var idx = x + y * textureWidth;
                if (visited[idx])
                    return;
                visited[idx] = true;
                queue.Enqueue(idx);
            }
        }

        static bool ColorsMatch(Color32 a, Color32 b, int tol)
        {
            // Treat nearly-empty ink as the same "empty" region for filling closed shapes.
            if (a.a < 12 && b.a < 12)
                return true;
            if (a.a < 12 || b.a < 12)
                return false;
            return Mathf.Abs(a.r - b.r) <= tol &&
                   Mathf.Abs(a.g - b.g) <= tol &&
                   Mathf.Abs(a.b - b.b) <= tol;
        }

        /// <summary>True if ink differs from empty (alpha).</summary>
        public bool HasInk(int alphaThreshold = 12)
        {
            foreach (var c in _inkPixels)
            {
                if (c.a > alphaThreshold)
                    return true;
            }

            return false;
        }

        /// <summary>Writes flattened PNG (reference + ink) under persistentDataPath/Sketches.</summary>
        public string SavePngToPersistentData(string fileNamePrefix = "sketch")
        {
            var dir = Path.Combine(UnityEngine.Application.persistentDataPath, "Sketches");
            Directory.CreateDirectory(dir);
            var name = $"{fileNamePrefix}_{System.DateTime.UtcNow:yyyyMMdd_HHmmssfff}.png";
            var path = Path.Combine(dir, name);
            CompositeToTexture();
            _tex.Apply();
            File.WriteAllBytes(path, _tex.EncodeToPNG());
            return path;
        }

        /// <summary>Saves ink layer only (transparent PNG) so Edit sketch can restore strokes.</summary>
        public string SaveInkPngToPersistentData(string fileNamePrefix = "ink")
        {
            var dir = Path.Combine(UnityEngine.Application.persistentDataPath, "Sketches");
            Directory.CreateDirectory(dir);
            var name = $"{fileNamePrefix}_{System.DateTime.UtcNow:yyyyMMdd_HHmmssfff}.png";
            var path = Path.Combine(dir, name);
            var inkTex = new Texture2D(textureWidth, textureHeight, TextureFormat.RGBA32, false)
            {
                filterMode = FilterMode.Point,
                wrapMode = TextureWrapMode.Clamp
            };
            inkTex.SetPixels32(_inkPixels);
            inkTex.Apply();
            File.WriteAllBytes(path, inkTex.EncodeToPNG());
            Destroy(inkTex);
            return path;
        }

        /// <summary>Restores ink from a previously saved ink PNG (keeps current reference/mannequin).</summary>
        public bool TryLoadInkFromFile(string absolutePath, out string? errorMessage)
        {
            errorMessage = null;
            var path = (absolutePath ?? "").Trim();
            if (path.StartsWith("file:", StringComparison.OrdinalIgnoreCase))
                path = path["file:".Length..].TrimStart('/');

            if (string.IsNullOrEmpty(path) || !File.Exists(path))
            {
                errorMessage = "Ink file not found.";
                return false;
            }

            try
            {
                var bytes = File.ReadAllBytes(path);
                var src = new Texture2D(2, 2, TextureFormat.RGBA32, false);
                if (!src.LoadImage(bytes))
                {
                    Destroy(src);
                    errorMessage = "Could not read ink PNG.";
                    return false;
                }

                ClearInkOnly();
                // Nearest-neighbor blit into ink buffer
                for (var y = 0; y < textureHeight; y++)
                for (var x = 0; x < textureWidth; x++)
                {
                    var u = (x + 0.5f) / textureWidth;
                    var v = (y + 0.5f) / textureHeight;
                    var c = (Color32)src.GetPixelBilinear(u, v);
                    if (c.a < 8)
                        continue;
                    c.a = 255;
                    _inkPixels[x + y * textureWidth] = c;
                }

                Destroy(src);
                _undo.Clear();
                CompositeToTexture();
                _tex.Apply();
                return true;
            }
            catch (Exception ex)
            {
                errorMessage = ex.Message;
                return false;
            }
        }
    }
}
