using System.Collections.Generic;
using System.IO;
using FashionRise.Application;
using FashionRise.Content;
using FashionRise.Core.Navigation;
using FashionRise.Domain;
using FashionRise.Presentation.Sketch;
using FashionRise.UI;
using UnityEngine;
using UnityEngine.Events;
using UnityEngine.EventSystems;
using UnityEngine.UI;

namespace FashionRise.Presentation.Screens
{
    /// <summary>
    /// Modern kid fashion studio — icon tools, circular color picker, fabric chips,
    /// full-height mannequin. Draw → MAGIC!
    /// </summary>
    public sealed class SketchCanvasScreen : ScreenBase
    {
        public override ScreenId Id => ScreenId.SketchCanvas;

        UiSketchPad _pad = null!;
        Text _hint = null!;
        FashionRiseTheme _theme = null!;
        bool _padBootstrapped;
        bool _refDimmed;

        Image? _pencilFace;
        Image? _eraserFace;
        Image? _fillFace;
        readonly Image[] _sizeFaces = new Image[3];
        readonly Image[] _colorRings = new Image[8];
        readonly Image[] _fabricFaces = new Image[6];
        readonly string?[] _fabricForColor = new string[8];
        Text? _pairHint;
        int _sizeIndex = 1;
        int _colorIndex;
        int _fabricIndex = -1;
        enum DrawTool { Pencil, Eraser, Fill }
        DrawTool _tool = DrawTool.Pencil;

        static readonly int[] BrushSizes = { 3, 9, 20 };

        static readonly Color[] InkColors =
        {
            new(0.10f, 0.08f, 0.08f),
            new(0.86f, 0.18f, 0.36f),
            new(0.12f, 0.30f, 0.68f),
            new(0.96f, 0.58f, 0.18f),
            new(0.18f, 0.62f, 0.32f),
            new(0.78f, 0.40f, 0.72f),
            new(0.97f, 0.94f, 0.90f),
            new(0.48f, 0.48f, 0.52f),
        };

        static readonly string[] ColorNames =
        {
            "Ink", "Rose", "Navy", "Gold", "Green", "Orchid", "Cream", "Grey"
        };

        static readonly (string name, Color color, int radius)[] Fabrics =
        {
            ("Silk", new Color(0.98f, 0.90f, 0.94f), 7),
            ("Denim", new Color(0.22f, 0.38f, 0.62f), 13),
            ("Velvet", new Color(0.45f, 0.08f, 0.22f), 15),
            ("Glitter", new Color(0.95f, 0.35f, 0.65f), 11),
            ("Leather", new Color(0.18f, 0.12f, 0.10f), 12),
            ("Cotton", new Color(0.92f, 0.94f, 0.98f), 9),
        };

        void Awake()
        {
            var t = ThemeOrDefault;
            _theme = t;
            var root = FrUiFactory.CreateStretchPanel(transform, "Root", t);

            BuildTopBar(root, t);
            BuildStudio(root, t);

            SelectPencil();
            SetSize(1);
            SetColor(0);
        }

        void BuildTopBar(RectTransform root, FashionRiseTheme t)
        {
            var top = new GameObject("TopBar", typeof(RectTransform), typeof(HorizontalLayoutGroup));
            var topRt = top.GetComponent<RectTransform>();
            topRt.SetParent(root, false);
            topRt.anchorMin = new Vector2(0f, 1f);
            topRt.anchorMax = new Vector2(1f, 1f);
            topRt.pivot = new Vector2(0.5f, 1f);
            topRt.sizeDelta = new Vector2(0f, 70f);
            topRt.anchoredPosition = Vector2.zero;
            var topH = top.GetComponent<HorizontalLayoutGroup>();
            topH.padding = new RectOffset(14, 14, 10, 8);
            topH.spacing = 12f;
            topH.childAlignment = TextAnchor.MiddleCenter;
            topH.childControlWidth = true;
            topH.childForceExpandWidth = false;
            topH.childControlHeight = true;
            topH.childForceExpandHeight = true;

            var back = MakeCircleIconButton(top.transform, "Back", null, "‹", t, () =>
            {
                if (App.Navigation != null)
                    _ = App.Navigation.GoBackAsync();
            }, 48f);
            var backLe = back.gameObject.AddComponent<LayoutElement>();
            backLe.minWidth = 48f;
            backLe.preferredWidth = 48f;
            backLe.minHeight = 48f;

            var hintWrap = new GameObject("HintWrap", typeof(RectTransform), typeof(Image), typeof(LayoutElement));
            hintWrap.transform.SetParent(top.transform, false);
            var hintImg = hintWrap.GetComponent<Image>();
            hintImg.sprite = FrUiSprites.RoundPill;
            hintImg.type = Image.Type.Sliced;
            hintImg.color = new Color(1f, 1f, 1f, 0.78f);
            var hintLe = hintWrap.GetComponent<LayoutElement>();
            hintLe.flexibleWidth = 1f;
            hintLe.minHeight = 44f;
            hintLe.preferredHeight = 44f;
            _hint = FrUiFactory.AddLabel(hintWrap.transform, "Hint", "Draw your look", t,
                Mathf.RoundToInt(t.BodySize), FontStyle.Bold, TextAnchor.MiddleCenter);
            var hTxt = _hint.GetComponent<LayoutElement>();
            if (hTxt != null)
            {
                hTxt.minHeight = 36f;
                hTxt.preferredHeight = 36f;
                hTxt.flexibleWidth = 1f;
            }

            var hRt = _hint.GetComponent<RectTransform>();
            hRt.anchorMin = Vector2.zero;
            hRt.anchorMax = Vector2.one;
            hRt.offsetMin = new Vector2(12f, 4f);
            hRt.offsetMax = new Vector2(-12f, -4f);

            var magic = MakeMagicButton(top.transform, t);
            var magicLe = magic.gameObject.AddComponent<LayoutElement>();
            magicLe.minWidth = 128f;
            magicLe.preferredWidth = 136f;
            magicLe.minHeight = 50f;
            magicLe.preferredHeight = 50f;
        }

