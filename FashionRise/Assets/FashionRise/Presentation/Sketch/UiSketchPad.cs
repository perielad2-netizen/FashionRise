using System;
using System.Collections.Generic;
using System.IO;
using UnityEngine;
using UnityEngine.EventSystems;
using UnityEngine.UI;

namespace FashionRise.Presentation.Sketch
{
    /// <summary>
    /// Raster sketch surface for Pillar A — pointer draw, undo, PNG export. [V3_READY] layers / vectors.
    /// </summary>
    [RequireComponent(typeof(RawImage))]
    [DisallowMultipleComponent]
    public sealed class UiSketchPad : MonoBehaviour, IPointerDownHandler, IPointerUpHandler, IDragHandler
    {
        [SerializeField] int textureWidth = 768;
        [SerializeField] int textureHeight = 1024;
        [SerializeField] Color brushColor = new(0.11f, 0.09f, 0.08f, 1f);
        [SerializeField] [Range(1, 32)] int brushRadius = 4;

        const int MaxUndo = 14;

        RawImage _raw = null!;
        Texture2D _tex = null!;
        Color32[]? _referenceBase;
        readonly List<Color32[]> _undo = new();
        bool _drawing;
        Vector2 _lastPixel;

        void Awake()
        {
            _raw = GetComponent<RawImage>();
            _tex = new Texture2D(textureWidth, textureHeight, TextureFormat.RGBA32, false)
            {
                filterMode = FilterMode.Point,
                wrapMode = TextureWrapMode.Clamp
            };
            FillWhite();
            _tex.Apply();
            _raw.texture = _tex;
            _raw.uvRect = new Rect(0f, 0f, 1f, 1f);
        }

        void OnDestroy()
        {
            if (_tex != null)
                Destroy(_tex);
        }

        void FillWhite()
        {
            var w = new Color32(255, 255, 255, 255);
            var buf = new Color32[textureWidth * textureHeight];
            for (var i = 0; i < buf.Length; i++)
                buf[i] = w;
            _tex.SetPixels32(buf);
        }

        void ApplyBasePixels()
        {
            if (_referenceBase == null)
                FillWhite();
            else
            {
                var copy = new Color32[_referenceBase.Length];
                Array.Copy(_referenceBase, copy, _referenceBase.Length);
                _tex.SetPixels32(copy);
            }
        }

        public bool HasReferenceUnderlay => _referenceBase != null;

        public void ClearAll()
        {
            PushUndoSnapshot();
            ApplyBasePixels();
            _tex.Apply();
        }

        /// <summary>Load an image as a non-destructive underlay; ink draws on top. Clear resets to this image.</summary>
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
                _tex.ReadPixels(new Rect(0, 0, textureWidth, textureHeight), 0, 0);
                _tex.Apply();
                RenderTexture.active = prev;
                RenderTexture.ReleaseTemporary(rt);

                var snap = _tex.GetPixels32();
                _referenceBase = new Color32[snap.Length];
                Array.Copy(snap, _referenceBase, snap.Length);
                _undo.Clear();
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
            _tex.SetPixels32(prev);
            _tex.Apply();
            return true;
        }

        void PushUndoSnapshot()
        {
            var snap = _tex.GetPixels32();
            var copy = new Color32[snap.Length];
            System.Array.Copy(snap, copy, snap.Length);
            _undo.Add(copy);
            while (_undo.Count > MaxUndo)
                _undo.RemoveAt(0);
        }

        public void OnPointerDown(PointerEventData eventData)
        {
            _drawing = true;
            PushUndoSnapshot();
            if (TryPixel(eventData, out var p))
            {
                _lastPixel = p;
                StampBrush(p);
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

            _tex.Apply();
        }

        void StampBrush(Vector2 pixelPos)
        {
            var cx = Mathf.Clamp(Mathf.RoundToInt(pixelPos.x), 0, textureWidth - 1);
            var cy = Mathf.Clamp(Mathf.RoundToInt(pixelPos.y), 0, textureHeight - 1);
            var r = brushRadius;
            var c32 = (Color32)brushColor;
            for (var dy = -r; dy <= r; dy++)
            for (var dx = -r; dx <= r; dx++)
            {
                if (dx * dx + dy * dy > r * r)
                    continue;
                var x = cx + dx;
                var y = cy + dy;
                if (x < 0 || x >= textureWidth || y < 0 || y >= textureHeight)
                    continue;
                _tex.SetPixel(x, y, c32);
            }
        }

        /// <summary>True if the user changed pixels vs blank canvas or vs loaded reference.</summary>
        public bool HasInk(int threshold = 10)
        {
            var px = _tex.GetPixels32();
            if (_referenceBase == null)
            {
                foreach (var c in px)
                {
                    if (c.r < 255 - threshold || c.g < 255 - threshold || c.b < 255 - threshold)
                        return true;
                }

                return false;
            }

            for (var i = 0; i < px.Length; i++)
            {
                if (InkDelta(px[i], _referenceBase[i]) > threshold)
                    return true;
            }

            return false;
        }

        static int InkDelta(Color32 a, Color32 b) =>
            Mathf.Abs(a.r - b.r) + Mathf.Abs(a.g - b.g) + Mathf.Abs(a.b - b.b) + Mathf.Abs(a.a - b.a);

        /// <summary>Writes PNG under persistentDataPath/Sketches; returns full file path.</summary>
        public string SavePngToPersistentData(string fileNamePrefix = "sketch")
        {
            var dir = Path.Combine(Application.persistentDataPath, "Sketches");
            Directory.CreateDirectory(dir);
            var name = $"{fileNamePrefix}_{System.DateTime.UtcNow:yyyyMMdd_HHmmssfff}.png";
            var path = Path.Combine(dir, name);
            File.WriteAllBytes(path, _tex.EncodeToPNG());
            return path;
        }
    }
}
