using System;
using FashionRise.Application;
using FashionRise.Domain;
using UnityEngine;

namespace FashionRise.Presentation.Sketch
{
    /// <summary>
    /// Default sketch underlay: <c>Resources/SketchReference/female_model</c> and <c>male_model</c> when present;
    /// otherwise procedural croquis.
    /// </summary>
    public static class SketchDefaultFigureGenerator
    {
        public const string FemaleResourcePath = "SketchReference/female_model";
        public const string MaleResourcePath = "SketchReference/male_model";

        static readonly Color32 Paper = new(255, 255, 255, 255);
        static readonly Color32 Fill = new(218, 214, 208, 255);
        static readonly Color32 Stroke = new(88, 84, 80, 255);

        public static string ResourcePathFor(SketchFigureTemplate template, int poseIndex)
        {
            var gender = template == SketchFigureTemplate.Male ? "male" : "female";
            var n = Mathf.Clamp(poseIndex, 0, SketchFigurePreferences.PoseCount - 1) + 1;
            return $"SketchReference/{gender}_{n:00}";
        }

        /// <summary>Blit bundled PNG from Resources into <paramref name="dest"/> (pad size). Returns false if asset missing.</summary>
        public static bool TryFillReferenceFromBundledImage(Color32[] dest, int w, int h, SketchFigureTemplate template,
            int poseIndex = 0)
        {
            var path = ResourcePathFor(template, poseIndex);
            var src = Resources.Load<Texture2D>(path);
            if (src == null)
            {
                // Legacy single-file assets
                path = template == SketchFigureTemplate.Male ? MaleResourcePath : FemaleResourcePath;
                src = Resources.Load<Texture2D>(path);
            }

            if (src == null)
                return false;

            BlitAspectFit(src, dest, w, h, Paper);
            return true;
        }

        /// <summary>
        /// Scale source to fit inside <paramref name="w"/>×<paramref name="h"/> without stretching;
        /// letterbox / pillarbox with <paramref name="paper"/>.
        /// </summary>
        public static void BlitAspectFit(Texture src, Color32[] dest, int w, int h, Color32 paper)
        {
            for (var i = 0; i < dest.Length; i++)
                dest[i] = paper;

            if (src == null || src.width < 1 || src.height < 1 || w < 1 || h < 1)
                return;

            var srcAspect = src.width / (float)src.height;
            var dstAspect = w / (float)h;
            int dw;
            int dh;
            int ox;
            int oy;
            if (srcAspect > dstAspect)
            {
                dw = w;
                dh = Mathf.Max(1, Mathf.RoundToInt(w / srcAspect));
                ox = 0;
                oy = (h - dh) / 2;
            }
            else
            {
                dh = h;
                dw = Mathf.Max(1, Mathf.RoundToInt(h * srcAspect));
                ox = (w - dw) / 2;
                oy = 0;
            }

            var rt = RenderTexture.GetTemporary(dw, dh, 0, RenderTextureFormat.ARGB32, RenderTextureReadWrite.Linear);
            Graphics.Blit(src, rt);
            var prev = RenderTexture.active;
            RenderTexture.active = rt;
            var temp = new Texture2D(dw, dh, TextureFormat.RGBA32, false);
            temp.ReadPixels(new Rect(0, 0, dw, dh), 0, 0);
            temp.Apply();
            RenderTexture.active = prev;
            RenderTexture.ReleaseTemporary(rt);
            var px = temp.GetPixels32();
            UnityEngine.Object.Destroy(temp);

            for (var y = 0; y < dh; y++)
            {
                var destY = oy + y;
                if ((uint)destY >= (uint)h)
                    continue;
                var srcRow = y * dw;
                var destRow = destY * w;
                for (var x = 0; x < dw; x++)
                {
                    var destX = ox + x;
                    if ((uint)destX >= (uint)w)
                        continue;
                    var s = px[srcRow + x];
                    if (s.a >= 250)
                    {
                        dest[destRow + destX] = new Color32(s.r, s.g, s.b, 255);
                        continue;
                    }

                    if (s.a < 8)
                        continue;

                    var a = s.a / 255f;
                    var d = dest[destRow + destX];
                    dest[destRow + destX] = new Color32(
                        (byte)Mathf.Clamp(Mathf.RoundToInt(s.r * a + d.r * (1f - a)), 0, 255),
                        (byte)Mathf.Clamp(Mathf.RoundToInt(s.g * a + d.g * (1f - a)), 0, 255),
                        (byte)Mathf.Clamp(Mathf.RoundToInt(s.b * a + d.b * (1f - a)), 0, 255),
                        255);
                }
            }
        }