        Button MakeMagicButton(Transform parent, FashionRiseTheme t)
        {
            var go = new GameObject("Magic", typeof(Image), typeof(Button));
            go.transform.SetParent(parent, false);
            var face = go.GetComponent<Image>();
            face.sprite = FrUiSprites.RoundPill;
            face.type = Image.Type.Sliced;
            face.color = t.Accent;
            var shadow = go.AddComponent<Shadow>();
            shadow.effectColor = new Color(0.55f, 0.12f, 0.28f, 0.28f);
            shadow.effectDistance = new Vector2(0f, -5f);

            var icon = new GameObject("Spark", typeof(Image));
            icon.transform.SetParent(go.transform, false);
            var iconImg = icon.GetComponent<Image>();
            iconImg.sprite = FrUiSprites.IconSparkle;
            iconImg.color = Color.white;
            iconImg.raycastTarget = false;
            var irt = icon.GetComponent<RectTransform>();
            irt.anchorMin = new Vector2(0f, 0.5f);
            irt.anchorMax = new Vector2(0f, 0.5f);
            irt.pivot = new Vector2(0f, 0.5f);
            irt.anchoredPosition = new Vector2(14f, 0f);
            irt.sizeDelta = new Vector2(26f, 26f);

            var txtGo = new GameObject("Text", typeof(Text));
            txtGo.transform.SetParent(go.transform, false);
            var txt = txtGo.GetComponent<Text>();
            txt.font = Resources.GetBuiltinResource<Font>("LegacyRuntime.ttf");
            txt.text = "MAGIC!";
            txt.fontSize = 20;
            txt.fontStyle = FontStyle.Bold;
            txt.alignment = TextAnchor.MiddleCenter;
            txt.color = Color.white;
            txt.raycastTarget = false;
            var trt = txtGo.GetComponent<RectTransform>();
            trt.anchorMin = Vector2.zero;
            trt.anchorMax = Vector2.one;
            trt.offsetMin = new Vector2(34f, 0f);
            trt.offsetMax = new Vector2(-10f, 0f);

            var btn = go.GetComponent<Button>();
            btn.targetGraphic = face;
            btn.onClick.AddListener(ContinueToEnhancement);
            var motion = go.AddComponent<FrUiMotion>();
            motion.EnablePulse(true);
            HookPress(go, motion);
            return btn;
        }

        void BuildStudio(RectTransform root, FashionRiseTheme t)
        {
            var studio = new GameObject("Studio", typeof(RectTransform));
            var studioRt = studio.GetComponent<RectTransform>();
            studioRt.SetParent(root, false);
            studioRt.anchorMin = Vector2.zero;
            studioRt.anchorMax = Vector2.one;
            studioRt.offsetMin = new Vector2(0f, 4f);
            studioRt.offsetMax = new Vector2(0f, -72f);

            BuildMannequinStage(studioRt, t);
            BuildLeftTools(studioRt, t);
            BuildRightPalette(studioRt, t);
        }

        void BuildMannequinStage(RectTransform studio, FashionRiseTheme t)
        {
            var stage = new GameObject("MannequinStage", typeof(RectTransform), typeof(Image));
            stage.transform.SetParent(studio, false);
            var stageRt = stage.GetComponent<RectTransform>();
            stageRt.anchorMin = Vector2.zero;
            stageRt.anchorMax = Vector2.one;
            stageRt.offsetMin = Vector2.zero;
            stageRt.offsetMax = Vector2.zero;
            var stageImg = stage.GetComponent<Image>();
            stageImg.color = new Color(1f, 1f, 1f, 0.22f);
            stageImg.raycastTarget = false;

            // Soft runway glow behind the figure
            var glow = new GameObject("RunwayGlow", typeof(RectTransform), typeof(Image));
            glow.transform.SetParent(stage.transform, false);
            var glowRt = glow.GetComponent<RectTransform>();
            glowRt.anchorMin = new Vector2(0.18f, 0.02f);
            glowRt.anchorMax = new Vector2(0.82f, 0.98f);
            glowRt.offsetMin = Vector2.zero;
            glowRt.offsetMax = Vector2.zero;
            var glowImg = glow.GetComponent<Image>();
            glowImg.sprite = FrUiSprites.Circle;
            glowImg.color = new Color(t.Champagne.r, t.Champagne.g, t.Champagne.b, 0.45f);
            glowImg.raycastTarget = false;
            var glowMotion = glow.AddComponent<FrUiMotion>();
            glowMotion.EnablePulse(true);

            var padGo = new GameObject("SketchPad", typeof(RectTransform), typeof(RawImage), typeof(UiSketchPad),
                typeof(AspectRatioFitter));
            padGo.transform.SetParent(stage.transform, false);
            var padRt = padGo.GetComponent<RectTransform>();
            padRt.anchorMin = new Vector2(0.5f, 0f);
            padRt.anchorMax = new Vector2(0.5f, 1f);
            padRt.pivot = new Vector2(0.5f, 0.5f);
            padRt.offsetMin = new Vector2(0f, 8f);
            padRt.offsetMax = new Vector2(0f, -8f);
            _pad = padGo.GetComponent<UiSketchPad>();
            var fitter = padGo.GetComponent<AspectRatioFitter>();
            fitter.aspectMode = AspectRatioFitter.AspectMode.HeightControlsWidth;
            fitter.aspectRatio = _pad.TextureAspect;
            var rim = padGo.GetComponent<RawImage>();
            rim.raycastTarget = true;
            rim.color = Color.white;
        }

