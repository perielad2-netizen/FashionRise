using UnityEngine;

namespace FashionRise.UI
{
    /// <summary>Runtime-generated soft UI sprites (rounded chips, circles, tool icons).</summary>
    public static class FrUiSprites
    {
        static Sprite? s_circle;
        static Sprite? s_roundSoft;
        static Sprite? s_roundPill;
        static Sprite? s_pencil;
        static Sprite? s_eraser;
        static Sprite? s_undo;
        static Sprite? s_clear;
        static Sprite? s_fade;
        static Sprite? s_photo;
        static Sprite? s_pose;
        static Sprite? s_girl;
        static Sprite? s_boy;
        static Sprite? s_sparkle;
        static Sprite? s_fill;

        public static Sprite Circle => s_circle ??= MakeCircle(64);
        public static Sprite RoundSoft => s_roundSoft ??= MakeRoundedRect(64, 64, 18);
        public static Sprite RoundPill => s_roundPill ??= MakeRoundedRect(96, 48, 24);
        public static Sprite IconPencil => s_pencil ??= MakePencilIcon();
        public static Sprite IconEraser => s_eraser ??= MakeEraserIcon();
        public static Sprite IconUndo => s_undo ??= MakeUndoIcon();
        public static Sprite IconClear => s_clear ??= MakeClearIcon();
        public static Sprite IconFade => s_fade ??= MakeFadeIcon();
        public static Sprite IconPhoto => s_photo ??= MakePhotoIcon();
        public static Sprite IconPose => s_pose ??= MakePoseIcon();
        public static Sprite IconGirl => s_girl ??= MakePersonIcon(true);
        public static Sprite IconBoy => s_boy ??= MakePersonIcon(false);
        public static Sprite IconSparkle => s_sparkle ??= MakeSparkleIcon();
        public static Sprite IconFill => s_fill ??= MakeFillIcon();

        public static Sprite FabricSwatch(Color baseColor, int seed)
        {
            const int n = 48;
            var tex = new Texture2D(n, n, TextureFormat.RGBA32, false)
            {
                filterMode = FilterMode.Bilinear,
                wrapMode = TextureWrapMode.Clamp,
                name = "FrFabric_" + seed
            };
            var rng = new System.Random(seed);
            for (var y = 0; y < n; y++)
            for (var x = 0; x < n; x++)
            {
                var dx = (x + 0.5f) / n * 2f - 1f;
                var dy = (y + 0.5f) / n * 2f - 1f;
                var round = Mathf.Max(Mathf.Abs(dx), Mathf.Abs(dy));
                var corner = Mathf.Clamp01((0.92f - round) * 10f);
                var weave = 0.92f + 0.08f * Mathf.Sin(x * 0.9f + seed) * Mathf.Cos(y * 0.7f);
                var speck = (rng.NextDouble() < 0.08) ? 0.12f : 0f;
                var c = baseColor * weave + Color.white * speck;
                c.a = corner;
                tex.SetPixel(x, y, c);
            }

            tex.Apply(false, false);
            return Sprite.Create(tex, new Rect(0, 0, n, n), new Vector2(0.5f, 0.5f), 100f,
                0, SpriteMeshType.FullRect);
        }

        static Sprite MakeCircle(int n)
        {
            var tex = new Texture2D(n, n, TextureFormat.RGBA32, false)
            {
                filterMode = FilterMode.Bilinear,
                wrapMode = TextureWrapMode.Clamp
            };
            var mid = (n - 1) * 0.5f;
            var r = mid - 0.5f;
            for (var y = 0; y < n; y++)
            for (var x = 0; x < n; x++)
            {
                var d = Vector2.Distance(new Vector2(x, y), new Vector2(mid, mid));
                var a = Mathf.Clamp01((r - d) * 1.6f);
                a = a * a * (3f - 2f * a);
                tex.SetPixel(x, y, new Color(1f, 1f, 1f, a));
            }

            tex.Apply(false, false);
            return Sprite.Create(tex, new Rect(0, 0, n, n), new Vector2(0.5f, 0.5f), 100f);
        }