        public static void FillReference(Color32[] buf, int w, int h, SketchFigureTemplate template)
        {
            for (var i = 0; i < buf.Length; i++)
                buf[i] = Paper;

            var footY = h * 0.07f;
            var hipY = h * 0.30f;
            var waistY = h * 0.46f;
            var shoulderY = h * 0.60f;
            var neckY = h * 0.665f;
            var headCy = h * 0.745f;
            var cx = w * 0.5f;

            float shoulderHalf;
            float waistHalf;
            float hipHalf;
            if (template == SketchFigureTemplate.Male)
            {
                shoulderHalf = w * 0.125f;
                waistHalf = w * 0.095f;
                hipHalf = w * 0.105f;
            }
            else
            {
                shoulderHalf = w * 0.095f;
                waistHalf = w * 0.072f;
                hipHalf = w * 0.128f;
            }

            var headR = w * 0.052f;
            var thick = Mathf.Max(2f, w * 0.018f);

            // Torso fill (trapezoid shoulder → waist → hip)
            FillTrapezoid(buf, w, h,
                cx - shoulderHalf, shoulderY, cx + shoulderHalf, shoulderY,
                cx - waistHalf, waistY, cx + waistHalf, waistY, Fill);
            FillTrapezoid(buf, w, h,
                cx - waistHalf, waistY, cx + waistHalf, waistY,
                cx - hipHalf, hipY, cx + hipHalf, hipY, Fill);

            // Neck
            DrawThickLine(buf, w, h, cx, shoulderY, cx, neckY, thick * 0.55f, Fill);
            DrawThickLine(buf, w, h, cx, shoulderY, cx, neckY, thick * 0.2f, Stroke);

            // Head
            FillDisk(buf, w, h, cx, headCy, headR * 0.92f, Fill);
            DrawDiskOutline(buf, w, h, cx, headCy, headR * 0.92f, thick * 0.35f, Stroke);

            // Outer contour (stroke on top)
            DrawThickLine(buf, w, h, cx - shoulderHalf, shoulderY, cx - waistHalf, waistY, thick * 0.35f, Stroke);
            DrawThickLine(buf, w, h, cx + shoulderHalf, shoulderY, cx + waistHalf, waistY, thick * 0.35f, Stroke);
            DrawThickLine(buf, w, h, cx - waistHalf, waistY, cx - hipHalf, hipY, thick * 0.35f, Stroke);
            DrawThickLine(buf, w, h, cx + waistHalf, waistY, cx + hipHalf, hipY, thick * 0.35f, Stroke);

            // Legs (slight A-line to ankles)
            var ankle = w * 0.055f;
            DrawThickLine(buf, w, h, cx - hipHalf * 0.85f, hipY, cx - ankle, footY, thick * 0.9f, Fill);
            DrawThickLine(buf, w, h, cx + hipHalf * 0.85f, hipY, cx + ankle, footY, thick * 0.9f, Fill);
            DrawThickLine(buf, w, h, cx - hipHalf * 0.85f, hipY, cx - ankle, footY, thick * 0.32f, Stroke);
            DrawThickLine(buf, w, h, cx + hipHalf * 0.85f, hipY, cx + ankle, footY, thick * 0.32f, Stroke);

            // Arms (simple hanging)
            var handY = hipY + (waistY - hipY) * 0.35f;
            var elbowX = shoulderHalf * 1.55f;
            DrawThickLine(buf, w, h, cx - shoulderHalf, shoulderY * 0.995f, cx - elbowX, handY, thick * 0.65f, Fill);
            DrawThickLine(buf, w, h, cx + shoulderHalf, shoulderY * 0.995f, cx + elbowX, handY, thick * 0.65f, Fill);
            DrawThickLine(buf, w, h, cx - shoulderHalf, shoulderY * 0.995f, cx - elbowX, handY, thick * 0.28f, Stroke);
            DrawThickLine(buf, w, h, cx + shoulderHalf, shoulderY * 0.995f, cx + elbowX, handY, thick * 0.28f, Stroke);

            // Ground hint
            DrawThickLine(buf, w, h, w * 0.12f, footY - thick * 0.2f, w * 0.88f, footY - thick * 0.2f, thick * 0.25f,
                new Color32(180, 176, 170, 255));
        }