        void BuildLeftTools(RectTransform studio, FashionRiseTheme t)
        {
            var rail = MakeFloatingRail(studio, "LeftTools", true, 78f, t);
            AddSectionLabel(rail, "DRAW", t);

            _pencilFace = MakeIconTool(rail, "Pencil", FrUiSprites.IconPencil, t, SelectPencil, 58f).GetComponent<Image>();
            _eraserFace = MakeIconTool(rail, "Eraser", FrUiSprites.IconEraser, t, SelectEraser, 58f).GetComponent<Image>();
            _fillFace = MakeIconTool(rail, "Fill", FrUiSprites.IconFill, t, SelectFill, 58f).GetComponent<Image>();

            AddSectionLabel(rail, "SIZE", t);
            for (var i = 0; i < 3; i++)
            {
                var idx = i;
                var size = 14f + i * 10f;
                _sizeFaces[i] = MakeSizeChip(rail, idx, size, t, () => SetSize(idx));
            }

            AddSectionLabel(rail, "FIX", t);
            MakeIconTool(rail, "Undo", FrUiSprites.IconUndo, t, () =>
            {
                if (!_pad.UndoStroke())
                    FlashHint("Nothing to undo");
                else
                    FlashHint("Undone");
            }, 52f);
            MakeIconTool(rail, "Clear", FrUiSprites.IconClear, t, () =>
            {
                _pad.ClearAll();
                FlashHint("Fresh page");
            }, 52f);
            MakeIconTool(rail, "Fade", FrUiSprites.IconFade, t, ToggleReferenceDim, 52f);
        }

        void BuildRightPalette(RectTransform studio, FashionRiseTheme t)
        {
            var rail = MakeFloatingRail(studio, "RightPalette", false, 92f, t);

            AddSectionLabel(rail, "COLOR", t);
            var colorRow = new GameObject("Colors", typeof(RectTransform), typeof(GridLayoutGroup),
                typeof(LayoutElement), typeof(ContentSizeFitter));
            colorRow.transform.SetParent(rail, false);
            var grid = colorRow.GetComponent<GridLayoutGroup>();
            grid.constraint = GridLayoutGroup.Constraint.FixedColumnCount;
            grid.constraintCount = 2;
            grid.cellSize = new Vector2(36f, 36f);
            grid.spacing = new Vector2(8f, 8f);
            grid.childAlignment = TextAnchor.UpperCenter;
            var gridLe = colorRow.GetComponent<LayoutElement>();
            gridLe.minHeight = 160f;
            gridLe.preferredHeight = 160f;
            colorRow.GetComponent<ContentSizeFitter>().verticalFit = ContentSizeFitter.FitMode.PreferredSize;

            for (var i = 0; i < InkColors.Length; i++)
            {
                var idx = i;
                _colorRings[i] = MakeColorDot(colorRow.transform, InkColors[i], () =>
                {
                    _fabricIndex = -1;
                    ClearFabricSelection();
                    SetColor(idx);
                });
            }

            AddSectionLabel(rail, "FABRIC", t);
            for (var i = 0; i < Fabrics.Length; i++)
            {
                var idx = i;
                _fabricFaces[i] = MakeFabricChip(rail, Fabrics[i].name, Fabrics[i].color, idx,
                    () => SelectFabric(idx));
            }

            _pairHint = FrUiFactory.AddLabel(rail, "Pairs", "Tap color, then fabric", t, 10, FontStyle.Normal,
                TextAnchor.MiddleCenter, useSecondaryTextColor: true);
            var pairLe = _pairHint.GetComponent<LayoutElement>() ?? _pairHint.gameObject.AddComponent<LayoutElement>();
            pairLe.minHeight = 36f;
            pairLe.preferredHeight = 44f;

            AddSectionLabel(rail, "MODEL", t);
            MakeIconTool(rail, "Girl", FrUiSprites.IconGirl, t, () =>
            {
                SketchFigurePreferences.DefaultTemplate = SketchFigureTemplate.Female;
                ApplyCurrentFigure("Girl model");
            }, 52f);
            MakeIconTool(rail, "Boy", FrUiSprites.IconBoy, t, () =>
            {
                SketchFigurePreferences.DefaultTemplate = SketchFigureTemplate.Male;
                ApplyCurrentFigure("Boy model");
            }, 52f);
            MakeIconTool(rail, "Photo", FrUiSprites.IconPhoto, t, () =>
            {
                if (App.Navigation != null)
                    _ = App.Navigation.NavigateToAsync(ScreenId.ImportSketch);
            }, 52f);
            MakeIconTool(rail, "Pose", FrUiSprites.IconPose, t, CyclePose, 52f);
        }

