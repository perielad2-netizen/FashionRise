using System.Collections.Generic;
using UnityEngine;

namespace FashionRise.UI.Studio
{
    public enum FrStudioIconKind
    {
        Draw,
        Erase,
        Undo,
        Clear,
        Back,
        Import,
        Profile,
        Dim,
        Magic
    }

    /// <summary>Deliberate programmatic sprites — no emoji, no downloaded icon packs.</summary>
    public static class FrStudioSprites
    {
        static readonly Dictionary<string, Sprite> Cache = new();

        public static Sprite Rounded(int size, int radius, Color color)
        {
            var key = $"r:{size}:{radius}:{ColorUtility.ToHtmlStringRGBA(color)}";
            if (Cache.TryGetValue(key, out var hit) && hit != null)
                return hit;

            var tex = new Texture2D(size, size, TextureFormat.RGBA32, false)
            {
                filterMode = FilterMode.Bilinear,
                wrapMode = TextureWrapMode.Clamp,
                hideFlags = HideFlags.HideAndDontSave
            };
            var px = new Color32[size * size];
            var fill = (Color32)color;
            var clear = new Color32(0, 0, 0, 0);
            var r = Mathf.Clamp(radius, 1, size / 2);
            for (var y = 0; y < size; y++)
            for (var x = 0; x < size; x++)
            {
                px[x + y * size] = InsideRound(x, y, size, r) ? fill : clear;
            }

            tex.SetPixels32(px);
            tex.Apply(false, false);
            var sprite = Sprite.Create(tex, new Rect(0, 0, size, size), new Vector2(0.5f, 0.5f), 100f, 0,
                SpriteMeshType.FullRect, new Vector4(r, r, r, r));
            sprite.hideFlags = HideFlags.HideAndDontSave;
            Cache[key] = sprite;
            return sprite;
        }

        public static Sprite Circle(int size, Color color)
        {
            var key = $"c:{size}:{ColorUtility.ToHtmlStringRGBA(color)}";
            if (Cache.TryGetValue(key, out var hit) && hit != null)
                return hit;

            var tex = new Texture2D(size, size, TextureFormat.RGBA32, false)
            {
                filterMode = FilterMode.Bilinear,
                wrapMode = TextureWrapMode.Clamp,
                hideFlags = HideFlags.HideAndDontSave
            };
            var px = new Color32[size * size];
            var fill = (Color32)color;
            var clear = new Color32(0, 0, 0, 0);
            var cx = (size - 1) * 0.5f;
            var r2 = (size * 0.5f - 0.6f) * (size * 0.5f - 0.6f);
            for (var y = 0; y < size; y++)
            for (var x = 0; x < size; x++)
            {
                var dx = x - cx;
                var dy = y - cx;
                px[x + y * size] = dx * dx + dy * dy <= r2 ? fill : clear;
            }

            tex.SetPixels32(px);
            tex.Apply(false, false);
            var sprite = Sprite.Create(tex, new Rect(0, 0, size, size), new Vector2(0.5f, 0.5f), 100f);
            sprite.hideFlags = HideFlags.HideAndDontSave;
            Cache[key] = sprite;
            return sprite;
        }

        public static Sprite Icon(FrStudioIconKind kind, Color color)
        {
            var key = $"i:{(int)kind}:{ColorUtility.ToHtmlStringRGBA(color)}";
            if (Cache.TryGetValue(key, out var hit) && hit != null)
                return hit;

            const int size = 36;
            var tex = new Texture2D(size, size, TextureFormat.RGBA32, false)
            {
                filterMode = FilterMode.Bilinear,
                wrapMode = TextureWrapMode.Clamp,
                hideFlags = HideFlags.HideAndDontSave
            };
            var px = new Color32[size * size];
            var ink = (Color32)color;
            switch (kind)
            {
                case FrStudioIconKind.Draw:
                    StrokeLine(px, size, 9, 8, 26, 27, 2, ink);
                    FillRect(px, size, 24, 6, 28, 11, ink);
                    break;
                case FrStudioIconKind.Erase:
                    FillRound(px, size, 8, 12, 28, 26, 3, ink);
                    FillRect(px, size, 10, 14, 26, 16, new Color32(0, 0, 0, 0));
                    break;
                case FrStudioIconKind.Undo:
                    StrokeArc(px, size, 18, 18, 10, 40, 300, 2, ink);
                    FillTriangle(px, size, 8, 14, 16, 10, 16, 20, ink);
                    break;
                case FrStudioIconKind.Clear:
                    StrokeLine(px, size, 11, 11, 25, 25, 2, ink);
                    StrokeLine(px, size, 25, 11, 11, 25, 2, ink);
                    break;
                case FrStudioIconKind.Back:
                    StrokeLine(px, size, 20, 8, 10, 18, 2, ink);
                    StrokeLine(px, size, 10, 18, 20, 28, 2, ink);
                    break;
                case FrStudioIconKind.Import:
                    StrokeLine(px, size, 18, 8, 18, 22, 2, ink);
                    StrokeLine(px, size, 12, 16, 18, 22, 2, ink);
                    StrokeLine(px, size, 24, 16, 18, 22, 2, ink);
                    StrokeLine(px, size, 8, 26, 28, 26, 2, ink);
                    break;
                case FrStudioIconKind.Profile:
                    FillCircle(px, size, 18, 13, 5, ink);
                    FillRound(px, size, 8, 21, 28, 30, 6, ink);
                    break;
                case FrStudioIconKind.Dim:
                    FillCircle(px, size, 18, 18, 7, ink);
                    break;
                case FrStudioIconKind.Magic:
                    StrokeLine(px, size, 18, 6, 18, 30, 2, ink);
                    StrokeLine(px, size, 8, 14, 28, 22, 2, ink);
                    StrokeLine(px, size, 28, 14, 8, 22, 2, ink);
                    break;
            }

            tex.SetPixels32(px);
            tex.Apply(false, false);
            var sprite = Sprite.Create(tex, new Rect(0, 0, size, size), new Vector2(0.5f, 0.5f), 100f);
            sprite.hideFlags = HideFlags.HideAndDontSave;
            Cache[key] = sprite;
            return sprite;
        }

