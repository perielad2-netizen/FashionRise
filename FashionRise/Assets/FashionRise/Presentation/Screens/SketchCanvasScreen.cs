using System;
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
        Image? _brushFace;
        Image? _eraserFace;
        Image? _fillFace;
        Image? _colorPreview;
        RawImage? _svRaw;
        Texture2D? _svTex;
        Text? _sizeLabel;
        Slider? _sizeSlider;
        readonly Image[] _fabricFaces = new Image[6];
        readonly string?[] _fabricForColor = new string[8];
        Text? _pairHint;
        int _colorIndex;
        int _fabricIndex = -1;
        float _hue = 0.08f;
        float _sat = 0.85f;
        float _val = 0.95f;
        enum DrawTool { Pencil, Brush, Eraser, Fill }
        DrawTool _tool = DrawTool.Pencil;

        // Quick-bind named colors for fabric pairing (nearest match when picking from palette)
        static readonly Color[] InkColors =
        {
            new(0.10f, 0.08f, 0.08f),
            new(0.86f, 0.18f, 0.36f),
            new(0.18f, 0.42f, 0.82f),
            new(0.96f, 0.48f, 0.12f),
            new(0.18f, 0.62f, 0.32f),
            new(0.78f, 0.40f, 0.72f),
            new(0.97f, 0.94f, 0.90f),
            new(0.48f, 0.48f, 0.52f),
        };

        static readonly string[] ColorNames =
        {
            "Ink", "Rose", "Blue", "Orange", "Green", "Orchid", "Cream", "Grey"
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
            SetBrushSize(6);
            ApplyHsvColor(notify: false);
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

            // Hint is a quiet caption, not a filled pill — chrome stays out of the canvas' way.
            var hintWrap = new GameObject("HintWrap", typeof(RectTransform), typeof(LayoutElement));
            hintWrap.transform.SetParent(top.transform, false);
            var hintLe = hintWrap.GetComponent<LayoutElement>();
            hintLe.flexibleWidth = 1f;
            hintLe.minHeight = 44f;
            hintLe.preferredHeight = 44f;
            _hint = FrUiFactory.AddLabel(hintWrap.transform, "Hint", "Draw your look", t,
                Mathf.RoundToInt(t.CaptionSize), FontStyle.Normal, TextAnchor.MiddleCenter,
                useSecondaryTextColor: true);
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
            face.color = t.ButtonAiFace;
            var shadow = go.AddComponent<Shadow>();
            shadow.effectColor = new Color(0.08f, 0.07f, 0.06f, 0.22f);
            shadow.effectDistance = new Vector2(0f, -5f);
            var outline = go.AddComponent<Outline>();
            outline.effectColor = new Color(t.Champagne.r, t.Champagne.g, t.Champagne.b, 0.5f);
            outline.effectDistance = new Vector2(1.5f, -1.5f);

            var icon = new GameObject("Spark", typeof(Image));
            icon.transform.SetParent(go.transform, false);
            var iconImg = icon.GetComponent<Image>();
            iconImg.sprite = FrUiSprites.IconSparkle;
            iconImg.color = t.Champagne;
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
            txt.font = FrUiFonts.UiMedium;
            txt.text = "Magic";
            txt.fontSize = 18;
            txt.fontStyle = FontStyle.Normal;
            txt.alignment = TextAnchor.MiddleCenter;
            txt.color = t.Champagne;
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
            studioRt.offsetMin = new Vector2(0f, 2f);
            studioRt.offsetMax = new Vector2(0f, -64f);

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
            var rail = MakeFloatingRail(studio, "LeftTools", true, 72f, t);
            AddSectionLabel(rail, "TOOLS", t);

            _pencilFace = MakeIconTool(rail, "Pencil", FrUiSprites.IconPencil, t, SelectPencil, 50f)
                .GetComponent<Image>();
            _brushFace = MakeIconTool(rail, "Brush", FrUiSprites.IconBrush, t, SelectBrush, 50f)
                .GetComponent<Image>();
            _eraserFace = MakeIconTool(rail, "Eraser", FrUiSprites.IconEraser, t, SelectEraser, 50f)
                .GetComponent<Image>();
            _fillFace = MakeIconTool(rail, "Fill", FrUiSprites.IconFill, t, SelectFill, 50f)
                .GetComponent<Image>();

            AddSectionLabel(rail, "SIZE", t);
            _sizeLabel = FrUiFactory.AddLabel(rail, "SizeVal", "6", t, 12, FontStyle.Bold,
                TextAnchor.MiddleCenter, useSecondaryTextColor: true);
            var sizeLe = _sizeLabel.GetComponent<LayoutElement>() ?? _sizeLabel.gameObject.AddComponent<LayoutElement>();
            sizeLe.minHeight = 16f;
            sizeLe.preferredHeight = 18f;

            BuildSizeSlider(rail, t);

            AddSectionLabel(rail, "EDIT", t);
            MakeIconTool(rail, "Undo", FrUiSprites.IconUndo, t, () =>
            {
                if (!_pad.UndoStroke())
                    FlashHint("Nothing to undo");
                else
                    FlashHint("Undone");
            }, 46f);
            MakeIconTool(rail, "Clear", FrUiSprites.IconClear, t, () =>
            {
                _pad.ClearAll();
                FlashHint("Fresh page");
            }, 46f);
            MakeIconTool(rail, "Fade", FrUiSprites.IconFade, t, ToggleReferenceDim, 46f);
        }

        void BuildSizeSlider(Transform rail, FashionRiseTheme t)
        {
            var host = new GameObject("SizeSlider", typeof(RectTransform), typeof(Slider), typeof(LayoutElement));
            host.transform.SetParent(rail, false);
            var hostLe = host.GetComponent<LayoutElement>();
            hostLe.minHeight = 132f;
            hostLe.preferredHeight = 140f;
            hostLe.flexibleWidth = 1f;

            var bg = new GameObject("Background", typeof(Image));
            bg.transform.SetParent(host.transform, false);
            var bgImg = bg.GetComponent<Image>();
            bgImg.sprite = FrUiSprites.RoundPill;
            bgImg.type = Image.Type.Sliced;
            bgImg.color = new Color(t.AccentMuted.r, t.AccentMuted.g, t.AccentMuted.b, 0.5f);
            var bgRt = bg.GetComponent<RectTransform>();
            bgRt.anchorMin = new Vector2(0.5f, 0.05f);
            bgRt.anchorMax = new Vector2(0.5f, 0.95f);
            bgRt.sizeDelta = new Vector2(12f, 0f);

            var fillArea = new GameObject("Fill Area", typeof(RectTransform));
            fillArea.transform.SetParent(host.transform, false);
            var fillAreaRt = fillArea.GetComponent<RectTransform>();
            fillAreaRt.anchorMin = new Vector2(0.5f, 0.05f);
            fillAreaRt.anchorMax = new Vector2(0.5f, 0.95f);
            fillAreaRt.sizeDelta = new Vector2(12f, 0f);

            var fill = new GameObject("Fill", typeof(Image));
            fill.transform.SetParent(fillArea.transform, false);
            var fillImg = fill.GetComponent<Image>();
            fillImg.sprite = FrUiSprites.RoundPill;
            fillImg.type = Image.Type.Sliced;
            fillImg.color = t.Accent;
            var fillRt = fill.GetComponent<RectTransform>();
            fillRt.anchorMin = Vector2.zero;
            fillRt.anchorMax = Vector2.one;
            fillRt.offsetMin = Vector2.zero;
            fillRt.offsetMax = Vector2.zero;

            var handleArea = new GameObject("Handle Slide Area", typeof(RectTransform));
            handleArea.transform.SetParent(host.transform, false);
            var handleAreaRt = handleArea.GetComponent<RectTransform>();
            handleAreaRt.anchorMin = new Vector2(0.5f, 0.05f);
            handleAreaRt.anchorMax = new Vector2(0.5f, 0.95f);
            handleAreaRt.sizeDelta = new Vector2(28f, 0f);

            var handle = new GameObject("Handle", typeof(Image));
            handle.transform.SetParent(handleArea.transform, false);
            var handleImg = handle.GetComponent<Image>();
            handleImg.sprite = FrUiSprites.Circle;
            handleImg.color = Color.white;
            var handleRt = handle.GetComponent<RectTransform>();
            handleRt.sizeDelta = new Vector2(26f, 26f);

            var slider = host.GetComponent<Slider>();
            slider.direction = Slider.Direction.BottomToTop;
            slider.minValue = 1f;
            slider.maxValue = 50f;
            slider.wholeNumbers = true;
            slider.value = 6f;
            slider.targetGraphic = handleImg;
            slider.fillRect = fillRt;
            slider.handleRect = handleRt;
            slider.onValueChanged.AddListener(v => SetBrushSize(Mathf.RoundToInt(v)));
            _sizeSlider = slider;
        }

        void BuildRightPalette(RectTransform studio, FashionRiseTheme t)
        {
            var rail = MakeFloatingRail(studio, "RightPalette", false, 118f, t);

            AddSectionLabel(rail, "COLOR", t);
            BuildColorPalette(rail, t);

            AddSectionLabel(rail, "FABRIC", t);
            for (var i = 0; i < Fabrics.Length; i++)
            {
                var idx = i;
                _fabricFaces[i] = MakeFabricChip(rail, Fabrics[i].name, Fabrics[i].color, idx,
                    () => SelectFabric(idx));
            }

            _pairHint = FrUiFactory.AddLabel(rail, "Pairs", "Pick color → fabric", t, 10, FontStyle.Normal,
                TextAnchor.MiddleCenter, useSecondaryTextColor: true);
            var pairLe = _pairHint.GetComponent<LayoutElement>() ?? _pairHint.gameObject.AddComponent<LayoutElement>();
            pairLe.minHeight = 32f;
            pairLe.preferredHeight = 40f;

            AddSectionLabel(rail, "FIGURE", t);
            MakeIconTool(rail, "Women", FrUiSprites.IconGirl, t, () =>
            {
                SketchFigurePreferences.DefaultTemplate = SketchFigureTemplate.Female;
                ApplyCurrentFigure("Women · " + SketchFigurePreferences.PoseLabel(SketchFigurePreferences.DefaultPoseIndex));
            }, 46f);
            MakeIconTool(rail, "Men", FrUiSprites.IconBoy, t, () =>
            {
                SketchFigurePreferences.DefaultTemplate = SketchFigureTemplate.Male;
                ApplyCurrentFigure("Men · " + SketchFigurePreferences.PoseLabel(SketchFigurePreferences.DefaultPoseIndex));
            }, 46f);
            MakeIconTool(rail, "Photo", FrUiSprites.IconPhoto, t, () =>
            {
                if (App.Navigation != null)
                    _ = App.Navigation.NavigateToAsync(ScreenId.ImportSketch);
            }, 46f);
            MakeIconTool(rail, "Pose", FrUiSprites.IconPose, t, CyclePose, 46f);
        }

        void BuildColorPalette(Transform rail, FashionRiseTheme t)
        {
            var host = new GameObject("Palette", typeof(RectTransform), typeof(LayoutElement));
            host.transform.SetParent(rail, false);
            var hostLe = host.GetComponent<LayoutElement>();
            hostLe.minHeight = 150f;
            hostLe.preferredHeight = 156f;
            hostLe.flexibleWidth = 1f;

            // Current color chip
            var previewGo = new GameObject("Current", typeof(Image));
            previewGo.transform.SetParent(host.transform, false);
            _colorPreview = previewGo.GetComponent<Image>();
            _colorPreview.sprite = FrUiSprites.Circle;
            _colorPreview.color = Color.HSVToRGB(_hue, _sat, _val);
            var previewRt = previewGo.GetComponent<RectTransform>();
            previewRt.anchorMin = new Vector2(0.5f, 1f);
            previewRt.anchorMax = new Vector2(0.5f, 1f);
            previewRt.pivot = new Vector2(0.5f, 1f);
            previewRt.anchoredPosition = new Vector2(0f, -2f);
            previewRt.sizeDelta = new Vector2(28f, 28f);

            // SV square
            var svGo = new GameObject("SV", typeof(RawImage));
            svGo.transform.SetParent(host.transform, false);
            _svRaw = svGo.GetComponent<RawImage>();
            _svTex = FrUiSprites.BuildSvTexture(_hue, 96);
            _svRaw.texture = _svTex;
            _svRaw.color = Color.white;
            var svRt = svGo.GetComponent<RectTransform>();
            svRt.anchorMin = new Vector2(0f, 0f);
            svRt.anchorMax = new Vector2(1f, 1f);
            svRt.offsetMin = new Vector2(4f, 4f);
            svRt.offsetMax = new Vector2(-22f, -34f);
            WirePalettePointer(svGo, OnSvPointer);

            // Hue strip
            var hueGo = new GameObject("Hue", typeof(Image));
            hueGo.transform.SetParent(host.transform, false);
            var hueImg = hueGo.GetComponent<Image>();
            hueImg.sprite = FrUiSprites.HueStrip;
            hueImg.type = Image.Type.Simple;
            hueImg.color = Color.white;
            var hueRt = hueGo.GetComponent<RectTransform>();
            hueRt.anchorMin = new Vector2(1f, 0f);
            hueRt.anchorMax = new Vector2(1f, 1f);
            hueRt.pivot = new Vector2(1f, 0.5f);
            hueRt.anchoredPosition = new Vector2(-4f, -8f);
            hueRt.sizeDelta = new Vector2(14f, -40f);
            WirePalettePointer(hueGo, OnHuePointer);

            // Quick swatches row under preview
            var quick = new GameObject("Quick", typeof(RectTransform), typeof(HorizontalLayoutGroup));
            quick.transform.SetParent(host.transform, false);
            var qRt = quick.GetComponent<RectTransform>();
            qRt.anchorMin = new Vector2(0f, 1f);
            qRt.anchorMax = new Vector2(1f, 1f);
            qRt.pivot = new Vector2(0.5f, 1f);
            qRt.anchoredPosition = new Vector2(0f, -32f);
            qRt.sizeDelta = new Vector2(0f, 16f);
            var qH = quick.GetComponent<HorizontalLayoutGroup>();
            qH.spacing = 3f;
            qH.childAlignment = TextAnchor.MiddleCenter;
            qH.childControlWidth = true;
            qH.childForceExpandWidth = true;
            qH.childControlHeight = true;
            qH.childForceExpandHeight = true;
            qH.padding = new RectOffset(2, 18, 0, 0);
            for (var i = 0; i < InkColors.Length; i++)
            {
                var idx = i;
                var sw = new GameObject(ColorNames[i], typeof(Image), typeof(Button));
                sw.transform.SetParent(quick.transform, false);
                var img = sw.GetComponent<Image>();
                img.sprite = FrUiSprites.Circle;
                img.color = InkColors[i];
                var btn = sw.GetComponent<Button>();
                btn.targetGraphic = img;
                btn.onClick.AddListener(() => ApplyNamedColor(idx));
            }
        }

        void WirePalettePointer(GameObject go, System.Action<Vector2, RectTransform> onDrag)
        {
            var trigger = go.AddComponent<EventTrigger>();
            void Hook(EventTriggerType type)
            {
                var e = new EventTrigger.Entry { eventID = type };
                e.callback.AddListener(data =>
                {
                    if (data is PointerEventData ped &&
                        RectTransformUtility.ScreenPointToLocalPointInRectangle(
                            go.GetComponent<RectTransform>(), ped.position, ped.pressEventCamera, out var local))
                        onDrag(local, go.GetComponent<RectTransform>());
                });
                trigger.triggers.Add(e);
            }

            Hook(EventTriggerType.PointerDown);
            Hook(EventTriggerType.Drag);
        }

        void OnHuePointer(Vector2 local, RectTransform rt)
        {
            var h = rt.rect.height;
            if (h < 1f)
                return;
            var t = Mathf.Clamp01((local.y - rt.rect.yMin) / h);
            _hue = 1f - t;
            RebuildSvTexture();
            ApplyHsvColor();
        }

        void OnSvPointer(Vector2 local, RectTransform rt)
        {
            var w = rt.rect.width;
            var h = rt.rect.height;
            if (w < 1f || h < 1f)
                return;
            _sat = Mathf.Clamp01((local.x - rt.rect.xMin) / w);
            _val = Mathf.Clamp01((local.y - rt.rect.yMin) / h);
            ApplyHsvColor();
        }

        void RebuildSvTexture()
        {
            if (_svRaw == null)
                return;
            if (_svTex != null)
                Destroy(_svTex);
            _svTex = FrUiSprites.BuildSvTexture(_hue, 96);
            _svRaw.texture = _svTex;
        }

        void ApplyHsvColor(bool notify = true)
        {
            var c = Color.HSVToRGB(_hue, _sat, _val);
            if (_colorPreview != null)
                _colorPreview.color = c;
            _pad.SetBrushColor(c);
            _colorIndex = NearestNamedColor(c);
            if (notify)
            {
                FlashHint(ColorNames[_colorIndex] + " ready");
                PersistMaterialSession();
                RefreshPairHint();
            }
        }

        void ApplyNamedColor(int index)
        {
            _colorIndex = Mathf.Clamp(index, 0, InkColors.Length - 1);
            var c = InkColors[_colorIndex];
            Color.RGBToHSV(c, out _hue, out _sat, out _val);
            RebuildSvTexture();
            ApplyHsvColor();
            var bound = _fabricForColor[_colorIndex];
            FlashHint(string.IsNullOrEmpty(bound)
                ? ColorNames[_colorIndex] + " — pick a fabric"
                : ColorNames[_colorIndex] + " → " + bound);
        }

        static int NearestNamedColor(Color c)
        {
            var best = 0;
            var bestD = float.MaxValue;
            for (var i = 0; i < InkColors.Length; i++)
            {
                var o = InkColors[i];
                var d = (c.r - o.r) * (c.r - o.r) + (c.g - o.g) * (c.g - o.g) + (c.b - o.b) * (c.b - o.b);
                if (d >= bestD)
                    continue;
                bestD = d;
                best = i;
            }

            return best;
        }

        static Transform MakeFloatingRail(RectTransform parent, string name, bool left, float width,
            FashionRiseTheme t)
        {
            var shell = new GameObject(name, typeof(RectTransform), typeof(Image));
            shell.transform.SetParent(parent, false);
            var rt = shell.GetComponent<RectTransform>();
            if (left)
            {
                rt.anchorMin = new Vector2(0f, 0.01f);
                rt.anchorMax = new Vector2(0f, 0.99f);
                rt.pivot = new Vector2(0f, 0.5f);
                rt.sizeDelta = new Vector2(width, 0f);
                rt.anchoredPosition = new Vector2(4f, 0f);
            }
            else
            {
                rt.anchorMin = new Vector2(1f, 0.01f);
                rt.anchorMax = new Vector2(1f, 0.99f);
                rt.pivot = new Vector2(1f, 0.5f);
                rt.sizeDelta = new Vector2(width, 0f);
                rt.anchoredPosition = new Vector2(-4f, 0f);
            }

            var face = shell.GetComponent<Image>();
            face.sprite = FrUiSprites.RoundSoft;
            face.type = Image.Type.Sliced;
            face.color = new Color(1f, 1f, 1f, 0.94f);
            var shadow = shell.AddComponent<Shadow>();
            shadow.effectColor = new Color(0.08f, 0.07f, 0.06f, 0.14f);
            shadow.effectDistance = new Vector2(left ? 4f : -4f, -5f);
            var railEdge = shell.AddComponent<Outline>();
            railEdge.effectColor = t.Hairline;
            railEdge.effectDistance = new Vector2(1f, -1f);

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

        /// <summary>Hairline divider — pro drawing apps separate tool groups with rules, not words.</summary>
        static void AddSectionLabel(Transform parent, string text, FashionRiseTheme t)
        {
            var go = new GameObject("Divider_" + text, typeof(RectTransform), typeof(Image), typeof(LayoutElement));
            go.transform.SetParent(parent, false);
            var img = go.GetComponent<Image>();
            img.color = t.Hairline;
            img.raycastTarget = false;
            var le = go.GetComponent<LayoutElement>();
            le.minHeight = 1f;
            le.preferredHeight = 1f;
            le.flexibleWidth = 1f;
        }

        Button MakeIconTool(Transform parent, string name, Sprite icon, FashionRiseTheme t, UnityAction onClick,
            float size)
        {
            var go = new GameObject(name + "_Tool", typeof(Image), typeof(Button), typeof(LayoutElement));
            go.transform.SetParent(parent, false);
            var face = go.GetComponent<Image>();
            face.sprite = FrUiSprites.RoundSoft;
            face.type = Image.Type.Sliced;
            face.color = new Color(1f, 1f, 1f, 0f);
            var le = go.GetComponent<LayoutElement>();
            le.minHeight = size;
            le.preferredHeight = size;
            le.minWidth = size;
            le.preferredWidth = size;
            le.flexibleWidth = 0f;

            var iconGo = new GameObject("Icon", typeof(Image));
            iconGo.transform.SetParent(go.transform, false);
            var iconImg = iconGo.GetComponent<Image>();
            iconImg.sprite = icon;
            // Art-supply icons carry their own colour; flat glyphs get inked.
            iconImg.color = Color.white;
            iconImg.raycastTarget = false;
            iconImg.preserveAspect = true;
            var irt = iconGo.GetComponent<RectTransform>();
            irt.anchorMin = new Vector2(0.5f, 0.5f);
            irt.anchorMax = new Vector2(0.5f, 0.5f);
            irt.sizeDelta = new Vector2(size * 0.86f, size * 0.86f);

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
            _pad.SetBrushSoftness(0.78f);
            _pad.SetBrushOpacity(0.55f);
            ApplyHsvColor(notify: false);
            HighlightTool();
            FlashHint("Pencil — sketch folds & shading");
        }

        void SelectBrush()
        {
            _tool = DrawTool.Brush;
            _pad.FillBucketActive = false;
            _pad.EraserActive = false;
            _pad.SetBrushSoftness(0f);
            _pad.SetBrushOpacity(1f);
            ApplyHsvColor(notify: false);
            HighlightTool();
            FlashHint("Brush — bold color strokes");
        }

        void SelectEraser()
        {
            _tool = DrawTool.Eraser;
            _pad.FillBucketActive = false;
            _pad.EraserActive = true;
            _pad.SetBrushSoftness(0.35f);
            _pad.SetBrushOpacity(1f);
            HighlightTool();
            FlashHint("Eraser");
        }

        void SelectFill()
        {
            _tool = DrawTool.Fill;
            _pad.EraserActive = false;
            _pad.FillBucketActive = true;
            _pad.SetBrushSoftness(0f);
            _pad.SetBrushOpacity(1f);
            ApplyHsvColor(notify: false);
            HighlightTool();
            FlashHint("Fill — tap inside a closed shape");
        }

        void SetBrushSize(int size)
        {
            size = Mathf.Clamp(size, 1, 50);
            _pad.SetBrushRadius(size);
            if (_sizeLabel != null)
                _sizeLabel.text = size.ToString();
            if (_sizeSlider != null && Mathf.Abs(_sizeSlider.value - size) > 0.01f)
                _sizeSlider.SetValueWithoutNotify(size);
        }

        void SelectFabric(int index)
        {
            _fabricIndex = Mathf.Clamp(index, 0, Fabrics.Length - 1);
            _fabricForColor[_colorIndex] = Fabrics[_fabricIndex].name;
            ApplyHsvColor(notify: false);
            if (_tool == DrawTool.Fill)
            {
                _pad.FillBucketActive = true;
                _pad.EraserActive = false;
            }
            else if (_tool == DrawTool.Eraser)
                SelectPencil();
            else if (_tool == DrawTool.Brush)
                SelectBrush();
            else
                SelectPencil();

            ClearFabricSelection();
            if (_fabricFaces[_fabricIndex] != null)
                _fabricFaces[_fabricIndex].transform.localScale = Vector3.one * 1.06f;
            RefreshPairHint();
            FlashHint(ColorNames[_colorIndex] + " → " + Fabrics[_fabricIndex].name);
            PersistMaterialSession();
        }

        void ApplyFabricBrush(int index)
        {
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
            // Selected tool gets a soft tray behind the art supply + a nudge forward, like pro drawing rails.
            void Style(Image? face, bool on)
            {
                if (face == null)
                    return;
                face.color = on
                    ? new Color(_theme.Champagne.r, _theme.Champagne.g, _theme.Champagne.b, 0.32f)
                    : new Color(1f, 1f, 1f, 0f);
                var motion = face.GetComponent<FrUiMotion>();
                if (motion != null)
                    motion.SetSelected(on);
            }

            Style(_pencilFace, _tool == DrawTool.Pencil);
            Style(_brushFace, _tool == DrawTool.Brush);
            Style(_eraserFace, _tool == DrawTool.Eraser);
            Style(_fillFace, _tool == DrawTool.Fill);
        }

        void RefreshPairHint()
        {
            if (_pairHint == null)
                return;
            var pairs = BuildMaterialPairs();
            _pairHint.text = string.IsNullOrEmpty(pairs)
                ? "Tap color, then fabric"
                : FormatPairsForHint(pairs);
        }

        static string FormatPairsForHint(string pairs)
        {
            var lines = new List<string>();
            foreach (var part in pairs.Split(';'))
            {
                var bits = part.Split(':');
                if (bits.Length < 2)
                    continue;
                lines.Add(bits[0].Trim() + " → " + bits[1].Trim());
            }

            return lines.Count == 0 ? "Tap color, then fabric" : string.Join("\n", lines);
        }

        string BuildMaterialPairs()
        {
            var painted = PaintedRegionHexes();
            var parts = new List<string>();
            for (var i = 0; i < _fabricForColor.Length; i++)
            {
                var f = _fabricForColor[i];
                if (string.IsNullOrEmpty(f))
                    continue;
                // Color:Fabric:#RRGGBB — Magic matches ink by name and approximate RGB
                var c = InkColors[i];
                var hex = $"#{Mathf.RoundToInt(c.r * 255):X2}{Mathf.RoundToInt(c.g * 255):X2}{Mathf.RoundToInt(c.b * 255):X2}";
                // Leftover chips (tapped orange, never painted) used to leak into Magic.
                if (painted.Count > 0)
                {
                    if (!MatchesPaintedHex(hex, painted))
                        continue;
                }
                else if (i != _colorIndex)
                {
                    continue;
                }

                parts.Add(ColorNames[i] + ":" + f + ":" + hex);
            }

            return string.Join(";", parts);
        }

        List<string> PaintedRegionHexes()
        {
            var regions = _pad != null
                ? _pad.DescribeColorRegions()
                : App?.CreateDesign.SketchColorRegions ?? "";
            var hexes = new List<string>();
            if (string.IsNullOrWhiteSpace(regions))
                return hexes;
            foreach (var part in regions.Split(';'))
            {
                var bits = part.Split(',');
                if (bits.Length < 3)
                    continue;
                var hex = bits[0].Trim();
                if (hex.Length > 0)
                    hexes.Add(hex);
            }

            return hexes;
        }

        static bool MatchesPaintedHex(string chipHex, List<string> painted, int tol = 90)
        {
            foreach (var paintedHex in painted)
            {
                if (HexManhattan(chipHex, paintedHex) <= tol)
                    return true;
            }

            return false;
        }

        static int HexManhattan(string a, string b)
        {
            if (!TryParseHexRgb(a, out var ar, out var ag, out var ab) ||
                !TryParseHexRgb(b, out var br, out var bg, out var bb))
                return int.MaxValue;
            return Mathf.Abs(ar - br) + Mathf.Abs(ag - bg) + Mathf.Abs(ab - bb);
        }

        static bool TryParseHexRgb(string hex, out int r, out int g, out int b)
        {
            r = g = b = 0;
            if (string.IsNullOrWhiteSpace(hex))
                return false;
            var s = hex.Trim();
            if (s.StartsWith("#"))
                s = s.Substring(1);
            if (s.Length != 6)
                return false;
            try
            {
                r = Convert.ToInt32(s.Substring(0, 2), 16);
                g = Convert.ToInt32(s.Substring(2, 2), 16);
                b = Convert.ToInt32(s.Substring(4, 2), 16);
                return true;
            }
            catch
            {
                return false;
            }
        }

        string NearestPaletteName(string hex)
        {
            var best = ColorNames[_colorIndex];
            var bestDist = int.MaxValue;
            for (var i = 0; i < InkColors.Length; i++)
            {
                var c = InkColors[i];
                var chip = $"#{Mathf.RoundToInt(c.r * 255):X2}{Mathf.RoundToInt(c.g * 255):X2}{Mathf.RoundToInt(c.b * 255):X2}";
                var d = HexManhattan(hex, chip);
                if (d < bestDist)
                {
                    bestDist = d;
                    best = ColorNames[i];
                }
            }

            return best;
        }

        void PersistMaterialSession()
        {
            if (App == null)
                return;
            // Read the ink itself first: chips only record what was tapped, not what was painted.
            if (_pad != null)
                App.CreateDesign.SketchColorRegions = _pad.DescribeColorRegions();

            var painted = PaintedRegionHexes();
            var pairs = BuildMaterialPairs();
            App.CreateDesign.SketchMaterialPairs = pairs;

            if (painted.Count == 1)
                App.CreateDesign.SketchColorName = NearestPaletteName(painted[0]);
            else if (painted.Count == 0)
                App.CreateDesign.SketchColorName = ColorNames[_colorIndex];
            else
                App.CreateDesign.SketchColorName = "";

            var fabrics = new HashSet<string>(StringComparer.OrdinalIgnoreCase);
            if (!string.IsNullOrEmpty(pairs))
            {
                foreach (var part in pairs.Split(';'))
                {
                    var bits = part.Split(':');
                    if (bits.Length >= 2 && !string.IsNullOrWhiteSpace(bits[1]))
                        fabrics.Add(bits[1].Trim());
                }
            }

            if (fabrics.Count == 1)
            {
                foreach (var name in fabrics)
                {
                    App.CreateDesign.SketchFabricName = name;
                    App.CreateDesign.MaterialId = name.ToLowerInvariant();
                    break;
                }
            }
            else if (fabrics.Count > 1 || painted.Count > 0)
            {
                // Mixed fabrics, or leftover chips with no fabric on the painted color —
                // don't send a last-tapped chip as "the" fabric.
                App.CreateDesign.SketchFabricName = "";
            }
            else if (_fabricIndex >= 0)
            {
                App.CreateDesign.SketchFabricName = Fabrics[_fabricIndex].name;
                App.CreateDesign.MaterialId = Fabrics[_fabricIndex].name.ToLowerInvariant();
            }
        }

        void RestoreMaterialPairsFromSession()
        {
            var raw = App?.CreateDesign.SketchMaterialPairs?.Trim() ?? "";
            if (string.IsNullOrEmpty(raw))
                return;
            foreach (var part in raw.Split(';'))
            {
                var bits = part.Split(':');
                if (bits.Length < 2)
                    continue;
                var colorName = bits[0].Trim();
                var fabricName = bits[1].Trim();
                // Migrate old Gold/Navy names from previous sessions
                if (string.Equals(colorName, "Gold", System.StringComparison.OrdinalIgnoreCase))
                    colorName = "Orange";
                if (string.Equals(colorName, "Navy", System.StringComparison.OrdinalIgnoreCase))
                    colorName = "Blue";
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
            var who = SketchFigurePreferences.DefaultTemplate == SketchFigureTemplate.Male ? "Men" : "Women";
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
                var who = SketchFigurePreferences.DefaultTemplate == SketchFigureTemplate.Male ? "Men" : "Women";
                ApplyCurrentFigure($"{who} — sketch your look!");
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
                var who = forced.Value == SketchFigureTemplate.Male ? "Men" : "Women";
                ApplyCurrentFigure($"{who} — sketch your look!");
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