        static Transform MakeFloatingRail(RectTransform parent, string name, bool left, float width,
            FashionRiseTheme t)
        {
            var shell = new GameObject(name, typeof(RectTransform), typeof(Image));
            shell.transform.SetParent(parent, false);
            var rt = shell.GetComponent<RectTransform>();
            if (left)
            {
                rt.anchorMin = new Vector2(0f, 0.02f);
                rt.anchorMax = new Vector2(0f, 0.98f);
                rt.pivot = new Vector2(0f, 0.5f);
                rt.sizeDelta = new Vector2(width, 0f);
                rt.anchoredPosition = new Vector2(8f, 0f);
            }
            else
            {
                rt.anchorMin = new Vector2(1f, 0.02f);
                rt.anchorMax = new Vector2(1f, 0.98f);
                rt.pivot = new Vector2(1f, 0.5f);
                rt.sizeDelta = new Vector2(width, 0f);
                rt.anchoredPosition = new Vector2(-8f, 0f);
            }

            var face = shell.GetComponent<Image>();
            face.sprite = FrUiSprites.RoundSoft;
            face.type = Image.Type.Sliced;
            face.color = new Color(1f, 1f, 1f, 0.82f);
            var shadow = shell.AddComponent<Shadow>();
            shadow.effectColor = new Color(0.2f, 0.08f, 0.14f, 0.18f);
            shadow.effectDistance = new Vector2(left ? 5f : -5f, -6f);

            var scrollGo = new GameObject("Scroll", typeof(RectTransform), typeof(ScrollRect), typeof(RectMask2D));
            scrollGo.transform.SetParent(shell.transform, false);
            var scrollRt = scrollGo.GetComponent<RectTransform>();
            scrollRt.anchorMin = Vector2.zero;
            scrollRt.anchorMax = Vector2.one;
            scrollRt.offsetMin = new Vector2(6f, 8f);
            scrollRt.offsetMax = new Vector2(-6f, -8f);

            var content = new GameObject("Content", typeof(RectTransform), typeof(VerticalLayoutGroup),
                typeof(ContentSizeFitter));
            content.transform.SetParent(scrollGo.transform, false);
            var contentRt = content.GetComponent<RectTransform>();
            contentRt.anchorMin = new Vector2(0f, 1f);
            contentRt.anchorMax = new Vector2(1f, 1f);
            contentRt.pivot = new Vector2(0.5f, 1f);
            contentRt.sizeDelta = Vector2.zero;
            var v = content.GetComponent<VerticalLayoutGroup>();
            v.padding = new RectOffset(4, 4, 4, 10);
            v.spacing = 8f;
            v.childAlignment = TextAnchor.UpperCenter;
            v.childControlWidth = true;
            v.childForceExpandWidth = true;
            v.childControlHeight = true;
            v.childForceExpandHeight = false;
            content.GetComponent<ContentSizeFitter>().verticalFit = ContentSizeFitter.FitMode.PreferredSize;

            var scroll = scrollGo.GetComponent<ScrollRect>();
            scroll.content = contentRt;
            scroll.viewport = scrollRt;
            scroll.horizontal = false;
            scroll.vertical = true;
            scroll.movementType = ScrollRect.MovementType.Clamped;
            scroll.scrollSensitivity = 32f;
            return content.transform;
        }

        static void AddSectionLabel(Transform parent, string text, FashionRiseTheme t)
        {
            var label = FrUiFactory.AddLabel(parent, text, text, t, 11, FontStyle.Bold,
                TextAnchor.MiddleCenter, useSecondaryTextColor: true);
            var le = label.GetComponent<LayoutElement>() ?? label.gameObject.AddComponent<LayoutElement>();
            le.minHeight = 14f;
            le.preferredHeight = 16f;
        }