        static Sprite MakeRoundedRect(int w, int h, float radius)
        {
            var tex = new Texture2D(w, h, TextureFormat.RGBA32, false)
            {
                filterMode = FilterMode.Bilinear,
                wrapMode = TextureWrapMode.Clamp
            };
            for (var y = 0; y < h; y++)
            for (var x = 0; x < w; x++)
            {
                var a = RoundedAlpha(x + 0.5f, y + 0.5f, w, h, radius);
                tex.SetPixel(x, y, new Color(1f, 1f, 1f, a));
            }

            tex.Apply(false, false);
            var border = Mathf.Max(4, Mathf.RoundToInt(radius));
            return Sprite.Create(tex, new Rect(0, 0, w, h), new Vector2(0.5f, 0.5f), 100f, 0,
                SpriteMeshType.FullRect, new Vector4(border, border, border, border));
        }

        static float RoundedAlpha(float x, float y, int w, int h, float radius)
        {
            var r = Mathf.Min(radius, Mathf.Min(w, h) * 0.5f - 1f);
            var cx = Mathf.Clamp(x, r, w - r);
            var cy = Mathf.Clamp(y, r, h - r);
            var d = Vector2.Distance(new Vector2(x, y), new Vector2(cx, cy));
            var a = Mathf.Clamp01((r - d) * 1.8f + 1f);
            return a * a * (3f - 2f * a);
        }

        static Sprite MakeIcon(System.Action<Color32[], int> paint)
        {
            const int n = 64;
            var px = new Color32[n * n];
            for (var i = 0; i < px.Length; i++)
                px[i] = new Color32(0, 0, 0, 0);
            paint(px, n);
            var tex = new Texture2D(n, n, TextureFormat.RGBA32, false)
            {
                filterMode = FilterMode.Bilinear,
                wrapMode = TextureWrapMode.Clamp
            };
            tex.SetPixels32(px);
            tex.Apply(false, false);
            return Sprite.Create(tex, new Rect(0, 0, n, n), new Vector2(0.5f, 0.5f), 100f);
        }

        static void Dot(Color32[] px, int n, int cx, int cy, int r, Color32 c)
        {
            for (var y = cy - r; y <= cy + r; y++)
            for (var x = cx - r; x <= cx + r; x++)
            {
                if (x < 0 || y < 0 || x >= n || y >= n)
                    continue;
                var dx = x - cx;
                var dy = y - cy;
                if (dx * dx + dy * dy <= r * r)
                    px[x + y * n] = c;
            }
        }

        static void Stamp(Color32[] px, int n, int x0, int y0, int x1, int y1, int thickness, Color32 c)
        {
            var steps = Mathf.Max(1, Mathf.CeilToInt(Vector2.Distance(new Vector2(x0, y0), new Vector2(x1, y1))));
            for (var i = 0; i <= steps; i++)
            {
                var t = i / (float)steps;
                var x = Mathf.RoundToInt(Mathf.Lerp(x0, x1, t));
                var y = Mathf.RoundToInt(Mathf.Lerp(y0, y1, t));
                Dot(px, n, x, y, thickness, c);
            }
        }

        static readonly Color32 Ink = new(42, 28, 48, 255);
        static readonly Color32 Soft = new(42, 28, 48, 200);

        static Sprite MakePencilIcon() =>
            MakeIcon((px, n) =>
            {
                Stamp(px, n, 18, 18, 44, 44, 4, Ink);
                Dot(px, n, 16, 16, 3, new Color32(236, 72, 153, 255));
                Stamp(px, n, 40, 40, 48, 48, 3, Soft);
            });

        static Sprite MakeEraserIcon() =>
            MakeIcon((px, n) =>
            {
                for (var y = 22; y <= 40; y++)
                for (var x = 18; x <= 44; x++)
                {
                    var slant = (x - 18) * 0.35f;
                    if (y > 24 + slant && y < 38 + slant)
                        px[x + y * n] = new Color32(255, 170, 190, 255);
                }

                Stamp(px, n, 18, 24, 44, 38, 2, Ink);
                Stamp(px, n, 18, 38, 44, 24, 2, Ink);
            });

