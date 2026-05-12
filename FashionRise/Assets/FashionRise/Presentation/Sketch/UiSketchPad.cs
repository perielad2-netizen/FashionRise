using System;
using System.Collections.Generic;
using System.IO;
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
        [SerializeField] [Range(1, 48)] int brushRadius = 4;

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
            set => _eraser = value;
        }

        /// <summary>How strongly the reference shows through (1 = full, lower = fainter for tracing).</summary>
        public float ReferenceStrength
        {
            get => referenceStrength;
            set => referenceStrength = Mathf.Clamp(value, 0.25f, 1f);
        }

        public void SetBrushRadius(int radius) =>
            brushRadius = Mathf.Clamp(radius, 1, 48);

        public int BrushRadius => brushRadius;

        public void SetBrushColor(Color c) => brushColor = c;

        public Color BrushColor => brushColor;

        public bool HasReferenceUnderlay => _hasFigureOrPhoto;

        bool _hasFigureOrPhoto;

        /// <summary>Apply default female/male underlay from <c>Resources/SketchReference</c> when available; else procedural croquis.</summary>
        public void ApplyDefaultFigure(SketchFigureTemplate template)
        {
            if (!SketchDefaultFigureGenerator.TryFillReferenceFromBundledImage(_referencePixels, textureWidth,
                    textureHeight, template))
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

                var rt = RenderTexture.GetTemporary(textureWidth, textureHeight, 0, RenderTextureFormat.ARGB32,
                    RenderTextureReadWrite.Linear);
                Graphics.Blit(src, rt);
                Destroy(src);

                var prev = RenderTexture.active;
                RenderTexture.active = rt;
                var temp = new Texture2D(textureWidth, textureHeight, TextureFormat.RGBA32, false);
                temp.ReadPixels(new Rect(0, 0, textureWidth, textureHeight), 0, 0);
                temp.Apply();
                RenderTexture.active = prev;
                RenderTexture.ReleaseTemporary(rt);

                var snap = temp.GetPixels32();
                Destroy(temp);
                Array.Copy(snap, _referencePixels, Mathf.Min(snap.Length, _referencePixels.Length));
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
            _drawing = true;
            PushUndoSnapshot();
            if (TryPixel(eventData, out var p))
            {
                _lastPixel = p;
                StampBrush(p);
                CompositeToTexture();
                _tex.Apply();
            }
        }

        public void OnPointerUp(PointerEventData eventData) => _drawing = false;

        public void OnDrag(PointerEventData eventData)
        {
            if (!_drawing || !TryPixel(eventData, out var p))
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
            var steps = Mathf.Max(1, Mathf.CeilToInt(dist / Mathf.Max(0.5f, brushRadius * 0.35f)));
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
            if (_eraser)
            {
                for (var dy = -r; dy <= r; dy++)
                for (var dx = -r; dx <= r; dx++)
                {
                    if (dx * dx + dy * dy > r * r)
                        continue;
                    var x = cx + dx;
                    var y = cy + dy;
                    if (x < 0 || x >= textureWidth || y < 0 || y >= textureHeight)
                        continue;
                    _inkPixels[x + y * textureWidth] = InkClear;
                }
            }
            else
            {
                var c32 = (Color32)brushColor;
                c32.a = 255;
                for (var dy = -r; dy <= r; dy++)
                for (var dx = -r; dx <= r; dx++)
                {
                    if (dx * dx + dy * dy > r * r)
                        continue;
                    var x = cx + dx;
                    var y = cy + dy;
                    if (x < 0 || x >= textureWidth || y < 0 || y >= textureHeight)
                        continue;
                    _inkPixels[x + y * textureWidth] = c32;
                }
            }
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
    }
}