        Button MakeIconTool(Transform parent, string name, Sprite icon, FashionRiseTheme t, UnityAction onClick,
            float size)
        {
            var go = new GameObject(name + "_Tool", typeof(Image), typeof(Button), typeof(LayoutElement));
            go.transform.SetParent(parent, false);
            var face = go.GetComponent<Image>();
            face.sprite = FrUiSprites.Circle;
            face.color = t.ButtonFace;
            var le = go.GetComponent<LayoutElement>();
            le.minHeight = size;
            le.preferredHeight = size;
            le.minWidth = size;
            le.preferredWidth = size;
            le.flexibleWidth = 0f;
            var shadow = go.AddComponent<Shadow>();
            shadow.effectColor = new Color(0.2f, 0.1f, 0.15f, 0.16f);
            shadow.effectDistance = new Vector2(0f, -3f);

            var iconGo = new GameObject("Icon", typeof(Image));
            iconGo.transform.SetParent(go.transform, false);
            var iconImg = iconGo.GetComponent<Image>();
            iconImg.sprite = icon;
            iconImg.color = t.MidnightNavy;
            iconImg.raycastTarget = false;
            iconImg.preserveAspect = true;
            var irt = iconGo.GetComponent<RectTransform>();
            irt.anchorMin = new Vector2(0.5f, 0.5f);
            irt.anchorMax = new Vector2(0.5f, 0.5f);
            irt.sizeDelta = new Vector2(size * 0.55f, size * 0.55f);

            var btn = go.GetComponent<Button>();
            btn.targetGraphic = face;
            btn.onClick.AddListener(onClick);
            var motion = go.AddComponent<FrUiMotion>();
            HookPress(go, motion);
            return btn;
        }

        Button MakeCircleIconButton(Transform parent, string name, Sprite? icon, string fallbackGlyph,
            FashionRiseTheme t, UnityAction onClick, float size)
        {
            var go = new GameObject(name + "_Circle", typeof(Image), typeof(Button));
            go.transform.SetParent(parent, false);
            var face = go.GetComponent<Image>();
            face.sprite = FrUiSprites.Circle;
            face.color = new Color(1f, 1f, 1f, 0.9f);
            var shadow = go.AddComponent<Shadow>();
            shadow.effectColor = new Color(0.2f, 0.1f, 0.15f, 0.14f);
            shadow.effectDistance = new Vector2(0f, -3f);

            if (icon != null)
            {
                var iconGo = new GameObject("Icon", typeof(Image));
                iconGo.transform.SetParent(go.transform, false);
                var iconImg = iconGo.GetComponent<Image>();
                iconImg.sprite = icon;
                iconImg.color = t.MidnightNavy;
                iconImg.raycastTarget = false;
                var irt = iconGo.GetComponent<RectTransform>();
                irt.anchorMin = new Vector2(0.5f, 0.5f);
                irt.anchorMax = new Vector2(0.5f, 0.5f);
                irt.sizeDelta = new Vector2(size * 0.5f, size * 0.5f);
            }
            else
            {
                var txtGo = new GameObject("Glyph", typeof(Text));
                txtGo.transform.SetParent(go.transform, false);
                var txt = txtGo.GetComponent<Text>();
                txt.font = Resources.GetBuiltinResource<Font>("LegacyRuntime.ttf");
                txt.text = fallbackGlyph;
                txt.fontSize = 28;
                txt.fontStyle = FontStyle.Bold;
                txt.alignment = TextAnchor.MiddleCenter;
                txt.color = t.MidnightNavy;
                txt.raycastTarget = false;
                var trt = txtGo.GetComponent<RectTransform>();
                trt.anchorMin = Vector2.zero;
                trt.anchorMax = Vector2.one;
                trt.offsetMin = Vector2.zero;
                trt.offsetMax = Vector2.zero;
            }

            var btn = go.GetComponent<Button>();
            btn.targetGraphic = face;
            btn.onClick.AddListener(onClick);
            var motion = go.AddComponent<FrUiMotion>();
            HookPress(go, motion);
            var rt = go.GetComponent<RectTransform>();
            rt.sizeDelta = new Vector2(size, size);
            return btn;
        }

        Image MakeSizeChip(Transform parent, int index, float dotPx, FashionRiseTheme t, UnityAction onClick)
        {
            var go = new GameObject("Size" + index, typeof(Image), typeof(Button), typeof(LayoutElement));
            go.transform.SetParent(parent, false);
            var face = go.GetComponent<Image>();
            face.sprite = FrUiSprites.Circle;
            face.color = t.ButtonFace;
            var le = go.GetComponent<LayoutElement>();
            le.minHeight = 44f;
            le.preferredHeight = 44f;

            var dot = new GameObject("Dot", typeof(Image));
            dot.transform.SetParent(go.transform, false);
            var dotImg = dot.GetComponent<Image>();
            dotImg.sprite = FrUiSprites.Circle;
            dotImg.color = t.MidnightNavy;
            dotImg.raycastTarget = false;
            var drt = dot.GetComponent<RectTransform>();
            drt.anchorMin = new Vector2(0.5f, 0.5f);
            drt.anchorMax = new Vector2(0.5f, 0.5f);
            drt.sizeDelta = new Vector2(dotPx, dotPx);

            var btn = go.GetComponent<Button>();
            btn.targetGraphic = face;
            btn.onClick.AddListener(onClick);
            HookPress(go, go.AddComponent<FrUiMotion>());
            return face;
        }