        static void FillTrapezoid(Color32[] buf, int w, int h,
            float x1, float y1, float x2, float y2, float x3, float y3, float x4, float y4, Color32 fill)
        {
            var yMin = Mathf.Max(0, Mathf.FloorToInt(Mathf.Min(y1, Mathf.Min(y2, Mathf.Min(y3, y4))) - 2));
            var yMax = Mathf.Min(h - 1, Mathf.CeilToInt(Mathf.Max(y1, Mathf.Max(y2, Mathf.Max(y3, y4))) + 2));
            for (var y = yMin; y <= yMax; y++)
            {
                var xa = IntersectX(x1, y1, x4, y4, y);
                var xb = IntersectX(x2, y2, x3, y3, y);
                if (float.IsNaN(xa) || float.IsNaN(xb))
                    continue;
                if (xa > xb)
                    (xa, xb) = (xb, xa);
                var x0 = Mathf.Clamp(Mathf.FloorToInt(xa), 0, w - 1);
                var x1b = Mathf.Clamp(Mathf.CeilToInt(xb), 0, w - 1);
                for (var x = x0; x <= x1b; x++)
                    Set(buf, w, h, x, y, fill);
            }
        }

        static float IntersectX(float ax, float ay, float bx, float by, float y)
        {
            if (Mathf.Abs(by - ay) < 0.001f)
                return float.NaN;
            if ((y < Mathf.Min(ay, by) - 0.01f) || (y > Mathf.Max(ay, by) + 0.01f))
                return float.NaN;
            var t = (y - ay) / (by - ay);
            return ax + (bx - ax) * t;
        }

        static void FillDisk(Color32[] buf, int w, int h, float cx, float cy, float r, Color32 fill)
        {
            var x0 = Mathf.Clamp(Mathf.FloorToInt(cx - r - 1), 0, w - 1);
            var x1 = Mathf.Clamp(Mathf.CeilToInt(cx + r + 1), 0, w - 1);
            var y0 = Mathf.Clamp(Mathf.FloorToInt(cy - r - 1), 0, h - 1);
            var y1 = Mathf.Clamp(Mathf.CeilToInt(cy + r + 1), 0, h - 1);
            var r2 = r * r;
            for (var y = y0; y <= y1; y++)
            for (var x = x0; x <= x1; x++)
            {
                var dx = x - cx;
                var dy = y - cy;
                if (dx * dx + dy * dy <= r2)
                    Set(buf, w, h, x, y, fill);
            }
        }

        static void DrawDiskOutline(Color32[] buf, int w, int h, float cx, float cy, float r, float thickness,
            Color32 col)
        {
            var steps = Mathf.Max(48, Mathf.RoundToInt(r * 6f));
            for (var i = 0; i < steps; i++)
            {
                var t = (i + 1) / (float)steps * Mathf.PI * 2f;
                var x = cx + Mathf.Cos(t) * r;
                var y = cy + Mathf.Sin(t) * r;
                StampDisk(buf, w, h, x, y, thickness * 0.5f, col);
            }
        }

        static void DrawThickLine(Color32[] buf, int w, int h, float x0, float y0, float x1, float y1, float thickness,
            Color32 col)
        {
            var dist = Mathf.Sqrt((x1 - x0) * (x1 - x0) + (y1 - y0) * (y1 - y0));
            var steps = Mathf.Max(1, Mathf.CeilToInt(dist / Mathf.Max(0.5f, thickness * 0.25f)));
            for (var i = 0; i <= steps; i++)
            {
                var t = i / (float)steps;
                var x = x0 + (x1 - x0) * t;
                var y = y0 + (y1 - y0) * t;
                StampDisk(buf, w, h, x, y, thickness * 0.5f, col);
            }
        }

        static void StampDisk(Color32[] buf, int w, int h, float cx, float cy, float radius, Color32 col)
        {
            var ir = Mathf.CeilToInt(radius) + 1;
            var x0 = Mathf.Clamp(Mathf.FloorToInt(cx) - ir, 0, w - 1);
            var x1 = Mathf.Clamp(Mathf.FloorToInt(cx) + ir, 0, w - 1);
            var y0 = Mathf.Clamp(Mathf.FloorToInt(cy) - ir, 0, h - 1);
            var y1 = Mathf.Clamp(Mathf.FloorToInt(cy) + ir, 0, h - 1);
            var r2 = radius * radius;
            for (var y = y0; y <= y1; y++)
            for (var x = x0; x <= x1; x++)
            {
                var dx = x - cx;
                var dy = y - cy;
                if (dx * dx + dy * dy <= r2)
                    Set(buf, w, h, x, y, col);
            }
        }

        static void Set(Color32[] buf, int w, int h, int x, int y, Color32 c) => buf[x + y * w] = c;
    }
}