        static Sprite MakeUndoIcon() =>
            MakeIcon((px, n) =>
            {
                for (var a = 40; a <= 220; a += 8)
                {
                    var rad = a * Mathf.Deg2Rad;
                    var x = 32 + Mathf.RoundToInt(Mathf.Cos(rad) * 14);
                    var y = 30 + Mathf.RoundToInt(Mathf.Sin(rad) * 14);
                    Dot(px, n, x, y, 2, Ink);
                }

                Stamp(px, n, 18, 36, 14, 28, 2, Ink);
                Stamp(px, n, 18, 36, 26, 32, 2, Ink);
            });

        static Sprite MakeClearIcon() =>
            MakeIcon((px, n) =>
            {
                Stamp(px, n, 20, 20, 44, 44, 3, Ink);
                Stamp(px, n, 20, 44, 44, 20, 3, Ink);
            });

        static Sprite MakeFadeIcon() =>
            MakeIcon((px, n) =>
            {
                for (var i = 0; i < 5; i++)
                {
                    var a = (byte)(220 - i * 40);
                    Dot(px, n, 20 + i * 6, 32, 8 - i, new Color32(42, 28, 48, a));
                }
            });

        static Sprite MakePhotoIcon() =>
            MakeIcon((px, n) =>
            {
                for (var y = 20; y <= 44; y++)
                for (var x = 16; x <= 48; x++)
                    if (x == 16 || x == 48 || y == 20 || y == 44)
                        px[x + y * n] = Ink;
                Dot(px, n, 32, 32, 6, Soft);
                Dot(px, n, 40, 26, 2, Ink);
            });

        static Sprite MakePoseIcon() =>
            MakeIcon((px, n) =>
            {
                Dot(px, n, 32, 46, 4, Ink);
                Stamp(px, n, 32, 42, 32, 28, 2, Ink);
                Stamp(px, n, 32, 36, 22, 30, 2, Ink);
                Stamp(px, n, 32, 36, 42, 30, 2, Ink);
                Stamp(px, n, 32, 28, 24, 16, 2, Ink);
                Stamp(px, n, 32, 28, 40, 16, 2, Ink);
            });

        static Sprite MakePersonIcon(bool girl) =>
            MakeIcon((px, n) =>
            {
                Dot(px, n, 32, 44, 5, Ink);
                Stamp(px, n, 32, 38, 32, 24, 3, Ink);
                Stamp(px, n, 32, 34, 22, 28, 2, Ink);
                Stamp(px, n, 32, 34, 42, 28, 2, Ink);
                if (girl)
                {
                    Stamp(px, n, 32, 24, 24, 14, 2, Ink);
                    Stamp(px, n, 32, 24, 40, 14, 2, Ink);
                    Stamp(px, n, 24, 14, 40, 14, 2, Soft);
                }
                else
                {
                    Stamp(px, n, 32, 24, 26, 14, 2, Ink);
                    Stamp(px, n, 32, 24, 38, 14, 2, Ink);
                }
            });

        static Sprite MakeSparkleIcon() =>
            MakeIcon((px, n) =>
            {
                Stamp(px, n, 32, 14, 32, 50, 2, Ink);
                Stamp(px, n, 14, 32, 50, 32, 2, Ink);
                Stamp(px, n, 20, 20, 44, 44, 2, Soft);
                Stamp(px, n, 20, 44, 44, 20, 2, Soft);
                Dot(px, n, 32, 32, 3, new Color32(236, 72, 153, 255));
            });

        static Sprite MakeFillIcon() =>
            MakeIcon((px, n) =>
            {
                // Paint bucket silhouette
                for (var y = 28; y <= 46; y++)
                for (var x = 22; x <= 42; x++)
                {
                    if (y >= 28 + (x - 22) / 4 && y <= 46 - (x - 32) * (x - 32) / 40)
                        px[x + y * n] = Ink;
                }

                Stamp(px, n, 30, 20, 38, 28, 2, Soft);
                Dot(px, n, 40, 18, 3, new Color32(236, 72, 153, 255));
                Dot(px, n, 44, 22, 2, new Color32(236, 72, 153, 200));
            });
    }
}