        Image MakeColorDot(Transform parent, Color color, UnityAction onClick)
        {
            var go = new GameObject("ColorDot", typeof(Image), typeof(Button));
            go.transform.SetParent(parent, false);
            var ring = go.GetComponent<Image>();
            ring.sprite = FrUiSprites.Circle;
            ring.color = new Color(1f, 1f, 1f, 0.95f);

            var fill = new GameObject("Fill", typeof(Image));
            fill.transform.SetParent(go.transform, false);
            var fillImg = fill.GetComponent<Image>();
            fillImg.sprite = FrUiSprites.Circle;
            fillImg.color = color;
            fillImg.raycastTarget = false;
            var frt = fill.GetComponent<RectTransform>();
            frt.anchorMin = new Vector2(0.5f, 0.5f);
            frt.anchorMax = new Vector2(0.5f, 0.5f);
            frt.sizeDelta = new Vector2(28f, 28f);

            var btn = go.GetComponent<Button>();
            btn.targetGraphic = ring;
            btn.onClick.AddListener(onClick);
            HookPress(go, go.AddComponent<FrUiMotion>());
            return ring;
        }

        Image MakeFabricChip(Transform parent, string name, Color color, int seed, UnityAction onClick)
        {
            var go = new GameObject(name + "_Fabric", typeof(Image), typeof(Button), typeof(LayoutElement));
            go.transform.SetParent(parent, false);
            var face = go.GetComponent<Image>();
            face.sprite = FrUiSprites.FabricSwatch(color, 100 + seed);
            face.color = Color.white;
            var le = go.GetComponent<LayoutElement>();
            le.minHeight = 40f;
            le.preferredHeight = 40f;
            var shadow = go.AddComponent<Shadow>();
            shadow.effectColor = new Color(0.15f, 0.08f, 0.12f, 0.2f);
            shadow.effectDistance = new Vector2(0f, -2f);

            var txtGo = new GameObject("Name", typeof(Text));
            txtGo.transform.SetParent(go.transform, false);
            var txt = txtGo.GetComponent<Text>();
            txt.font = Resources.GetBuiltinResource<Font>("LegacyRuntime.ttf");
            txt.text = name;
            txt.fontSize = 12;
            txt.fontStyle = FontStyle.Bold;
            txt.alignment = TextAnchor.MiddleCenter;
            var lum = color.r * 0.3f + color.g * 0.59f + color.b * 0.11f;
            txt.color = lum < 0.45f ? Color.white : new Color(0.15f, 0.1f, 0.14f, 1f);
            txt.raycastTarget = false;
            var trt = txtGo.GetComponent<RectTransform>();
            trt.anchorMin = Vector2.zero;
            trt.anchorMax = Vector2.one;
            trt.offsetMin = Vector2.zero;
            trt.offsetMax = Vector2.zero;

            var btn = go.GetComponent<Button>();
            btn.targetGraphic = face;
            btn.onClick.AddListener(onClick);
            HookPress(go, go.AddComponent<FrUiMotion>());
            return face;
        }

        static void HookPress(GameObject go, FrUiMotion motion)
        {
            var trigger = go.GetComponent<EventTrigger>() ?? go.AddComponent<EventTrigger>();
            void Hook(EventTriggerType type, UnityAction<BaseEventData> cb)
            {
                var e = new EventTrigger.Entry { eventID = type };
                e.callback.AddListener(cb);
                trigger.triggers.Add(e);
            }

            Hook(EventTriggerType.PointerDown, _ => motion.SetPressed(true));
            Hook(EventTriggerType.PointerUp, _ => motion.SetPressed(false));
            Hook(EventTriggerType.PointerExit, _ => motion.SetPressed(false));
        }

        void SelectPencil()
        {
            _tool = DrawTool.Pencil;
            _pad.FillBucketActive = false;
            _pad.EraserActive = false;
            _pad.SetBrushColor(InkColors[_colorIndex]);
            _pad.SetBrushRadius(BrushSizes[_sizeIndex]);
            HighlightTool();
            FlashHint("Pencil — draw clothes");
        }

        void SelectEraser()
        {
            _tool = DrawTool.Eraser;
            _pad.FillBucketActive = false;
            _pad.EraserActive = true;
            HighlightTool();
            FlashHint("Eraser — rub to erase");
        }

        void SelectFill()
        {
            _tool = DrawTool.Fill;
            _pad.EraserActive = false;
            _pad.FillBucketActive = true;
            _pad.SetBrushColor(InkColors[_colorIndex]);
            HighlightTool();
            FlashHint("Fill — tap inside a closed shape");
        }

        void SetSize(int index)
        {
            _sizeIndex = Mathf.Clamp(index, 0, BrushSizes.Length - 1);
            if (_tool != DrawTool.Fill)
                _pad.SetBrushRadius(BrushSizes[_sizeIndex]);

            for (var i = 0; i < _sizeFaces.Length; i++)
            {
                if (_sizeFaces[i] == null)
                    continue;
                _sizeFaces[i].color = i == _sizeIndex
                    ? new Color(_theme.Accent.r, _theme.Accent.g, _theme.Accent.b, 0.35f)
                    : _theme.ButtonFace;
            }

            FlashHint(_sizeIndex == 0 ? "Thin pencil" : _sizeIndex == 1 ? "Medium brush" : "Bold brush");
        }