        static bool InsideRound(int x, int y, int size, int r)
        {
            if (x >= r && x < size - r && y >= r && y < size - r)
                return true;
            if (x >= r && x < size - r)
                return true;
            if (y >= r && y < size - r)
                return true;
            var cx = x < r ? r : size - 1 - r;
            var cy = y < r ? r : size - 1 - r;
            if (x >= r && x < size - r)
                cx = x;
            if (y >= r && y < size - r)
                cy = y;
            var dx = x - cx;
            var dy = y - cy;
            return dx * dx + dy * dy <= r * r;
        }

        static void FillRect(Color32[] px, int size, int x0, int y0, int x1, int y1, Color32 c)
        {
            for (var y = y0; y <= y1; y++)
            for (var x = x0; x <= x1; x++)
                Plot(px, size, x, y, c);
        }

        static void FillRound(Color32[] px, int size, int x0, int y0, int x1, int y1, int r, Color32 c)
        {
            for (var y = y0; y <= y1; y++)
            for (var x = x0; x <= x1; x++)
            {
                var lx = x - x0;
                var ly = y - y0;
                var w = x1 - x0 + 1;
                var h = y1 - y0 + 1;
                if (InsideRound(lx, ly, Mathf.Max(w, h), r) ||
                    (x >= x0 + r && x <= x1 - r) ||
                    (y >= y0 + r && y <= y1 - r))
                    Plot(px, size, x, y, c);
            }
        }

        static void FillCircle(Color32[] px, int size, int cx, int cy, int r, Color32 c)
        {
            var r2 = r * r;
            for (var y = cy - r; y <= cy + r; y++)
            for (var x = cx - r; x <= cx + r; x++)
            {
                var dx = x - cx;
                var dy = y - cy;
                if (dx * dx + dy * dy <= r2)
                    Plot(px, size, x, y, c);
            }
        }

        static void StrokeLine(Color32[] px, int size, int x0, int y0, int x1, int y1, int thickness, Color32 c)
        {
            var steps = Mathf.Max(1, Mathf.CeilToInt(Vector2.Distance(new Vector2(x0, y0), new Vector2(x1, y1))));
            for (var i = 0; i <= steps; i++)
            {
                var t = i / (float)steps;
                var x = Mathf.RoundToInt(Mathf.Lerp(x0, x1, t));
                var y = Mathf.RoundToInt(Mathf.Lerp(y0, y1, t));
                for (var dy = -thickness; dy <= thickness; dy++)
                for (var dx = -thickness; dx <= thickness; dx++)
                {
                    if (dx * dx + dy * dy <= thickness * thickness)
                        Plot(px, size, x + dx, y + dy, c);
                }
            }
        }

        static void StrokeArc(Color32[] px, int size, int cx, int cy, int r, float fromDeg, float toDeg, int thickness,
            Color32 c)
        {
            for (var a = fromDeg; a <= toDeg; a += 3f)
            {
                var rad = a * Mathf.Deg2Rad;
                var x = cx + Mathf.RoundToInt(Mathf.Cos(rad) * r);
                var y = cy + Mathf.RoundToInt(Mathf.Sin(rad) * r);
                for (var dy = -thickness; dy <= thickness; dy++)
                for (var dx = -thickness; dx <= thickness; dx++)
                {
                    if (dx * dx + dy * dy <= thickness * thickness)
                        Plot(px, size, x + dx, y + dy, c);
                }
            }
        }

        static void FillTriangle(Color32[] px, int size, int x0, int y0, int x1, int y1, int x2, int y2, Color32 c)
        {
            var minX = Mathf.Min(x0, Mathf.Min(x1, x2));
            var maxX = Mathf.Max(x0, Mathf.Max(x1, x2));
            var minY = Mathf.Min(y0, Mathf.Min(y1, y2));
            var maxY = Mathf.Max(y0, Mathf.Max(y1, y2));
            for (var y = minY; y <= maxY; y++)
            for (var x = minX; x <= maxX; x++)
            {
                if (Bary(x, y, x0, y0, x1, y1, x2, y2))
                    Plot(px, size, x, y, c);
            }
        }

        static bool Bary(int x, int y, int x0, int y0, int x1, int y1, int x2, int y2)
        {
            var d = (y1 - y2) * (x0 - x2) + (x2 - x1) * (y0 - y2);
            if (Mathf.Abs(d) < 0.0001f)
                return false;
            var a = ((y1 - y2) * (x - x2) + (x2 - x1) * (y - y2)) / (float)d;
            var b = ((y2 - y0) * (x - x2) + (x0 - x2) * (y - y2)) / (float)d;
            var c = 1f - a - b;
            return a >= 0f && b >= 0f && c >= 0f;
        }

        static void Plot(Color32[] px, int size, int x, int y, Color32 c)
        {
            if ((uint)x >= (uint)size || (uint)y >= (uint)size)
                return;
            px[x + y * size] = c;
        }
    }
}
