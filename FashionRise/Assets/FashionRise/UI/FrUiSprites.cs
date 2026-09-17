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
        static Sprite? s_brush;
        static Sprite? s_eraser;
        static Sprite? s_fill;
        static Sprite? s_undo;
        static Sprite? s_clear;
        static Sprite? s_fade;
        static Sprite? s_photo;
        static Sprite? s_pose;
        static Sprite? s_girl;
        static Sprite? s_boy;
        static Sprite? s_sparkle;
        static Sprite? s_hueStrip;
        static Sprite? s_svSquare;

        public static Sprite Circle => s_circle ??= MakeCircle(64);
        public static Sprite RoundSoft => s_roundSoft ??= MakeRoundedRect(64, 64, 18);
        public static Sprite RoundPill => s_roundPill ??= MakeRoundedRect(96, 48, 24);
        public static Sprite IconPencil => s_pencil ??= MakePencilIcon();
        public static Sprite IconBrush => s_brush ??= MakeBrushIcon();
        public static Sprite IconEraser => s_eraser ??= MakeEraserIcon();
        public static Sprite IconFill => s_fill ??= MakeFillIcon();
        public static Sprite IconUndo => s_undo ??= MakeUndoIcon();
        public static Sprite IconClear => s_clear ??= MakeClearIcon();
        public static Sprite IconFade => s_fade ??= MakeFadeIcon();
        public static Sprite IconPhoto => s_photo ??= MakePhotoIcon();
        public static Sprite IconPose => s_pose ??= MakePoseIcon();
        public static Sprite IconGirl => s_girl ??= MakePersonIcon(true);
        public static Sprite IconBoy => s_boy ??= MakePersonIcon(false);
        public static Sprite IconSparkle => s_sparkle ??= MakeSparkleIcon();
        public static Sprite HueStrip => s_hueStrip ??= MakeHueStrip(24, 128);
        public static Sprite SvSquare => s_svSquare ??= MakeSvSquare(128);

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

        public static Texture2D BuildSvTexture(float hue, int size = 96)
        {
            var tex = new Texture2D(size, size, TextureFormat.RGBA32, false)
            {
                filterMode = FilterMode.Bilinear,
                wrapMode = TextureWrapMode.Clamp,
                name = "FrSv"
            };
            for (var y = 0; y < size; y++)
            for (var x = 0; x < size; x++)
            {
                var s = x / (float)(size - 1);
                var v = y / (float)(size - 1);
                tex.SetPixel(x, y, Color.HSVToRGB(hue, s, v));
            }

            tex.Apply(false, false);
            return tex;
        }

        static Sprite MakeHueStrip(int w, int h)
        {
            var tex = new Texture2D(w, h, TextureFormat.RGBA32, false)
            {
                filterMode = FilterMode.Bilinear,
                wrapMode = TextureWrapMode.Clamp
            };
            for (var y = 0; y < h; y++)
            {
                var hue = 1f - y / (float)(h - 1);
                var c = Color.HSVToRGB(hue, 1f, 1f);
                for (var x = 0; x < w; x++)
                    tex.SetPixel(x, y, c);
            }

            tex.Apply(false, false);
            return Sprite.Create(tex, new Rect(0, 0, w, h), new Vector2(0.5f, 0.5f), 100f);
        }

        static Sprite MakeSvSquare(int n)
        {
            // Neutral template; live SV texture is rebuilt when hue changes.
            return Sprite.Create(BuildSvTexture(0f, n), new Rect(0, 0, n, n), new Vector2(0.5f, 0.5f), 100f);
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

        static readonly Color32 Ink = new(36, 28, 42, 255);
        static readonly Color32 Soft = new(36, 28, 42, 180);
        static readonly Color32 Accent = new(236, 72, 153, 255);

        static Sprite MakePencilIcon() =>
            MakeIcon((px, n) =>
            {
                // Classic diagonal pencil
                Stamp(px, n, 16, 44, 42, 18, 5, Ink);
                Stamp(px, n, 18, 46, 44, 20, 2, Soft);
                // Tip
                Stamp(px, n, 14, 46, 18, 50, 2, Accent);
                Dot(px, n, 14, 50, 2, Accent);
                // Ferrule
                Stamp(px, n, 38, 20, 46, 12, 3, Soft);
                Dot(px, n, 48, 10, 3, new Color32(255, 200, 120, 255));
            });

        static Sprite MakeBrushIcon() =>
            MakeIcon((px, n) =>
            {
                // Handle
                Stamp(px, n, 28, 14, 28, 34, 4, Ink);
                // Ferrule
                for (var y = 34; y <= 40; y++)
                for (var x = 22; x <= 34; x++)
                    px[x + y * n] = Soft;
                // Bristles
                Stamp(px, n, 24, 40, 20, 52, 2, Accent);
                Stamp(px, n, 28, 40, 28, 54, 2, Accent);
                Stamp(px, n, 32, 40, 36, 52, 2, Accent);
            });

        static Sprite MakeEraserIcon() =>
            MakeIcon((px, n) =>
            {
                // Angled eraser block
                for (var y = 18; y <= 42; y++)
                for (var x = 16; x <= 46; x++)
                {
                    var slant = (x - 16) * 0.4f;
                    if (y > 22 + slant && y < 36 + slant)
                        px[x + y * n] = new Color32(255, 170, 190, 255);
                }

                Stamp(px, n, 18, 24, 44, 38, 2, Ink);
                Stamp(px, n, 18, 36, 44, 22, 2, Ink);
                // Metal band
                Stamp(px, n, 20, 28, 42, 34, 2, Soft);
            });

        static Sprite MakeFillIcon() =>
            MakeIcon((px, n) =>
            {
                // Bucket body
                for (var y = 26; y <= 48; y++)
                for (var x = 18; x <= 40; x++)
                {
                    if (x >= 20 && x <= 38 && y >= 28 && y <= 46)
                        px[x + y * n] = Ink;
                }

                // Handle
                Stamp(px, n, 28, 18, 40, 28, 2, Soft);
                // Spill drop
                Dot(px, n, 44, 40, 4, Accent);
                Dot(px, n, 48, 48, 3, new Color32(236, 72, 153, 200));
            });

        static Sprite MakeUndoIcon() =>
            MakeIcon((px, n) =>
            {
                for (var a = 30; a <= 230; a += 6)
                {
                    var rad = a * Mathf.Deg2Rad;
                    var x = 32 + Mathf.RoundToInt(Mathf.Cos(rad) * 15);
                    var y = 30 + Mathf.RoundToInt(Mathf.Sin(rad) * 15);
                    Dot(px, n, x, y, 2, Ink);
                }

                Stamp(px, n, 16, 38, 12, 28, 2, Ink);
                Stamp(px, n, 16, 38, 24, 34, 2, Ink);
            });

        static Sprite MakeClearIcon() =>
            MakeIcon((px, n) =>
            {
                // Trash can
                for (var y = 22; y <= 48; y++)
                for (var x = 20; x <= 44; x++)
                    if (x == 20 || x == 44 || y == 48 || (y == 22 && x >= 20 && x <= 44))
                        px[x + y * n] = Ink;
                Stamp(px, n, 18, 20, 46, 20, 2, Ink);
                Stamp(px, n, 28, 14, 36, 14, 2, Soft);
                Stamp(px, n, 26, 28, 26, 42, 1, Soft);
                Stamp(px, n, 32, 28, 32, 42, 1, Soft);
                Stamp(px, n, 38, 28, 38, 42, 1, Soft);
            });

        static Sprite MakeFadeIcon() =>
            MakeIcon((px, n) =>
            {
                for (var i = 0; i < 5; i++)
                {
                    var a = (byte)(230 - i * 42);
                    Dot(px, n, 18 + i * 7, 32, 9 - i, new Color32(36, 28, 42, a));
                }
            });

        static Sprite MakePhotoIcon() =>
            MakeIcon((px, n) =>
            {
                for (var y = 18; y <= 46; y++)
                for (var x = 14; x <= 50; x++)
                    if (x == 14 || x == 50 || y == 18 || y == 46)
                        px[x + y * n] = Ink;
                Dot(px, n, 32, 32, 7, Soft);
                Dot(px, n, 42, 24, 2, Accent);
            });

        static Sprite MakePoseIcon() =>
            MakeIcon((px, n) =>
            {
                Dot(px, n, 32, 48, 4, Ink);
                Stamp(px, n, 32, 44, 32, 28, 2, Ink);
                Stamp(px, n, 32, 38, 18, 44, 2, Soft);
                Stamp(px, n, 32, 38, 46, 32, 2, Soft);
                Stamp(px, n, 32, 28, 24, 14, 2, Ink);
                Stamp(px, n, 32, 28, 40, 14, 2, Ink);
            });

        static Sprite MakePersonIcon(bool girl) =>
            MakeIcon((px, n) =>
            {
                Dot(px, n, 32, 46, 5, Ink);
                Stamp(px, n, 32, 40, 32, 26, 3, Ink);
                Stamp(px, n, 32, 36, 22, 30, 2, Soft);
                Stamp(px, n, 32, 36, 42, 30, 2, Soft);
                if (girl)
                {
                    Stamp(px, n, 32, 26, 22, 12, 2, Ink);
                    Stamp(px, n, 32, 26, 42, 12, 2, Ink);
                    Stamp(px, n, 22, 12, 42, 12, 2, Soft);
                }
                else
                {
                    Stamp(px, n, 32, 26, 26, 12, 2, Ink);
                    Stamp(px, n, 32, 26, 38, 12, 2, Ink);
                }
            });

        static Sprite MakeSparkleIcon() =>
            MakeIcon((px, n) =>
            {
                Stamp(px, n, 32, 12, 32, 52, 2, Ink);
                Stamp(px, n, 12, 32, 52, 32, 2, Ink);
                Stamp(px, n, 18, 18, 46, 46, 2, Soft);
                Stamp(px, n, 18, 46, 46, 18, 2, Soft);
                Dot(px, n, 32, 32, 3, Accent);
            });
    }
}