        void SetColor(int index)
        {
            _colorIndex = Mathf.Clamp(index, 0, InkColors.Length - 1);
            _pad.SetBrushColor(InkColors[_colorIndex]);
            if (_tool == DrawTool.Eraser)
                SelectPencil();
            else if (_tool == DrawTool.Fill)
            {
                _pad.FillBucketActive = true;
                _pad.EraserActive = false;
            }
            else
            {
                _pad.EraserActive = false;
                _pad.FillBucketActive = false;
                _pad.SetBrushRadius(BrushSizes[_sizeIndex]);
            }

            var bound = _fabricForColor[_colorIndex];
            if (!string.IsNullOrEmpty(bound))
            {
                for (var i = 0; i < Fabrics.Length; i++)
                {
                    if (!string.Equals(Fabrics[i].name, bound, System.StringComparison.OrdinalIgnoreCase))
                        continue;
                    _fabricIndex = i;
                    break;
                }
            }

            HighlightTool();
            for (var i = 0; i < _colorRings.Length; i++)
            {
                if (_colorRings[i] == null)
                    continue;
                _colorRings[i].color = i == _colorIndex
                    ? _theme.Accent
                    : new Color(1f, 1f, 1f, 0.95f);
                _colorRings[i].transform.localScale = i == _colorIndex ? Vector3.one * 1.12f : Vector3.one;
            }

            RefreshPairHint();
            FlashHint(string.IsNullOrEmpty(bound)
                ? ColorNames[_colorIndex] + " — pick a fabric"
                : ColorNames[_colorIndex] + " → " + bound);
            PersistMaterialSession();
        }

        void SelectFabric(int index)
        {
            _fabricIndex = Mathf.Clamp(index, 0, Fabrics.Length - 1);
            // Pair fabric with the active ink color (keep painting THAT color)
            _fabricForColor[_colorIndex] = Fabrics[_fabricIndex].name;
            _pad.SetBrushColor(InkColors[_colorIndex]);
            if (_tool == DrawTool.Fill)
            {
                _pad.FillBucketActive = true;
                _pad.EraserActive = false;
            }
            else
            {
                _tool = DrawTool.Pencil;
                _pad.EraserActive = false;
                _pad.FillBucketActive = false;
                _pad.SetBrushRadius(BrushSizes[_sizeIndex]);
            }

            HighlightTool();
            ClearFabricSelection();
            if (_fabricFaces[_fabricIndex] != null)
                _fabricFaces[_fabricIndex].transform.localScale = Vector3.one * 1.06f;
            RefreshPairHint();
            FlashHint(ColorNames[_colorIndex] + " → " + Fabrics[_fabricIndex].name);
            PersistMaterialSession();
        }

        void ApplyFabricBrush(int index)
        {
            // Kept for compatibility — fabric no longer recolors the brush (pairs with ink color).
            _fabricIndex = Mathf.Clamp(index, 0, Fabrics.Length - 1);
        }

        void ClearFabricSelection()
        {
            for (var i = 0; i < _fabricFaces.Length; i++)
            {
                if (_fabricFaces[i] != null)
                    _fabricFaces[i].transform.localScale = Vector3.one;
            }
        }

        void HighlightTool()
        {
            void Style(Image? face, bool on)
            {
                if (face == null)
                    return;
                face.color = on ? _theme.Accent : _theme.ButtonFace;
                var icon = face.transform.Find("Icon")?.GetComponent<Image>();
                if (icon != null)
                    icon.color = on ? Color.white : _theme.MidnightNavy;
            }

            Style(_pencilFace, _tool == DrawTool.Pencil);
            Style(_eraserFace, _tool == DrawTool.Eraser);
            Style(_fillFace, _tool == DrawTool.Fill);
            if (_tool == DrawTool.Eraser && _eraserFace != null)
                _eraserFace.color = new Color(1f, 0.82f, 0.88f, 1f);
        }

        void RefreshPairHint()
        {
            if (_pairHint == null)
                return;
            var pairs = BuildMaterialPairs();
            _pairHint.text = string.IsNullOrEmpty(pairs)
                ? "Tap color, then fabric"
                : pairs.Replace(';', '\n');
        }

        string BuildMaterialPairs()
        {
            var parts = new List<string>();
            for (var i = 0; i < _fabricForColor.Length; i++)
            {
                var f = _fabricForColor[i];
                if (string.IsNullOrEmpty(f))
                    continue;
                parts.Add(ColorNames[i] + ":" + f);
            }

            return string.Join(";", parts);
        }

        void PersistMaterialSession()
        {
            if (App == null)
                return;
            App.CreateDesign.SketchColorName = ColorNames[_colorIndex];
            if (_fabricIndex >= 0)
            {
                App.CreateDesign.SketchFabricName = Fabrics[_fabricIndex].name;
                App.CreateDesign.MaterialId = Fabrics[_fabricIndex].name.ToLowerInvariant();
            }

            App.CreateDesign.SketchMaterialPairs = BuildMaterialPairs();
        }

        void RestoreMaterialPairsFromSession()
        {
            var raw = App?.CreateDesign.SketchMaterialPairs?.Trim() ?? "";
            if (string.IsNullOrEmpty(raw))
                return;
            foreach (var part in raw.Split(';'))
            {
                var bits = part.Split(':');
                if (bits.Length != 2)
                    continue;
                var colorName = bits[0].Trim();
                var fabricName = bits[1].Trim();
                var ci = System.Array.FindIndex(ColorNames,
                    n => string.Equals(n, colorName, System.StringComparison.OrdinalIgnoreCase));
                if (ci < 0)
                    continue;
                _fabricForColor[ci] = fabricName;
            }

            RefreshPairHint();
        }

        void CyclePose()
        {
            var next = (SketchFigurePreferences.DefaultPoseIndex + 1) % SketchFigurePreferences.PoseCount;
            SketchFigurePreferences.DefaultPoseIndex = next;
            var who = SketchFigurePreferences.DefaultTemplate == SketchFigureTemplate.Male ? "Boy" : "Girl";
            ApplyCurrentFigure($"{who} · {SketchFigurePreferences.PoseLabel(next)}");
        }

        void FlashHint(string msg)
        {
            if (_hint != null)
                _hint.text = msg;
        }

        void ApplyCurrentFigure(string hint)
        {
            _pad.ApplyDefaultFigure(SketchFigurePreferences.DefaultTemplate,
                SketchFigurePreferences.DefaultPoseIndex);
            FlashHint(hint);
        }

        void ToggleReferenceDim()
        {
            _refDimmed = !_refDimmed;
            _pad.ReferenceStrength = _refDimmed ? 0.4f : 1f;
            _pad.RefreshComposite();
            FlashHint(_refDimmed ? "Model faded" : "Model bright");
        }

        void BootstrapPadReference(SketchFigureTemplate? forcedFigure)
        {
            if (App == null)
                return;

            if (forcedFigure.HasValue)
                SketchFigurePreferences.DefaultTemplate = forcedFigure.Value;

            var pending = App.CreateDesign.PendingReferenceImagePath?.Trim();
            if (!string.IsNullOrEmpty(pending) && File.Exists(pending))
            {
                App.CreateDesign.PendingReferenceImagePath = "";
                if (_pad.TryLoadUnderlayFromFile(pending, out var err))
                    FlashHint("Photo ready — draw!");
                else
                {
                    FlashHint(string.IsNullOrEmpty(err) ? "Using default model" : err);
                    ApplyCurrentFigure(_hint.text);
                }
            }
            else
            {
                var who = SketchFigurePreferences.DefaultTemplate == SketchFigureTemplate.Male ? "Boy" : "Girl";
                ApplyCurrentFigure($"{who} — draw your look!");
            }
        }

        protected override void OnShown(object? payload)
        {
            if (App == null)
                return;

            SketchFigureTemplate? forced = null;
            var restore = false;
            if (payload is SketchNavContext ctx)
            {
                if (ctx.Figure.HasValue)
                    forced = ctx.Figure;
                restore = ctx.RestoreSketch;
            }
            else if (payload is SketchFigureTemplate fig)
                forced = fig;

            RestoreMaterialPairsFromSession();

            if (!_padBootstrapped)
            {
                _padBootstrapped = true;
                BootstrapPadReference(forced);
                if (restore)
                    TryRestoreInkLayer();
                return;
            }

            if (restore)
            {
                TryRestoreInkLayer();
                FlashHint("Edit your sketch — then MAGIC!");
                return;
            }

            if (forced.HasValue)
            {
                SketchFigurePreferences.DefaultTemplate = forced.Value;
                var who = forced.Value == SketchFigureTemplate.Male ? "Boy" : "Girl";
                ApplyCurrentFigure($"{who} — draw your look!");
            }

            var pending = App.CreateDesign.PendingReferenceImagePath?.Trim();
            if (string.IsNullOrEmpty(pending))
                return;

            App.CreateDesign.PendingReferenceImagePath = "";
            if (!File.Exists(pending))
            {
                FlashHint("Photo missing");
                return;
            }

            if (_pad.TryLoadUnderlayFromFile(pending, out var err))
                FlashHint("Photo ready — draw!");
            else
                FlashHint(string.IsNullOrEmpty(err) ? "Could not load photo" : err);
        }

        void TryRestoreInkLayer()
        {
            var ink = App.CreateDesign.LastInkImagePath?.Trim() ?? "";
            if (string.IsNullOrEmpty(ink))
            {
                // Fall back: keep whatever is on the pad if still in memory
                if (_pad.HasInk())
                    FlashHint("Your sketch is still here");
                return;
            }

            if (_pad.TryLoadInkFromFile(ink, out var err))
                FlashHint("Sketch restored — edit away!");
            else
                FlashHint(string.IsNullOrEmpty(err) ? "Could not restore sketch" : err);
        }

        void ContinueToEnhancement()
        {
            if (!_pad.HasInk())
            {
                FlashHint("Draw a little first!");
                return;
            }

            PersistMaterialSession();
            var path = _pad.SavePngToPersistentData("canvas");
            App.CreateDesign.SketchReference = "file:" + path.Replace('\\', '/');
            try
            {
                var inkPath = _pad.SaveInkPngToPersistentData("ink");
                App.CreateDesign.LastInkImagePath = inkPath;
            }
            catch (System.Exception ex)
            {
                Debug.LogWarning($"FashionRise could not save ink layer: {ex.Message}");
            }

            FlashHint("Magic…");
            if (App.Navigation != null)
                _ = App.Navigation.NavigateToAsync(ScreenId.SketchEnhancement,
                    new SketchNavContext { AutoMagic = true });
        }
    }
}
